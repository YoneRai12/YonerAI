import logging
import asyncio
from typing import Any
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession

from ora_core.api.schemas.messages import MessageRequest
from ora_core.database.repo import Repository, RunStatus
from ora_core.brain.context import ContextBuilder
from ora_core.brain.memory import memory_store
# from ora_core.engine.omni_engine import remote_engine # To be implemented/connected
from ora_core.engine.simple_worker import event_manager # For event streaming
from src.utils.cost_manager import CostManager, Usage

logger = logging.getLogger(__name__)

class MainProcess:
    """
    The Central Brain Loop.
    Coordinates: Input -> Context -> Engine -> Output -> Memory Update.
    """
    
    def __init__(self, run_id: str, conversation_id: str, request: MessageRequest, db_session: AsyncSession):
        self.run_id = run_id
        self.conversation_id = conversation_id
        self.request = request
        self.db = db_session
        self.repo = Repository(db_session)
        self.cost_manager = CostManager()

    async def run(self):
        """Execute the cognitive cycle."""
        try:
            # 1. Status -> In Progress
            await self.repo.update_run_status(self.run_id, RunStatus.in_progress)
            
            # 2. Build Context (Brain)
            user = await self.repo.get_or_create_user(
                self.request.user_identity.provider,
                self.request.user_identity.id,
                self.request.user_identity.display_name
            )
            
            context_messages = await ContextBuilder.build_context(self.request, user.id, self.conversation_id, self.repo)
            
            # [Moltbook] Soul Injection
            try:
                # Soul path is relative to repo root: memory/soul.md
                # Avoid machine-specific absolute paths so Core works across environments.
                from pathlib import Path

                repo_root = Path(__file__).resolve().parents[4]
                soul_path = repo_root / "memory" / "soul.md"
                if soul_path.exists():
                    with open(soul_path, "r", encoding="utf-8") as f:
                        soul_content = f.read().strip()
                        if soul_content:
                            # Prepend to context (System Prompt)
                            context_messages.insert(0, {
                                "role": "system", 
                                "content": f"[SYSTEM IDENTITY]\n{soul_content}"
                            })
                            logger.info("👻 Core: Soul Injected.")
            except Exception as e:
                logger.warning(f"Core Soul Injection Failed: {e}")

            client_type = getattr(self.request, "source", "web")
            should_stream = getattr(self.request, "stream", True)
            selected_tool_schemas = self._resolve_selected_tools_for_core(client_type)
            if client_type == "discord" and selected_tool_schemas:
                self._register_missing_discord_proxy_tools(selected_tool_schemas)
            
            from ora_core.engine.omni_engine import omni_engine
            from ora_core.mcp.runner import ToolRunner
            import json
            
            runner = ToolRunner(self.repo)

            # 3. LLM Execution Loop (Intelligent Tool Use)
            llm_pref = getattr(self.request, "llm_preference", None)
            max_turns = 5
            final_response_text = ""
            
            for turn in range(max_turns):
                logger.info(f"Run {self.run_id} Turn {turn+1}: Generating response (Pref: {llm_pref})...")
                
                # In Phase 6, we use non-streaming call to LLM to handle tool_calls robustly,
                # then manually stream the text content to the user for UX.
                response = await omni_engine.generate(
                    context_messages,
                    client_type,
                    stream=False,
                    preference=llm_pref,
                    tool_schemas=selected_tool_schemas or None,
                )
                
                # --- COST TRACKING ---
                usage_info = getattr(response, "usage", None)
                if usage_info:
                    try:
                        exec_model = getattr(response, "model", "unknown")
                        # Routing Heuristic
                        lane = "optimization"
                        provider = "local"
                        low_model = exec_model.lower()
                        
                        if any(k in low_model for k in ["gpt-4o", "gpt-4-turbo", "o1", "o3"]):
                             if "mini" in low_model:
                                 lane = "stable"
                                 provider = "openai"
                             else:
                                 lane = "high"
                                 provider = "openai"
                        elif "gemini" in low_model:
                             lane = "burn"
                             provider = "gemini_trial"
                        elif "claude" in low_model:
                             lane = "high"
                             provider = "claude"
                        
                        # Use Discord ID for tracking
                        target_uid = self.request.user_identity.id
                        
                        u_obj = Usage(tokens_in=usage_info.prompt_tokens, tokens_out=usage_info.completion_tokens)
                        self.cost_manager.add_cost(lane, provider, target_uid, u_obj)
                        logger.info(f"💰 Cost Tracked: {lane}:{provider} ({u_obj.tokens_in} in, {u_obj.tokens_out} out)")
                    except Exception as e:
                        logger.error(f"Failed to track cost: {e}")
                # ---------------------

                message = response.choices[0].message
                content = message.content or ""
                tool_calls = message.tool_calls
                
                if not tool_calls:
                    # Final Turn (or just text)
                    final_response_text = content
                    context_messages.append({"role": "assistant", "content": content})
                    break
                else:
                    # Intermediate turn with tool calls
                    # Note: We must convert message to dict or store it as is if OmniEngine expects objects.
                    # Usually OpenAI message objects work.
                    context_messages.append(message)
                    
                    for tc in tool_calls:
                        tc_id = tc.id
                        t_name = tc.function.name
                        t_args = json.loads(tc.function.arguments)
                        
                        logger.info(f"Executing Tool: {t_name} (ID: {tc_id})")
                        
                        result = await runner.run_tool(tc_id, self.run_id, user.id, t_name, t_args, client_type)

                        # Hub->Spoke bridge:
                        # If this tool was proxied to Discord client action, wait for submitted
                        # tool output from /v1/runs/{run_id}/results before continuing.
                        tool_data = result.get("result") or result.get("error")
                        dispatched_externally = (
                            client_type == "discord"
                            and isinstance(result.get("result"), dict)
                            and "client_action" in result.get("result", {})
                        )
                        if dispatched_externally:
                            await event_manager.emit(
                                self.run_id,
                                "progress",
                                {"status": f"Waiting client tool result: {t_name}"},
                            )
                            try:
                                submitted = await event_manager.wait_for_tool_result(
                                    self.run_id,
                                    tc_id,
                                    timeout_sec=180,
                                )
                                tool_data = submitted.get("result", "[Success]")
                            except asyncio.TimeoutError:
                                tool_data = {
                                    "ok": False,
                                    "error": {
                                        "code": "CLIENT_RESULT_TIMEOUT",
                                        "message": f"Timed out waiting for client result: {t_name}",
                                    },
                                }
                            except asyncio.CancelledError:
                                tool_data = {
                                    "ok": False,
                                    "error": {
                                        "code": "CLIENT_RESULT_CANCELLED",
                                        "message": f"Client result wait cancelled: {t_name}",
                                    },
                                }
                        
                        context_messages.append({
                            "role": "tool",
                            "tool_call_id": tc_id,
                            "name": t_name,
                            "content": json.dumps(tool_data)
                        })
            
            # 4. Save Assistant Message (Repo)
            await self.repo.create_assistant_message(self.conversation_id, final_response_text)
            
            # 5. Update Memory (L3/L4)
            await self._update_memory_on_completion(user.id, self.request.content, final_response_text)

            # 6. Final Event & Status
            await event_manager.emit(self.run_id, "final", {
                "text": final_response_text, "message_id": "pending-db-save"
            })
            await self.repo.update_run_status(self.run_id, RunStatus.completed)

        except Exception as e:
            logger.error(f"MainProcess Error: {e}", exc_info=True)
            await self.repo.update_run_status(self.run_id, RunStatus.failed)
            await event_manager.emit(self.run_id, "error", {"message": str(e)})

    def _resolve_selected_tools_for_core(self, client_type: str) -> list[dict[str, Any]]:
        """
        Resolve client-selected tool schemas to an executable subset for Core.
        - Keeps only tools registered in Core and allowed for the current client_type.
        - Preserves router-selected order to keep behavior stable.
        """
        from ora_core.mcp.registry import tool_registry

        requested = getattr(self.request, "available_tools", None) or []
        if not requested:
            return []

        allowed_defs = {t.name: t for t in tool_registry.list_tools_for_client(client_type)}
        resolved: list[dict[str, Any]] = []
        seen: set[str] = set()

        for tool in requested:
            if not isinstance(tool, dict):
                continue
            name = tool.get("name")
            if not isinstance(name, str) or name in seen:
                continue
            if name in allowed_defs:
                definition = allowed_defs[name]
                params = tool.get("parameters") if isinstance(tool.get("parameters"), dict) else definition.parameters
                desc = tool.get("description") if isinstance(tool.get("description"), str) else definition.description
                resolved.append({"name": name, "description": desc, "parameters": params})
            elif client_type == "discord":
                # For Discord, allow client-selected tools to be auto-proxied to Bot ToolHandler.
                params = tool.get("parameters") if isinstance(tool.get("parameters"), dict) else {"type": "object", "properties": {}}
                desc = (
                    tool.get("description")
                    if isinstance(tool.get("description"), str)
                    else f"Dispatch '{name}' to Discord client tool handler."
                )
                resolved.append({"name": name, "description": desc, "parameters": params})
            seen.add(name)

        return resolved

    def _register_missing_discord_proxy_tools(self, selected_tools: list[dict[str, Any]]) -> None:
        """
        Register missing Discord tools as lightweight proxy tools so Core can dispatch
        router-selected client capabilities without hardcoding every tool in Core.
        """
        import re

        from ora_core.mcp.registry import ToolDefinition, tool_registry

        async def dynamic_discord_proxy(args: dict, context: dict) -> dict[str, Any]:
            return {
                "ok": True,
                "content": [{"type": "text", "text": "Dispatching action to Discord client..."}],
                "client_action": args,
            }

        valid_name = re.compile(r"^[a-zA-Z0-9_\\-]{1,64}$")
        for tool in selected_tools:
            name = tool.get("name")
            if not isinstance(name, str) or not valid_name.match(name):
                continue
            if tool_registry.get_definition(name):
                continue
            params = tool.get("parameters") if isinstance(tool.get("parameters"), dict) else {"type": "object", "properties": {}}
            desc = tool.get("description") if isinstance(tool.get("description"), str) else f"Discord proxy for {name}"
            tool_registry.register_tool(
                ToolDefinition(
                    name=name,
                    description=desc,
                    parameters=params,
                    allowed_clients=["discord"],
                ),
                dynamic_discord_proxy,
            )

    async def _update_memory_on_completion(self, user_id: str, user_text: str, assistant_text: str):
        """Append to Raw Logs (L4) and trigger background summarization (L3)."""
        # Keep the memory file ID consistent with ContextBuilder (guild-scoped for Discord).
        target_memory_id = user_id
        if self.request.user_identity.provider == "discord":
            guild_id = None
            try:
                if self.request.client_context and getattr(self.request.client_context, "guild_id", None):
                    guild_id = self.request.client_context.guild_id
            except Exception:
                guild_id = None
            if guild_id:
                target_memory_id = f"{self.request.user_identity.id}_{guild_id}_public"
            else:
                target_memory_id = self.request.user_identity.id

        profile = await memory_store.get_or_create_profile(
            target_memory_id,
            default_name=self.request.user_identity.display_name or "User",
        )

        # L4: Raw Logs
        if "layer4_raw_logs" not in profile:
            profile["layer4_raw_logs"] = []

        profile["layer4_raw_logs"].append(
            {
                "timestamp": datetime.now().isoformat(),
                "user": user_text,
                "assistant": assistant_text,
            }
        )
        profile["last_updated"] = datetime.now().isoformat()

        # Atomic Save
        await memory_store.save_user_profile(target_memory_id, profile)
