"""Integration tests against a real RabbitMQ broker (``rabbitmq:3-management``).

These tests are skipped when Docker is unavailable. Mark with ``-m integration``
to run only this suite.
"""

from __future__ import annotations

import json
import uuid

import pytest

from langchain_rabbitmq import (
    AckMessageTool,
    CheckHealthTool,
    ConsumeMessageTool,
    DeclareExchangeTool,
    DeclareQueueTool,
    DeleteExchangeTool,
    DeleteQueueTool,
    GetQueueInfoTool,
    ListQueuesTool,
    PublishMessageTool,
    PurgeQueueTool,
    RabbitMQConfig,
    RabbitMQToolkit,
)

pytestmark = [pytest.mark.integration, pytest.mark.usefixtures("rabbitmq_env")]


def _qname() -> str:
    return f"itq-{uuid.uuid4().hex[:8]}"


def _exname() -> str:
    return f"itex-{uuid.uuid4().hex[:8]}"


def test_health_against_real_broker() -> None:
    tool = CheckHealthTool(config=RabbitMQConfig.from_env())
    out = json.loads(tool.invoke({}))
    assert out["healthy"] is True


def test_declare_publish_consume_ack() -> None:
    cfg = RabbitMQConfig.from_env()
    q = _qname()

    DeclareQueueTool(config=cfg).invoke({"queue": q, "durable": False})
    PublishMessageTool(config=cfg).invoke(
        {"routing_key": q, "json_body": {"value": 42}, "persistent": False}
    )
    info = json.loads(GetQueueInfoTool(config=cfg).invoke({"queue": q}))
    assert info["message_count"] == 1

    msg = json.loads(
        ConsumeMessageTool(config=cfg).invoke(
            {"queue": q, "max_messages": 1, "auto_ack": False}
        )
    )
    assert msg["count"] == 1
    assert msg["messages"][0]["body"] == {"value": 42}

    AckMessageTool(config=cfg).invoke(
        {"delivery_tag": msg["messages"][0]["delivery_tag"]}
    )

    info_after = json.loads(GetQueueInfoTool(config=cfg).invoke({"queue": q}))
    assert info_after["message_count"] == 0

    DeleteQueueTool(config=cfg).invoke({"queue": q})


def test_purge_queue() -> None:
    cfg = RabbitMQConfig.from_env()
    q = _qname()
    DeclareQueueTool(config=cfg).invoke({"queue": q, "durable": False})
    for i in range(5):
        PublishMessageTool(config=cfg).invoke(
            {"routing_key": q, "body": f"m{i}", "persistent": False}
        )
    purged = json.loads(PurgeQueueTool(config=cfg).invoke({"queue": q}))
    assert purged["purged_messages"] == 5
    DeleteQueueTool(config=cfg).invoke({"queue": q})


def test_exchange_routing_topic() -> None:
    cfg = RabbitMQConfig.from_env()
    ex = _exname()
    q = _qname()
    DeclareExchangeTool(config=cfg).invoke({"exchange": ex, "exchange_type": "topic"})
    DeclareQueueTool(config=cfg).invoke({"queue": q, "durable": False})
    # Bind via the toolkit's BindQueueTool through the toolkit factory.
    tk = RabbitMQToolkit(config=cfg, include_async=False)
    bind = next(t for t in tk.get_tools() if t.name == "rabbitmq_bind_queue")
    bind.invoke({"queue": q, "exchange": ex, "routing_key": "events.*"})

    PublishMessageTool(config=cfg).invoke(
        {"exchange": ex, "routing_key": "events.created", "body": "hi"}
    )
    out = json.loads(
        ConsumeMessageTool(config=cfg).invoke(
            {"queue": q, "max_messages": 1, "auto_ack": True}
        )
    )
    assert out["count"] == 1
    assert out["messages"][0]["routing_key"] == "events.created"

    DeleteQueueTool(config=cfg).invoke({"queue": q})
    DeleteExchangeTool(config=cfg).invoke({"exchange": ex})


def test_list_queues_via_management_api() -> None:
    cfg = RabbitMQConfig.from_env()
    q = _qname()
    DeclareQueueTool(config=cfg).invoke({"queue": q, "durable": False})
    out = json.loads(ListQueuesTool(config=cfg).invoke({}))
    names = {item["name"] for item in out["queues"]}
    assert q in names
    DeleteQueueTool(config=cfg).invoke({"queue": q})
