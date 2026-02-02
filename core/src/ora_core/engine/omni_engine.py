import os

from openai import AsyncOpenAI
from ora_core.mcp.registry import tool_registry


class OmniEngine:
    def __init__(self):
        from dotenv import load_dotenv
        load_dotenv(override=True)
        
        self.api_key = (os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY") or "").strip()
        self.local_url = os.getenv("LLM_BASE_URL", "http://127.0.0.1:8008/v1").rstrip("/")
        self.model = os.getenv("LLM_MODEL") or "mistralai/ministral-3-14b-reasoning"
        
        # 1. Local Client (vLLM)
        # Set short timeout for local connections to fail fast and trigger fallback
        self.local_client = AsyncOpenAI(api_key="EMPTY", base_url=self.local_url, timeout=5.0)
        
        # 2. Cloud Client (OpenAI)
        self.cloud_client = None
        openai_key = (os.getenv("OPENAI_API_KEY") or "").strip()
        if openai_key and not openai_key.startswith("sk-xxxx"):
            base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
            self.cloud_client = AsyncOpenAI(api_key=openai_key, base_url=base_url, timeout=60.0)
        
        # Priority Preference: Default to 'cloud' (API) as per user request
        self.default_priority = os.getenv("ORA_LLM_PRIORITY", "cloud").lower()
        
        print(f"🚀 OmniEngine: Initialized with Model: {self.model}")
        print(f"   - Local: {self.local_url}")
        if self.cloud_client:
            print("   - Cloud Fallback: Enabled (OpenAI)")
        else:
            print("   - Cloud Fallback: DISABLED (Key missing or invalid)")

    async def generate_response(self, messages: list[dict], client_type: str = "web", preference: str = None):
        """Non-streaming generation with Intelligent Fallback and Manual Preference."""
        tools = self._get_tools_param(client_type)
        
        # Determine Priority & Model Override
        actual_priority = self.default_priority
        override_model = None
        
        if preference:
            if preference in ["cloud", "local"]:
                actual_priority = preference
            else:
                # Treat as specific model name (e.g. "ORA gpt-5")
                # Strip "ORA " prefix if present
                clean_model = preference.replace("ORA ", "").strip()
                override_model = clean_model
                
                # Auto-route to cloud if it looks like a GPT model
                if any(m in clean_model.lower() for m in ["gpt-", "o1", "o3", "o4", "chatgpt"]):
                    actual_priority = "cloud"
                else:
                    actual_priority = "local" # Or cloud if unknown, but let's stick to safe local default or auto logic?
                    # Actually if user asks for specific model, we should probably check if it is cloud capable.
                    # For now, explicit GPT -> Cloud. Everything else -> Local (or let fallback handle it).

        is_cloud_model = any(m in self.model.lower() for m in ["gpt-", "o1-", "o3-", "o4-", "chatgpt"])
        
        if actual_priority == "cloud":
            primary = self.cloud_client if self.cloud_client else self.local_client
            secondary = self.local_client if primary == self.cloud_client else None
        elif actual_priority == "local":
            primary = self.local_client
            secondary = self.cloud_client
        else: # Auto logic
            primary = self.cloud_client if is_cloud_model else self.local_client
            secondary = self.local_client if is_cloud_model else self.cloud_client
        
        # --- TEMPERATURE CONSTRAINT ---
        # User: "gpt-5, o1, o3, etc... don't put temperature or it errors"
        # Check override model too
        target_model = override_model or self.model
        omit_temp_models = ["gpt-5", "o1", "o3", "o4", "codex"]
        should_omit_temp = any(m in target_model.lower() for m in omit_temp_models)
        
        gen_params = {
            "model": target_model,
            "messages": messages,
            "tools": tools,
            "stream": False
        }
        if not should_omit_temp:
            gen_params["temperature"] = 0.7
        
        try:
            # 1. Try Primary
            if primary:
                exec_model = target_model
                # Safety: If using cloud client but model name is not a cloud model, fallback to a safe gpt-4o-mini
                if primary == self.cloud_client and not override_model and not is_cloud_model:
                    exec_model = "gpt-4o-mini"
                
                # Safety: If using local client (or fallback to local), do NOT pass gpt/o1 names.
                # Use self.model (the local default) instead.
                if primary == self.local_client and any(m in exec_model.lower() for m in ["gpt-", "o1", "o3", "o4", "chatgpt"]):
                    print(f"⚠️ OmniEngine: Model '{exec_model}' not found locally. Fallback to default local model: {self.model}")
                    exec_model = self.model

                # Copy params and update model
                current_params = gen_params.copy()
                current_params["model"] = exec_model
                current_params["model"] = exec_model
                
                return await primary.chat.completions.create(**current_params)
        except Exception as e:
            print(f"⚠️ OmniEngine: Primary Layer failed: {e}. Trying Fallback...")
            
        # 2. Try Secondary (Fallback)
        if secondary:
            # Fallback to a safe cloud model if local model name might fail on cloud
            fallback_model = target_model
            if secondary == self.cloud_client and not override_model and not is_cloud_model:
                # Use a standard cheap model as fallback
                fallback_model = "gpt-4o-mini"
                
            return await secondary.chat.completions.create(
                model=fallback_model, messages=messages, tools=tools, stream=False, temperature=0.7 if not should_omit_temp else None
            )
            
        raise RuntimeError("OmniEngine: Both Primary and Fallback layers failed.")

    def _get_tools_param(self, client_type: str) -> list[dict] | None:
        """Fetch tools from registry and format for OpenAI."""
        tools = tool_registry.list_tools_for_client(client_type)
        if not tools:
            return None
        
        openai_tools = []
        for t in tools:
            openai_tools.append({
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description,
                    "parameters": t.parameters # Already a dict with type/properties/required
                }
            })
        return openai_tools

    async def generate_stream(self, messages: list[dict], client_type: str = "web", preference: str = None):
        """Streaming generation with Intelligent Fallback and Preference."""
        tools = self._get_tools_param(client_type)
        
        # Determine Priority & Model Override (Duplicated logic for safety in both paths)
        actual_priority = self.default_priority
        override_model = None
        
        if preference:
            if preference in ["cloud", "local"]:
                actual_priority = preference
            else:
                clean_model = preference.replace("ORA ", "").strip()
                override_model = clean_model
                if any(m in clean_model.lower() for m in ["gpt-", "o1", "o3", "o4", "chatgpt"]):
                    actual_priority = "cloud"
                else:
                    actual_priority = "local"

        is_cloud_model = any(m in self.model.lower() for m in ["gpt-", "o1-", "o3-", "o4-", "chatgpt"])
        
        if actual_priority == "cloud":
            primary = self.cloud_client if self.cloud_client else self.local_client
            secondary = self.local_client if primary == self.cloud_client else None
        elif actual_priority == "local":
            primary = self.local_client
            secondary = self.cloud_client
        else:
            primary = self.cloud_client if is_cloud_model else self.local_client
            secondary = self.local_client if is_cloud_model else self.cloud_client

        # Target Model
        target_model = override_model or self.model
        omit_temp_models = ["gpt-5", "o1", "o3", "o4", "codex"]
        
        # 1. Try Primary
        if primary:
            try:
                should_omit_temp = any(m in target_model.lower() for m in omit_temp_models)
                params = {"model": target_model, "messages": messages, "tools": tools, "stream": True}
                if not should_omit_temp:
                    params["temperature"] = 0.7
                
                # Safety fallback logic integration
                if primary == self.cloud_client and not override_model and not is_cloud_model:
                     params["model"] = "gpt-4o-mini"
                
                # Safety: If using local client (or fallback to local), do NOT pass gpt/o1 names.
                # Use self.model (the local default) instead.
                if primary == self.local_client and any(m in target_model.lower() for m in ["gpt-", "o1", "o3", "o4", "chatgpt"]):
                    print(f"⚠️ OmniEngine (Stream): Model '{target_model}' not found locally. Fallback to default local model: {self.model}")
                    params["model"] = self.model

                # Yield Metadata
                yield {"type": "meta", "model": target_model}

                response_stream = await primary.chat.completions.create(**params)
                async for chunk in response_stream:
                    if chunk.choices and chunk.choices[0].delta.content:
                        content = chunk.choices[0].delta.content
                        yield {"type": "text", "content": content}
                return # Success
            except Exception as e:
                print(f"⚠️ OmniEngine (Stream): Primary Layer failed: {e}. Trying Fallback...")

        # 2. Try Secondary
        if secondary:
            try:
                fallback_model = target_model
                if secondary == self.cloud_client and not override_model and not is_cloud_model:
                    fallback_model = "gpt-4o-mini"
                
                should_omit_temp_fb = any(m in fallback_model.lower() for m in omit_temp_models)
                fb_params = {"model": fallback_model, "messages": messages, "tools": tools, "stream": True}
                if not should_omit_temp_fb:
                    fb_params["temperature"] = 0.7
                
                # Yield Metadata (Fallback)
                yield {"type": "meta", "model": fallback_model}

                response_stream = await secondary.chat.completions.create(**fb_params)
                async for chunk in response_stream:
                    if chunk.choices and chunk.choices[0].delta.content:
                        content = chunk.choices[0].delta.content
                        yield {"type": "text", "content": content}
                return # Success
            except Exception as e:
                yield f"\n[System Error: Both layers failed. Last Error: {str(e)}]"
        else:
            yield "\n[System Error: No fallback layer available.]"

    async def generate(self, messages: list[dict], client_type: str = "web", stream: bool = True, preference: str = None):
        # Deprecated: use specific methods. Kept for back-compat if needed, 
        # but caution: can't be both async def and async generator easily.
        if stream:
            return self.generate_stream(messages, client_type, preference=preference)
        else:
            return await self.generate_response(messages, client_type, preference=preference)

# Singleton instance
omni_engine = OmniEngine()
