import asyncio

import pytest
from pydantic import BaseModel

from backend.app.agent.tools.executor import ToolExecutor
from backend.app.agent.tools.registry import RegisteredTool, ToolRegistry


class Args(BaseModel):
    value: int = 1


@pytest.mark.asyncio
async def test_registered_tool_timeout_overrides_default_timeout():
    async def slow(_args):
        await asyncio.sleep(0.03)
        return {"ok": True}

    registry = ToolRegistry()
    registry.register(RegisteredTool("slow", "test", Args, slow, timeout_seconds=0.1))

    result = await ToolExecutor(registry, timeout_seconds=0.01).execute("slow", {})

    assert result["ok"] is True


@pytest.mark.asyncio
async def test_default_timeout_still_applies_without_tool_override():
    async def slow(_args):
        await asyncio.sleep(0.03)
        return {"ok": True}

    registry = ToolRegistry()
    registry.register(RegisteredTool("slow", "test", Args, slow))

    result = await ToolExecutor(registry, timeout_seconds=0.01).execute("slow", {})

    assert result["error"] == "timeout"
