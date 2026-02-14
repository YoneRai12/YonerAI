from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from pydantic import BaseModel

class ToolContext(BaseModel):
    user_id: str
    conversation_id: str
    run_id: str
    # Add other context like lat/long or user preferences if needed

class BaseTool(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        pass

    @property
    def input_schema(self) -> Dict[str, Any]:
        """JSON Schema for input validation."""
        return {}

    @abstractmethod
    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        """
        Executes the tool logic.
        Returns a string representation of the result to be fed into the LLM.
        """
        pass
