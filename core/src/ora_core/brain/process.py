import logging
import asyncio
import time
from typing import Any
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession

from ora_core.api.schemas.messages import EffectiveRoute, MessageRequest
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

    _ROUTE_DEFAULTS: dict[str, dict[str, int]] = {
        "INSTANT": {"max_turns": 2, "max_tool_calls": 0, "time_budget_seconds": 25},
        "TASK": {"max_turns": 5, "max_tool_calls": 5, "time_budget_seconds": 120},
        "AGENT_LOOP": {"max_turns": 8, "max_tool_calls": 10, "time_budget_seconds": 300},
    }

    @staticmethod
    def _clamp_int(value: Any, default: int, *, lo: int, hi: int) -> int:
        try:
            v = int(value)
        except Exception:
            v = int(default)
        return max(lo, min(hi, v))

    @staticmethod
    def _clamp_float(value: Any, default: float, *, lo: float = 0.0, hi: float = 1.0) -> float:
        try:
            v = float(value)
        except Exception:
            v = float(default)
        return max(lo, min(hi, v))

    @staticmethod
    def _dedup_reason_codes(raw: Any) -> list[str]:
        out: list[str] = []
        if not isinstance(raw, list):
            return out
        for x in raw:
            rc = str(x or "").strip()
            if rc and rc not in out:
                out.append(rc)
        return out

    @staticmethod
    def _risk_level_from_score(score: float) -> str:
        s = max(0.0, min(1.0, float(score)))
        if s >= 0.9:
            return "CRITICAL"
        if s >= 0.6:
            return "HIGH"
        if s >= 0.3:
            return "MEDIUM"
        return "LOW"

    @staticmethod
    def _mode_from_difficulty(score: float) -> str:
        d = max(0.0, min(1.0, float(score)))
        if d <= 0.3:
            return "INSTANT"
        if d <= 0.6:
            return "TASK"
        return "AGENT_LOOP"

    @staticmethod
    def _append_reason_code(effective_route: dict[str, Any], reason_code: str) -> None:
        rc = str(reason_code or "").strip()
        if not rc:
            return
        reason_codes = effective_route.get("reason_codes")
        if not isinstance(reason_codes, list):
            reason_codes = []
            effective_route["reason_codes"] = reason_codes
        if rc not in reason_codes:
            reason_codes.append(rc)

    async def _persist_effective_route(self, effective_route: dict[str, Any]) -> None:
        try:
            from src.utils.link_attribution import record_run_effective_route

            await record_run_effective_route(run_id=self.run_id, effective_route=effective_route)
        except Exception:
            pass

    def _resolve_effective_route(self, selected_tool_schemas: list[dict[str, Any]]) -> dict[str, Any]:
        hint: dict[str, Any] = {}
        raw_hint = getattr(self.request, "route_hint", None)
        if raw_hint is not None:
            if hasattr(raw_hint, "model_dump"):
                try:
                    dumped = raw_hint.model_dump()
                    if isinstance(dumped, dict):
                        hint = dumped
                except Exception:
                    hint = {}
            elif isinstance(raw_hint, dict):
                hint = raw_hint

        difficulty_score = self._clamp_float(hint.get("difficulty_score"), 0.5)
        complexity_score = self._clamp_float(hint.get("complexity_score"), difficulty_score)
        action_score = self._clamp_float(hint.get("action_score"), difficulty_score)
        security_risk_score = self._clamp_float(hint.get("security_risk_score"), 0.0)
        function_category = str(hint.get("function_category") or "chat").strip().lower() or "chat"
        route_score_hint = hint.get("route_score")
        if route_score_hint is None:
            route_score = (complexity_score * 0.45) + (security_risk_score * 0.35) + (action_score * 0.20)
        else:
            route_score = self._clamp_float(route_score_hint, difficulty_score)

        budget_hint = hint.get("budget")
        budget_dict = budget_hint if isinstance(budget_hint, dict) else {}

        def _build_budget(route_defaults: dict[str, int]) -> dict[str, int]:
            return {
                "max_turns": self._clamp_int(budget_dict.get("max_turns"), route_defaults["max_turns"], lo=1, hi=20),
                "max_tool_calls": self._clamp_int(
                    budget_dict.get("max_tool_calls"),
                    route_defaults["max_tool_calls"],
                    lo=0,
                    hi=20,
                ),
                "time_budget_seconds": self._clamp_int(
                    budget_dict.get("time_budget_seconds"),
                    route_defaults["time_budget_seconds"],
                    lo=10,
                    hi=1800,
                ),
            }

        reason_codes = self._dedup_reason_codes(hint.get("reason_codes"))
        floor_applied = False
        if function_category == "vision" and route_score < 0.35:
            route_score = 0.35
            floor_applied = True
            if "router_vision_floor_applied" not in reason_codes:
                reason_codes.append("router_vision_floor_applied")

        mode_hint = str(hint.get("mode") or "").strip().upper()
        if mode_hint in self._ROUTE_DEFAULTS and not floor_applied:
            mode = mode_hint
        else:
            mode = self._mode_from_difficulty(route_score)
        defaults = dict(self._ROUTE_DEFAULTS.get(mode, self._ROUTE_DEFAULTS["TASK"]))
        budget = _build_budget(defaults)
        security_risk_level = str(hint.get("security_risk_level") or "").strip().upper()
        if not security_risk_level:
            security_risk_level = self._risk_level_from_score(security_risk_score)

        high_risk = security_risk_score >= 0.6 or security_risk_level in {"HIGH", "CRITICAL"}
        if mode in {"INSTANT", "AGENT_LOOP"} and high_risk:
            mode = "TASK"
            defaults = dict(self._ROUTE_DEFAULTS["TASK"])
            budget = _build_budget(defaults)
            if "router_mode_forced_safe" not in reason_codes:
                reason_codes.append("router_mode_forced_safe")

        if selected_tool_schemas and mode == "INSTANT":
            mode = "TASK"
            defaults = dict(self._ROUTE_DEFAULTS["TASK"])
            budget = _build_budget(defaults)
            if "router_mode_forced_tools" not in reason_codes:
                reason_codes.append("router_mode_forced_tools")

        if mode == "INSTANT":
            budget["max_tool_calls"] = 0
        elif not selected_tool_schemas:
            # Keep Core budget consistent with the actual executable tool set.
            budget["max_tool_calls"] = 0

        effective = EffectiveRoute(
            mode=mode,  # type: ignore[arg-type]
            function_category=function_category,
            route_score=round(route_score, 2),
            difficulty_score=round(difficulty_score, 2),
            complexity_score=round(complexity_score, 2),
            action_score=round(action_score, 2),
            security_risk_score=round(security_risk_score, 2),
            security_risk_level=security_risk_level,
            budget=budget,
            reason_codes=reason_codes,
            source_hint_present=bool(hint),
        )
        return effective.model_dump()

    async def run(self):
        """Execute the cognitive cycle."""
        effective_route: dict[str, Any] = {}
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
            del should_stream  # Reserved for future stream/no-stream divergence.
            selected_tool_schemas = self._resolve_selected_tools_for_core(client_type)
            if client_type == "discord" and selected_tool_schemas:
                self._register_missing_discord_proxy_tools(selected_tool_schemas)

            effective_route = self._resolve_effective_route(selected_tool_schemas)
            if effective_route.get("mode") == "INSTANT":
                selected_tool_schemas = []
            await self._persist_effective_route(effective_route)
            await event_manager.emit(
                self.run_id,
                "meta",
                {
                    "effective_route": effective_route,
                },
            )

            from ora_core.engine.omni_engine import omni_engine
            from ora_core.mcp.runner import ToolRunner
            import json
            import traceback
              
            runner = ToolRunner(self.repo)

            def _tool_content(tool_data: Any) -> str:
                # OpenAI tool message content must be a string.
                if isinstance(tool_data, str):
                    return tool_data
                if tool_data is None:
                    return ""
                try:
                    return json.dumps(tool_data, ensure_ascii=False)
                except Exception:
                    return str(tool_data)

            # 3. LLM Execution Loop (Intelligent Tool Use)
            llm_pref = getattr(self.request, "llm_preference", None)
            route_budget = effective_route.get("budget") if isinstance(effective_route, dict) else {}
            if not isinstance(route_budget, dict):
                route_budget = {}
            max_turns = self._clamp_int(route_budget.get("max_turns"), 5, lo=1, hi=20)
            max_tool_calls = self._clamp_int(route_budget.get("max_tool_calls"), 0, lo=0, hi=20)
            time_budget_seconds = self._clamp_int(route_budget.get("time_budget_seconds"), 120, lo=10, hi=1800)
            started_at = time.monotonic()
            tool_calls_used = 0
            budget_stop_reason: str | None = None
            final_response_text = ""
            last_content: str = ""
              
            for turn in range(max_turns):
                if (time.monotonic() - started_at) >= float(time_budget_seconds):
                    budget_stop_reason = "router_budget_time_exceeded"
                    self._append_reason_code(effective_route, budget_stop_reason)
                    break
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
                last_content = content
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
                        if (time.monotonic() - started_at) >= float(time_budget_seconds):
                            budget_stop_reason = "router_budget_time_exceeded"
                            self._append_reason_code(effective_route, budget_stop_reason)
                            break
                        if tool_calls_used >= max_tool_calls:
                            budget_stop_reason = "router_budget_tool_exceeded"
                            self._append_reason_code(effective_route, budget_stop_reason)
                            break
                        tc_id = tc.id
                        t_name = tc.function.name
                        try:
                            t_args = json.loads(tc.function.arguments or "{}")
                        except json.JSONDecodeError as e:
                            logger.warning(
                                f"Tool {t_name} (ID: {tc_id}): Invalid JSON arguments: {e}. args={tc.function.arguments!r}"
                            )
                            context_messages.append(
                                {
                                    "role": "tool",
                                    "tool_call_id": tc_id,
                                    "name": t_name,
                                    "content": _tool_content({"ok": False, "error": f"Invalid arguments JSON: {str(e)}"}),
                                }
                            )
                            continue
                        except Exception as e:
                            logger.warning(
                                f"Tool {t_name} (ID: {tc_id}): Failed to parse arguments. err={e} args={tc.function.arguments!r}"
                            )
                            context_messages.append(
                                {
                                    "role": "tool",
                                    "tool_call_id": tc_id,
                                    "name": t_name,
                                    "content": _tool_content({"ok": False, "error": f"Failed to parse arguments: {str(e)}"}),
                                }
                            )
                            continue
                        
                        logger.info(f"Executing Tool: {t_name} (ID: {tc_id})")

                        req_meta = self.request.request_meta.model_dump() if self.request.request_meta else None
                        result = await runner.run_tool(
                            tc_id,
                            self.run_id,
                            user.id,
                            t_name,
                            t_args,
                            client_type,
                            request_meta=req_meta,
                            effective_route=effective_route,
                        )

                        # Hub->Spoke bridge:
                        # If this tool was proxied to Discord client action, wait for submitted
                        # tool output from /v1/runs/{run_id}/results before continuing.
                        tool_data: Any = None
                        if isinstance(result, dict):
                            tool_data = result.get("result") if result.get("result") is not None else result.get("error")
                        else:
                            tool_data = result
                        dispatched_externally = (
                            client_type == "discord"
                            and isinstance(result, dict)
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
                            "content": _tool_content(tool_data)
                        })
                        tool_calls_used += 1
                    if budget_stop_reason:
                        break
            else:
                # The tool loop never produced a final assistant message. Avoid saving / streaming an empty response.
                self._append_reason_code(effective_route, "router_budget_turn_exceeded")
                final_response_text = last_content.strip() or (
                    f"[System] Tool execution exceeded {max_turns} turns. "
                    "Last tool calls were processed but a final response could not be generated."
                )

            if budget_stop_reason and not final_response_text.strip():
                final_response_text = last_content.strip() or (
                    f"[System] Route budget reached ({budget_stop_reason}). "
                    "Request stopped by Core safety limits."
                )

            # 4. Save Assistant Message (Repo)
            await self.repo.create_assistant_message(self.conversation_id, final_response_text)
            
            # 5. Update Memory (L3/L4)
            try:
                await self._update_memory_on_completion(user.id, self.request.content, final_response_text)
            except Exception as e:
                logger.error(f"Memory update failed (non-fatal): {e}\n{traceback.format_exc()}")

            # 6. Final Event & Status
            await self._persist_effective_route(effective_route)
            await event_manager.emit(self.run_id, "final", {
                "text": final_response_text,
                "message_id": "pending-db-save",
                "effective_route": effective_route,
            })
            await self.repo.update_run_status(self.run_id, RunStatus.completed)

        except Exception as e:
            logger.error(f"MainProcess Error: {e}", exc_info=True)
            await self.repo.update_run_status(self.run_id, RunStatus.failed)
            await self._persist_effective_route(effective_route)
            await event_manager.emit(
                self.run_id,
                "error",
                {
                    "message": str(e),
                    "effective_route": effective_route if isinstance(effective_route, dict) else {},
                },
            )

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
