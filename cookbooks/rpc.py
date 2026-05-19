"""Cookbook: RPC over RabbitMQ using ``correlation_id`` + ``reply_to``.

A *client* publishes a request to ``rpc.requests`` and expects a response on a
temporary, exclusive ``reply_to`` queue. A *server* loop consumes requests and
publishes responses to ``reply_to`` with a matching ``correlation_id``.

This cookbook uses the synchronous tools and a small custom loop to keep the
example self-contained.

Run::

    python cookbooks/rpc.py
"""

from __future__ import annotations

import json
import threading
import time
import uuid

from langchain_rabbitmq import (
    ConsumeMessageTool,
    DeclareQueueTool,
    DeleteQueueTool,
    PublishMessageTool,
    RabbitMQConfig,
)

REQUEST_QUEUE = "rpc.requests"


def run_server(cfg: RabbitMQConfig, stop: threading.Event) -> None:
    DeclareQueueTool(config=cfg).invoke({"queue": REQUEST_QUEUE, "durable": False})
    consume = ConsumeMessageTool(config=cfg)
    publish = PublishMessageTool(config=cfg)
    while not stop.is_set():
        batch = json.loads(
            consume.invoke({"queue": REQUEST_QUEUE, "max_messages": 1, "auto_ack": True})
        )
        if batch["count"] == 0:
            time.sleep(0.05)
            continue
        msg = batch["messages"][0]
        reply_to = msg["properties"]["reply_to"]
        corr = msg["properties"]["correlation_id"]
        if reply_to is None or corr is None:
            continue
        # Compute the "service" response.
        n = int(msg["body"]) if isinstance(msg["body"], str) else int(msg["body"])
        publish.invoke(
            {
                "routing_key": reply_to,
                "json_body": {"result": n * n},
                "correlation_id": corr,
                "persistent": False,
            }
        )


def call(cfg: RabbitMQConfig, number: int) -> dict[str, object]:
    reply_queue = f"rpc.reply.{uuid.uuid4().hex[:8]}"
    DeclareQueueTool(config=cfg).invoke(
        {"queue": reply_queue, "durable": False, "auto_delete": True}
    )
    correlation_id = uuid.uuid4().hex
    PublishMessageTool(config=cfg).invoke(
        {
            "routing_key": REQUEST_QUEUE,
            "body": str(number),
            "correlation_id": correlation_id,
            "reply_to": reply_queue,
            "persistent": False,
        }
    )
    consume = ConsumeMessageTool(config=cfg)
    deadline = time.time() + 5.0
    while time.time() < deadline:
        batch = json.loads(
            consume.invoke({"queue": reply_queue, "max_messages": 1, "auto_ack": True})
        )
        if batch["count"]:
            DeleteQueueTool(config=cfg).invoke({"queue": reply_queue})
            return batch["messages"][0]["body"]
        time.sleep(0.05)
    DeleteQueueTool(config=cfg).invoke({"queue": reply_queue})
    raise TimeoutError("RPC call timed out")


def main() -> None:
    cfg = RabbitMQConfig.from_env()
    stop = threading.Event()
    server = threading.Thread(target=run_server, args=(cfg, stop), daemon=True)
    server.start()
    try:
        for n in [3, 4, 5]:
            print(f"{n} -> {call(cfg, n)}")
    finally:
        stop.set()
        server.join(timeout=2)
        DeleteQueueTool(config=cfg).invoke({"queue": REQUEST_QUEUE})


if __name__ == "__main__":
    main()
