"""Белый список инструментов и их JSON Schema."""
from dataclasses import dataclass
from typing import Awaitable, Callable
from pydantic import BaseModel


@dataclass(frozen=True)
class RegisteredTool:
    name: str
    description: str
    arguments: type[BaseModel]
    handler: Callable[[BaseModel], Awaitable[object]]
    timeout_seconds: float | None = None

    def ollama_schema(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.arguments.model_json_schema(),
            },
        }


class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, RegisteredTool] = {}

    def register(self, tool: RegisteredTool) -> None:
        if tool.name in self._tools:
            raise ValueError(f"Инструмент {tool.name} зарегистрирован дважды")
        self._tools[tool.name] = tool

    def get(self, name: str) -> RegisteredTool | None:
        return self._tools.get(name)

    def ollama_schemas(self) -> list[dict]:
        return [tool.ollama_schema() for tool in self._tools.values()]
