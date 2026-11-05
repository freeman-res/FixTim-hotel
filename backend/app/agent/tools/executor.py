"""Безопасное выполнение только разрешённых инструментов."""
import asyncio
import logging
from pydantic import ValidationError
from .registry import ToolRegistry

logger = logging.getLogger(__name__)


class ToolExecutor:
    def __init__(self, registry: ToolRegistry, timeout_seconds: int = 30):
        self.registry = registry
        self.timeout_seconds = timeout_seconds

    async def execute(self, name: str, arguments: dict) -> dict:
        tool = self.registry.get(name)
        if tool is None:
            return {"ok": False, "error": "unknown_tool", "message": "Инструмент не зарегистрирован"}
        try:
            parsed = tool.arguments.model_validate(arguments)
        except ValidationError as exc:
            return {"ok": False, "error": "invalid_arguments", "message": str(exc)}
        try:
            logger.info("Вызов инструмента: %s", name)
            timeout = tool.timeout_seconds or self.timeout_seconds
            result = await asyncio.wait_for(tool.handler(parsed), timeout=timeout)
            return {"ok": True, "data": result}
        except TimeoutError:
            logger.warning("Таймаут инструмента: %s", name)
            return {"ok": False, "error": "timeout", "message": "Превышено время ожидания"}
        except Exception:
            logger.exception("Ошибка при выполнении %s", name)
            return {"ok": False, "error": "tool_failure", "message": "Ошибка поискового сервиса"}
