"""Cookbook: topic-exchange routing.

Demonstrates how an agent (or a human operator using the tools directly) can
fan-out messages from a single producer to multiple specialised queues using a
``topic`` exchange and pattern routing keys.

Run::

    python cookbooks/routing.py
"""

from __future__ import annotations

import json

from langchain_rabbitmq import (
    ConsumeMessageTool,
    DeclareExchangeTool,
    DeclareQueueTool,
    DeleteExchangeTool,
    DeleteQueueTool,
    PublishMessageTool,
    RabbitMQConfig,
    RabbitMQToolkit,
)

EXCHANGE = "logs.topic"


def main() -> None:
    cfg = RabbitMQConfig.from_env()
    tk = RabbitMQToolkit(config=cfg, include_async=False)
    bind = next(t for t in tk.get_tools() if t.name == "rabbitmq_bind_queue")

    DeclareExchangeTool(config=cfg).invoke(
        {"exchange": EXCHANGE, "exchange_type": "topic", "durable": False}
    )

    queues = {
        "logs.errors": "*.error",
        "logs.kern": "kern.*",
        "logs.all": "#",
    }
    for q, pattern in queues.items():
        DeclareQueueTool(config=cfg).invoke({"queue": q, "durable": False})
        bind.invoke({"queue": q, "exchange": EXCHANGE, "routing_key": pattern})

    publisher = PublishMessageTool(config=cfg)
    events = [
        ("kern.info", "system booted"),
        ("kern.error", "kernel panic"),
        ("auth.error", "invalid password"),
        ("auth.info", "user logged in"),
    ]
    for rk, body in events:
        publisher.invoke(
            {"exchange": EXCHANGE, "routing_key": rk, "body": body, "persistent": False}
        )

    consumer = ConsumeMessageTool(config=cfg)
    for q in queues:
        out = json.loads(consumer.invoke({"queue": q, "max_messages": 10, "auto_ack": True}))
        bodies = [m["body"] for m in out["messages"]]
        print(f"{q:<14}  {bodies}")

    for q in queues:
        DeleteQueueTool(config=cfg).invoke({"queue": q})
    DeleteExchangeTool(config=cfg).invoke({"exchange": EXCHANGE})


if __name__ == "__main__":
    main()
