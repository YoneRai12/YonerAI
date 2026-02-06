
import asyncio
import importlib.util
import json
import logging
import os
from typing import Any, Dict

logger = logging.getLogger(__name__)

class SkillLoader:
    """
    Loads skills from the src/skills directory following the Clawdbot pattern:
    src/skills/<skill_name>/SKILL.md (Description)
    src/skills/<skill_name>/tool.py (Implementation)
    """
    def __init__(self, root_dir: str = "src/skills"):
        self.root_dir = root_dir
        self.skills: Dict[str, Dict[str, Any]] = {}

    def load_skills(self):
        """Scans the directory and loads valid skills."""
        if not os.path.exists(self.root_dir):
            logger.warning(f"Skill root not found: {self.root_dir}")
            return

        for item in os.listdir(self.root_dir):
            skill_path = os.path.join(self.root_dir, item)
            if os.path.isdir(skill_path):
                self._load_single_skill(item, skill_path)
        
        logger.info(f"Loaded {len(self.skills)} skills: {list(self.skills.keys())}")

    def _load_single_skill(self, skill_name: str, path: str):
        md_path = os.path.join(path, "SKILL.md")
        tool_path = os.path.join(path, "tool.py")
        schema_path = os.path.join(path, "schema.json")

        if not os.path.exists(md_path):
            return  # Not a self-describing skill

        # Read Description
        try:
            with open(md_path, "r", encoding="utf-8") as f:
                description = f.read()
        except Exception as e:
            logger.error(f"Failed to read SKILL.md for {skill_name}: {e}")
            return

        # Load Python Module (Optional, but usually required for execution)
        module = None
        if os.path.exists(tool_path):
            try:
                spec = importlib.util.spec_from_file_location(f"skills.{skill_name}", tool_path)
                if spec and spec.loader:
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
            except Exception as e:
                logger.error(f"Failed to load tool.py for {skill_name}: {e}")

        # Optional schema (Anthropic/OpenAI-style tool schema)
        schema = None
        if module and hasattr(module, "TOOL_SCHEMA"):
            maybe = getattr(module, "TOOL_SCHEMA")
            if isinstance(maybe, dict):
                schema = maybe
        elif os.path.exists(schema_path):
            try:
                with open(schema_path, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                    if isinstance(loaded, dict):
                        schema = loaded
            except Exception as e:
                logger.error(f"Failed to read schema.json for {skill_name}: {e}")

        if not schema:
            # Safe generic fallback to keep dynamic onboarding fast.
            schema = {
                "name": skill_name,
                "description": f"Execute skill '{skill_name}'.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "input": {"type": "string", "description": "Skill input text"}
                    },
                    "required": []
                },
                "tags": ["dynamic", "skill"]
            }

        self.skills[skill_name] = {
            "name": skill_name,
            "description": description,
            "module": module,
            "path": path,
            "schema": schema,
        }

    def get_prompt_context(self) -> str:
        """Returns a string suitable for LLM System Prompt."""
        lines = ["## Available Skills"]
        for name, data in self.skills.items():
            lines.append(f"### {name}")
            lines.append(data["description"])
            lines.append("")
        return "\n".join(lines)

    async def execute_tool(self, tool_name: str, args: dict, message: Any, bot: Any = None) -> str:
        skill = self.skills.get(tool_name)
        if not skill or not skill["module"]:
             return "Skill not found or no implementation."
        
        if hasattr(skill["module"], "execute"):
             # Support both async and sync execute? Assuming async for now as per ToolHandler
             try:
                if asyncio.iscoroutinefunction(skill["module"].execute):
                    return await skill["module"].execute(args, message, bot=bot)
                else:
                    return skill["module"].execute(args, message, bot=bot)
             except Exception as e:
                 logger.error(f"Error executing skill {tool_name}: {e}")
                 return f"Error: {e}"
        return "Skill implementation has no execute function."

    def get_schema(self, tool_name: str) -> Dict[str, Any] | None:
        skill = self.skills.get(tool_name)
        if not skill:
            return None
        schema = skill.get("schema")
        if isinstance(schema, dict):
            return schema
        return None

