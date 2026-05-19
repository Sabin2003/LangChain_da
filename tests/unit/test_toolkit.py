"""Tests for RabbitMQToolkit."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from langchain_core.tools import BaseTool

from langchain_rabbitmq import RabbitMQConfig, RabbitMQToolkit
from langchain_rabbitmq.utilities import (
    AsyncConnectionManager,
    SyncConnectionManager,
)

pytestmark = pytest.mark.unit


def test_toolkit_get_tools_returns_basetools() -> None:
    sync_mgr = SyncConnectionManager(RabbitMQConfig())
    async_mgr = AsyncConnectionManager(RabbitMQConfig())
    tk = RabbitMQToolkit(sync_manager=sync_mgr, async_manager=async_mgr)
    tools = tk.get_tools()
    assert len(tools) >= 21  # 21 sync + 1 async
    for t in tools:
        assert isinstance(t, BaseTool)
        assert t.name.startswith("rabbitmq_")
        assert t.description
        assert t.args_schema is not None


def test_toolkit_tool_names_are_unique() -> None:
    tk = RabbitMQToolkit(config=RabbitMQConfig())
    names = [t.name for t in tk.get_tools()]
    assert len(names) == len(set(names)), names


def test_toolkit_exclude_async() -> None:
    tk = RabbitMQToolkit(config=RabbitMQConfig(), include_async=False)
    names = {t.name for t in tk.get_tools()}
    assert "rabbitmq_publish_message_async" not in names


def test_toolkit_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RABBITMQ_HOST", "broker.example")
    tk = RabbitMQToolkit.from_env()
    assert tk.config.host == "broker.example"


@pytest.mark.asyncio
async def test_toolkit_aclose() -> None:
    from unittest.mock import AsyncMock

    sync_mgr = MagicMock(spec=SyncConnectionManager)
    async_mgr = MagicMock(spec=AsyncConnectionManager)
    async_mgr.close = AsyncMock(return_value=None)
    tk = RabbitMQToolkit(
        config=RabbitMQConfig(),
        sync_manager=sync_mgr,
        async_manager=async_mgr,
    )
    await tk.aclose()
    sync_mgr.close.assert_called_once()
    async_mgr.close.assert_called_once()


def test_toolkit_shares_sync_manager_across_tools() -> None:
    sync_mgr = SyncConnectionManager(RabbitMQConfig())
    tk = RabbitMQToolkit(sync_manager=sync_mgr)
    sync_tools = [
        t for t in tk.get_tools() if not t.name.endswith("_async")
    ]
    for t in sync_tools:
        assert getattr(t, "manager", None) is sync_mgr
