"""Unit tests for the synchronous queue/exchange/message/admin tools.

The tests stub :class:`SyncConnectionManager.channel` with a context manager
returning a :class:`MagicMock` channel — no real broker is required.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any
from unittest.mock import MagicMock

import pika
import pika.exceptions
import pytest

from langchain_rabbitmq.config import RabbitMQConfig
from langchain_rabbitmq.exceptions import (
    RabbitMQChannelError,
    RabbitMQMessageError,
)
from langchain_rabbitmq.tools import (
    AckMessageTool,
    BindExchangeTool,
    BindQueueTool,
    CheckHealthTool,
    CloseConnectionTool,
    ConsumeMessageTool,
    DeclareExchangeTool,
    DeclareQueueTool,
    DeleteExchangeTool,
    DeleteQueueTool,
    GetConnectionInfoTool,
    GetQueueInfoTool,
    NackMessageTool,
    PublishMessageTool,
    PurgeQueueTool,
    RejectMessageTool,
    UnbindQueueTool,
)
from langchain_rabbitmq.utilities import SyncConnectionManager

pytestmark = pytest.mark.unit


class FakeManager:
    """Minimal stand-in for :class:`SyncConnectionManager`."""

    def __init__(self, channel: MagicMock | None = None) -> None:
        self.channel_mock = channel or MagicMock()
        self.channel_mock.is_open = True
        self.config = RabbitMQConfig()
        self.closed = False
        self.is_open_value = True

    @contextmanager
    def channel(self) -> Iterator[MagicMock]:
        yield self.channel_mock

    def close(self) -> None:
        self.closed = True

    def is_open(self) -> bool:
        return self.is_open_value


def _make(tool_cls: type, channel: MagicMock | None = None) -> tuple[Any, FakeManager]:
    mgr = FakeManager(channel=channel)
    # Cast to SyncConnectionManager for the type checker; runtime is duck typed.
    tool = tool_cls(manager=mgr)  # type: ignore[arg-type]
    return tool, mgr


def _parse(result: str) -> dict[str, Any]:
    data = json.loads(result)
    assert isinstance(data, dict)
    return data


# --------------------------------------------------------------------------- #
# Queue tools
# --------------------------------------------------------------------------- #
def test_declare_queue_returns_metadata() -> None:
    ch = MagicMock()
    ch.queue_declare.return_value = MagicMock(
        method=MagicMock(queue="q1", message_count=3, consumer_count=1)
    )
    tool, mgr = _make(DeclareQueueTool, channel=ch)
    out = _parse(tool.invoke({"queue": "q1", "durable": True}))
    assert out == {"queue": "q1", "message_count": 3, "consumer_count": 1}
    ch.queue_declare.assert_called_once()
    assert isinstance(mgr, FakeManager)


def test_declare_queue_wraps_error() -> None:
    ch = MagicMock()
    ch.queue_declare.side_effect = pika.exceptions.AMQPError("bad")
    tool, _ = _make(DeclareQueueTool, channel=ch)
    with pytest.raises(RabbitMQChannelError):
        tool._execute(queue="q1")


def test_delete_queue() -> None:
    ch = MagicMock()
    ch.queue_delete.return_value = MagicMock(method=MagicMock(message_count=7))
    tool, _ = _make(DeleteQueueTool, channel=ch)
    out = _parse(tool.invoke({"queue": "q1", "if_unused": True, "if_empty": False}))
    assert out["queue"] == "q1"
    assert out["deleted_messages"] == 7
    ch.queue_delete.assert_called_once_with(queue="q1", if_unused=True, if_empty=False)


def test_purge_queue() -> None:
    ch = MagicMock()
    ch.queue_purge.return_value = MagicMock(method=MagicMock(message_count=10))
    tool, _ = _make(PurgeQueueTool, channel=ch)
    out = _parse(tool.invoke({"queue": "q1"}))
    assert out == {"queue": "q1", "purged_messages": 10}


def test_bind_and_unbind_queue() -> None:
    ch = MagicMock()
    bt, _ = _make(BindQueueTool, channel=ch)
    out = _parse(bt.invoke({"queue": "q", "exchange": "ex", "routing_key": "rk"}))
    assert out["bound"] is True
    ch.queue_bind.assert_called_once_with(
        queue="q", exchange="ex", routing_key="rk", arguments=None
    )

    ut, _ = _make(UnbindQueueTool, channel=ch)
    out = _parse(ut.invoke({"queue": "q", "exchange": "ex", "routing_key": "rk"}))
    assert out["bound"] is False
    ch.queue_unbind.assert_called_once()


def test_get_queue_info_passive() -> None:
    ch = MagicMock()
    ch.queue_declare.return_value = MagicMock(
        method=MagicMock(queue="q1", message_count=0, consumer_count=2)
    )
    tool, _ = _make(GetQueueInfoTool, channel=ch)
    out = _parse(tool.invoke({"queue": "q1"}))
    assert out["consumer_count"] == 2
    args, kwargs = ch.queue_declare.call_args
    assert kwargs.get("passive") is True


# --------------------------------------------------------------------------- #
# Exchange tools
# --------------------------------------------------------------------------- #
def test_declare_exchange_all_types() -> None:
    ch = MagicMock()
    tool, _ = _make(DeclareExchangeTool, channel=ch)
    out = _parse(tool.invoke({"exchange": "ex1", "exchange_type": "topic"}))
    assert out["type"] == "topic"
    ch.exchange_declare.assert_called_once()


def test_delete_exchange() -> None:
    ch = MagicMock()
    tool, _ = _make(DeleteExchangeTool, channel=ch)
    out = _parse(tool.invoke({"exchange": "ex1", "if_unused": True}))
    assert out["deleted"] is True
    ch.exchange_delete.assert_called_once_with(exchange="ex1", if_unused=True)


def test_bind_exchange() -> None:
    ch = MagicMock()
    tool, _ = _make(BindExchangeTool, channel=ch)
    out = _parse(
        tool.invoke({"source": "src", "destination": "dst", "routing_key": "rk"})
    )
    assert out["bound"] is True
    ch.exchange_bind.assert_called_once()


def test_declare_exchange_error() -> None:
    ch = MagicMock()
    ch.exchange_declare.side_effect = pika.exceptions.AMQPError("nope")
    tool, _ = _make(DeclareExchangeTool, channel=ch)
    with pytest.raises(RabbitMQChannelError):
        tool._execute(exchange="ex1")


# --------------------------------------------------------------------------- #
# Message tools
# --------------------------------------------------------------------------- #
def test_publish_message_text() -> None:
    ch = MagicMock()
    tool, _ = _make(PublishMessageTool, channel=ch)
    out = _parse(
        tool.invoke(
            {
                "routing_key": "q1",
                "body": "hello",
                "headers": {"x": "1"},
                "priority": 5,
                "expiration_ms": 1000,
            }
        )
    )
    assert out["published"] is True
    assert out["bytes"] == len(b"hello")
    assert out["content_type"] == "text/plain"
    call = ch.basic_publish.call_args
    props = call.kwargs["properties"]
    assert props.delivery_mode == 2  # persistent default
    assert props.priority == 5
    assert props.expiration == "1000"
    assert props.content_type == "text/plain"


def test_publish_message_json_auto_content_type() -> None:
    ch = MagicMock()
    tool, _ = _make(PublishMessageTool, channel=ch)
    payload = {"a": 1, "b": [1, 2, 3]}
    out = _parse(tool.invoke({"routing_key": "q1", "json_body": payload}))
    assert out["content_type"] == "application/json"
    call = ch.basic_publish.call_args
    assert call.kwargs["body"] == json.dumps(payload, sort_keys=True).encode("utf-8")


def test_publish_message_requires_body_or_json() -> None:
    tool, _ = _make(PublishMessageTool)
    with pytest.raises(RabbitMQMessageError):
        tool._execute(routing_key="q1")


def test_publish_message_unroutable() -> None:
    ch = MagicMock()
    ch.basic_publish.side_effect = pika.exceptions.UnroutableError([])
    tool, _ = _make(PublishMessageTool, channel=ch)
    with pytest.raises(RabbitMQMessageError):
        tool._execute(routing_key="q1", body="x", mandatory=True)


def test_publish_message_persistent_flag_false() -> None:
    ch = MagicMock()
    tool, _ = _make(PublishMessageTool, channel=ch)
    tool._execute(routing_key="q1", body="x", persistent=False)
    props = ch.basic_publish.call_args.kwargs["properties"]
    assert props.delivery_mode == 1


def test_consume_message_serializes_json() -> None:
    ch = MagicMock()
    method = MagicMock(
        delivery_tag=42, redelivered=False, exchange="", routing_key="q1"
    )
    props = pika.BasicProperties(
        content_type="application/json", headers={"h": 1}, delivery_mode=2
    )
    body = json.dumps({"a": 1}).encode("utf-8")
    ch.basic_get.side_effect = [(method, props, body), (None, None, None)]
    tool, _ = _make(ConsumeMessageTool, channel=ch)
    out = _parse(tool.invoke({"queue": "q1", "max_messages": 5}))
    assert out["count"] == 1
    msg = out["messages"][0]
    assert msg["delivery_tag"] == 42
    assert msg["body"] == {"a": 1}
    assert msg["properties"]["headers"] == {"h": 1}


def test_consume_message_handles_text() -> None:
    ch = MagicMock()
    method = MagicMock(delivery_tag=1, redelivered=True, exchange="ex", routing_key="rk")
    props = pika.BasicProperties(content_type="text/plain")
    ch.basic_get.return_value = (method, props, b"hello")
    tool, _ = _make(ConsumeMessageTool, channel=ch)
    out = _parse(tool.invoke({"queue": "q", "max_messages": 1}))
    assert out["messages"][0]["body"] == "hello"
    assert out["messages"][0]["redelivered"] is True


def test_consume_message_handles_binary() -> None:
    ch = MagicMock()
    method = MagicMock(delivery_tag=1, redelivered=False, exchange="", routing_key="q")
    props = pika.BasicProperties()
    ch.basic_get.return_value = (method, props, b"\xff\xfe\xfd")
    tool, _ = _make(ConsumeMessageTool, channel=ch)
    out = _parse(tool.invoke({"queue": "q", "max_messages": 1}))
    assert out["messages"][0]["body"] == "fffefd"
    assert out["messages"][0]["properties"]["content_type"] == "application/octet-stream"


def test_ack_nack_reject() -> None:
    ch = MagicMock()
    ack, _ = _make(AckMessageTool, channel=ch)
    nack, _ = _make(NackMessageTool, channel=ch)
    rej, _ = _make(RejectMessageTool, channel=ch)
    assert _parse(ack.invoke({"delivery_tag": 1}))["acked"] is True
    assert _parse(nack.invoke({"delivery_tag": 2, "requeue": False}))["nacked"] is True
    assert _parse(rej.invoke({"delivery_tag": 3}))["rejected"] is True
    ch.basic_ack.assert_called_once_with(delivery_tag=1, multiple=False)
    ch.basic_nack.assert_called_once_with(delivery_tag=2, multiple=False, requeue=False)
    ch.basic_reject.assert_called_once_with(delivery_tag=3, requeue=False)


def test_ack_error() -> None:
    ch = MagicMock()
    ch.basic_ack.side_effect = pika.exceptions.AMQPError("nope")
    tool, _ = _make(AckMessageTool, channel=ch)
    with pytest.raises(RabbitMQMessageError):
        tool._execute(delivery_tag=1)


# --------------------------------------------------------------------------- #
# Monitoring tools
# --------------------------------------------------------------------------- #
def test_check_health() -> None:
    tool, _ = _make(CheckHealthTool)
    out = _parse(tool.invoke({}))
    assert out["healthy"] is True


def test_get_connection_info_omits_password() -> None:
    tool, _ = _make(GetConnectionInfoTool)
    out = _parse(tool.invoke({}))
    assert "password" not in out
    assert out["host"] == "localhost"
    assert out["username"] == "guest"


def test_close_connection() -> None:
    tool, mgr = _make(CloseConnectionTool)
    out = _parse(tool.invoke({}))
    assert out["closed"] is True
    assert mgr.closed is True


def test_async_run_uses_thread() -> None:
    """The ``_arun`` fallback should still produce JSON results."""
    import asyncio

    ch = MagicMock()
    ch.queue_declare.return_value = MagicMock(
        method=MagicMock(queue="q", message_count=0, consumer_count=0)
    )
    tool, _ = _make(DeclareQueueTool, channel=ch)
    out = asyncio.run(tool.ainvoke({"queue": "q"}))
    assert json.loads(out)["queue"] == "q"


def test_invalid_schema_rejected() -> None:
    """Pydantic v2 strict schemas refuse unknown fields."""
    tool, _ = _make(DeclareQueueTool)
    with pytest.raises(Exception):
        tool.invoke({"queue": "q", "unexpected": True})


def test_manager_property_exposed() -> None:
    tool, mgr = _make(DeclareQueueTool)
    assert tool.manager is mgr  # type: ignore[comparison-overlap]


def test_default_manager_falls_back_to_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Constructing a tool without a manager should not error at construction time."""
    monkeypatch.setenv("RABBITMQ_HOST", "broker.example")
    tool = DeclareQueueTool()
    assert isinstance(tool.manager, SyncConnectionManager)
    assert tool.manager.config.host == "broker.example"
