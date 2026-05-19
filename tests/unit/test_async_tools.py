"""Tests for the async aio-pika publish tool."""

from __future__ import annotations

import json
import sys
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from langchain_rabbitmq.config import RabbitMQConfig
from langchain_rabbitmq.exceptions import RabbitMQMessageError
from langchain_rabbitmq.tools.message_tools import AsyncPublishMessageTool
from langchain_rabbitmq.utilities import AsyncConnectionManager

pytestmark = pytest.mark.unit


class _FakeExchange:
    def __init__(self) -> None:
        self.publish = AsyncMock()


class _FakeChannel:
    def __init__(self) -> None:
        self.default_exchange = _FakeExchange()
        self.custom_exchange = _FakeExchange()
        self.close = AsyncMock()

    async def get_exchange(self, name: str, ensure: bool = True) -> Any:
        del name, ensure
        return self.custom_exchange


@pytest.fixture
def fake_aio_pika(monkeypatch: pytest.MonkeyPatch) -> Any:
    """Inject a fake aio_pika module into sys.modules."""

    fake = MagicMock()

    class _DeliveryMode:
        PERSISTENT = 2
        NOT_PERSISTENT = 1

    class _Message:
        def __init__(self, body: bytes, **kw: Any) -> None:
            self.body = body
            self.kwargs = kw

    class _Excs:
        class AMQPError(Exception):
            pass

        class AMQPConnectionError(AMQPError):
            pass

    fake.DeliveryMode = _DeliveryMode
    fake.Message = _Message
    fake.connect_robust = AsyncMock()

    monkeypatch.setitem(sys.modules, "aio_pika", fake)
    monkeypatch.setitem(sys.modules, "aio_pika.exceptions", _Excs)
    return fake


@pytest.mark.asyncio
async def test_async_publish_default_exchange(fake_aio_pika: Any) -> None:
    fake_conn = MagicMock()
    fake_conn.is_closed = False
    channel = _FakeChannel()

    async def _channel() -> Any:
        return channel

    fake_conn.channel = _channel
    fake_aio_pika.connect_robust = AsyncMock(return_value=fake_conn)

    mgr = AsyncConnectionManager(RabbitMQConfig())
    tool = AsyncPublishMessageTool(manager=mgr)
    out = await tool.ainvoke({"routing_key": "q1", "body": "hi"})
    data = json.loads(out)
    assert data["published"] is True
    channel.default_exchange.publish.assert_awaited_once()
    channel.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_async_publish_named_exchange_json(fake_aio_pika: Any) -> None:
    fake_conn = MagicMock()
    fake_conn.is_closed = False
    channel = _FakeChannel()

    async def _channel() -> Any:
        return channel

    fake_conn.channel = _channel
    fake_aio_pika.connect_robust = AsyncMock(return_value=fake_conn)

    mgr = AsyncConnectionManager(RabbitMQConfig())
    tool = AsyncPublishMessageTool(manager=mgr)
    payload = {"k": "v"}
    out = await tool.ainvoke(
        {"exchange": "ex", "routing_key": "rk", "json_body": payload, "persistent": False}
    )
    data = json.loads(out)
    assert data["content_type"] == "application/json"
    channel.custom_exchange.publish.assert_awaited_once()


@pytest.mark.asyncio
async def test_async_publish_error_wrapped(fake_aio_pika: Any) -> None:
    fake_conn = MagicMock()
    fake_conn.is_closed = False
    channel = _FakeChannel()
    aio_exc = sys.modules["aio_pika.exceptions"].AMQPError  # type: ignore[attr-defined]
    channel.default_exchange.publish.side_effect = aio_exc("broken")

    async def _channel() -> Any:
        return channel

    fake_conn.channel = _channel
    fake_aio_pika.connect_robust = AsyncMock(return_value=fake_conn)

    mgr = AsyncConnectionManager(RabbitMQConfig())
    tool = AsyncPublishMessageTool(manager=mgr)
    with pytest.raises(RabbitMQMessageError):
        await tool.ainvoke({"routing_key": "q1", "body": "x"})
    channel.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_async_publish_requires_payload(fake_aio_pika: Any) -> None:
    mgr = AsyncConnectionManager(RabbitMQConfig())
    tool = AsyncPublishMessageTool(manager=mgr)
    with pytest.raises(RabbitMQMessageError):
        await tool._aexecute(routing_key="q1")
