"""Cookbook: async publish + consume against RabbitMQ via aio-pika.

This example does not involve an LLM — it demonstrates how to use the async
tools (and their underlying :class:`AsyncConnectionManager`) directly.

Run with::

    python cookbooks/async_agent.py
"""

from __future__ import annotations

import asyncio
import json

from langchain_rabbitmq import (
    AsyncConnectionManager,
    AsyncPublishMessageTool,
    ConsumeMessageTool,
    DeclareQueueTool,
    DeleteQueueTool,
    RabbitMQConfig,
)


async def main() -> None:
    cfg = RabbitMQConfig.from_env()
    queue = "cookbook.async"

    DeclareQueueTool(config=cfg).invoke({"queue": queue, "durable": False})

    async_mgr = AsyncConnectionManager(cfg)
    publisher = AsyncPublishMessageTool(manager=async_mgr)
    try:
        for i in range(10):
            await publisher.ainvoke(
                {
                    "routing_key": queue,
                    "json_body": {"i": i},
                    "persistent": False,
                }
            )
        out = json.loads(
            ConsumeMessageTool(config=cfg).invoke(
                {"queue": queue, "max_messages": 10, "auto_ack": True}
            )
        )
        print("Received:", [m["body"] for m in out["messages"]])
    finally:
        await async_mgr.close()
        DeleteQueueTool(config=cfg).invoke({"queue": queue})


if __name__ == "__main__":
    asyncio.run(main())
