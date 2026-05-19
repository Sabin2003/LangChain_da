"""Load test: publish and consume 1000 messages end-to-end."""

from __future__ import annotations

import json
import time
import uuid

import pytest

from langchain_rabbitmq import (
    ConsumeMessageTool,
    DeclareQueueTool,
    DeleteQueueTool,
    PublishMessageTool,
    RabbitMQConfig,
)

pytestmark = [pytest.mark.load, pytest.mark.usefixtures("rabbitmq_env")]

MESSAGE_COUNT = 1000


def test_publish_and_consume_1000_messages() -> None:
    cfg = RabbitMQConfig.from_env()
    q = f"load-{uuid.uuid4().hex[:8]}"
    DeclareQueueTool(config=cfg).invoke({"queue": q, "durable": False})

    publisher = PublishMessageTool(config=cfg)
    consumer = ConsumeMessageTool(config=cfg)

    t0 = time.perf_counter()
    for i in range(MESSAGE_COUNT):
        publisher.invoke(
            {"routing_key": q, "json_body": {"i": i}, "persistent": False}
        )
    publish_elapsed = time.perf_counter() - t0

    t1 = time.perf_counter()
    received = 0
    while received < MESSAGE_COUNT:
        batch = json.loads(
            consumer.invoke(
                {"queue": q, "max_messages": min(100, MESSAGE_COUNT - received)}
            )
        )
        if batch["count"] == 0:
            break
        received += batch["count"]
    consume_elapsed = time.perf_counter() - t1

    DeleteQueueTool(config=cfg).invoke({"queue": q})

    assert received == MESSAGE_COUNT, f"Expected {MESSAGE_COUNT} got {received}"
    # Sanity: at least 50 msgs/sec each way on any non-pathological broker.
    assert publish_elapsed < MESSAGE_COUNT / 50
    assert consume_elapsed < MESSAGE_COUNT / 50
