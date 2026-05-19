"""Queue management tools."""

from __future__ import annotations

from typing import Any, Optional

import pika.exceptions

from ..exceptions import RabbitMQChannelError
from ..models import (
    DeclareQueueInput,
    DeleteQueueInput,
    PurgeQueueInput,
    QueueBindingInput,
    QueueInfoInput,
)
from .base import BaseRabbitMQTool


class DeclareQueueTool(BaseRabbitMQTool):
    """Declare (create if missing) an AMQP queue."""

    name: str = "rabbitmq_declare_queue"
    description: str = (
        "Declare a RabbitMQ queue. Creates the queue if it does not exist. "
        "Returns the queue name and current message/consumer counts."
    )
    args_schema: type = DeclareQueueInput

    def _execute(
        self,
        *,
        queue: str,
        durable: bool = True,
        exclusive: bool = False,
        auto_delete: bool = False,
        arguments: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        try:
            with self.manager.channel() as ch:
                result = ch.queue_declare(
                    queue=queue,
                    durable=durable,
                    exclusive=exclusive,
                    auto_delete=auto_delete,
                    arguments=arguments,
                )
                return {
                    "queue": result.method.queue,
                    "message_count": result.method.message_count,
                    "consumer_count": result.method.consumer_count,
                }
        except pika.exceptions.AMQPError as exc:
            raise RabbitMQChannelError(
                f"declare_queue failed for {queue!r}: {exc}", cause=exc
            ) from exc


class DeleteQueueTool(BaseRabbitMQTool):
    """Delete an AMQP queue."""

    name: str = "rabbitmq_delete_queue"
    description: str = "Delete a RabbitMQ queue. Optionally only if unused or empty."
    args_schema: type = DeleteQueueInput

    def _execute(
        self, *, queue: str, if_unused: bool = False, if_empty: bool = False
    ) -> dict[str, Any]:
        try:
            with self.manager.channel() as ch:
                result = ch.queue_delete(queue=queue, if_unused=if_unused, if_empty=if_empty)
                return {"queue": queue, "deleted_messages": result.method.message_count}
        except pika.exceptions.AMQPError as exc:
            raise RabbitMQChannelError(
                f"delete_queue failed for {queue!r}: {exc}", cause=exc
            ) from exc


class PurgeQueueTool(BaseRabbitMQTool):
    """Purge all messages from a queue."""

    name: str = "rabbitmq_purge_queue"
    description: str = (
        "Remove all messages from a RabbitMQ queue without deleting the queue itself."
    )
    args_schema: type = PurgeQueueInput

    def _execute(self, *, queue: str) -> dict[str, Any]:
        try:
            with self.manager.channel() as ch:
                result = ch.queue_purge(queue=queue)
                return {"queue": queue, "purged_messages": result.method.message_count}
        except pika.exceptions.AMQPError as exc:
            raise RabbitMQChannelError(
                f"purge_queue failed for {queue!r}: {exc}", cause=exc
            ) from exc


class BindQueueTool(BaseRabbitMQTool):
    """Bind a queue to an exchange with a routing key."""

    name: str = "rabbitmq_bind_queue"
    description: str = "Bind a RabbitMQ queue to an exchange using a routing key."
    args_schema: type = QueueBindingInput

    def _execute(
        self,
        *,
        queue: str,
        exchange: str,
        routing_key: str = "",
        arguments: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        try:
            with self.manager.channel() as ch:
                ch.queue_bind(
                    queue=queue,
                    exchange=exchange,
                    routing_key=routing_key,
                    arguments=arguments,
                )
                return {
                    "queue": queue,
                    "exchange": exchange,
                    "routing_key": routing_key,
                    "bound": True,
                }
        except pika.exceptions.AMQPError as exc:
            raise RabbitMQChannelError(
                f"bind_queue failed for {queue!r}->{exchange!r}: {exc}", cause=exc
            ) from exc


class UnbindQueueTool(BaseRabbitMQTool):
    """Remove a queue-exchange binding."""

    name: str = "rabbitmq_unbind_queue"
    description: str = "Remove a binding between a queue and an exchange."
    args_schema: type = QueueBindingInput

    def _execute(
        self,
        *,
        queue: str,
        exchange: str,
        routing_key: str = "",
        arguments: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        try:
            with self.manager.channel() as ch:
                ch.queue_unbind(
                    queue=queue,
                    exchange=exchange,
                    routing_key=routing_key,
                    arguments=arguments,
                )
                return {
                    "queue": queue,
                    "exchange": exchange,
                    "routing_key": routing_key,
                    "bound": False,
                }
        except pika.exceptions.AMQPError as exc:
            raise RabbitMQChannelError(
                f"unbind_queue failed for {queue!r}->{exchange!r}: {exc}", cause=exc
            ) from exc


class GetQueueInfoTool(BaseRabbitMQTool):
    """Return queue depth and consumer count (passive declare)."""

    name: str = "rabbitmq_get_queue_info"
    description: str = (
        "Return information about an existing queue: message count and consumer count. "
        "Uses a passive declare so it does not modify the queue."
    )
    args_schema: type = QueueInfoInput

    def _execute(self, *, queue: str) -> dict[str, Any]:
        try:
            with self.manager.channel() as ch:
                result = ch.queue_declare(queue=queue, passive=True)
                return {
                    "queue": result.method.queue,
                    "message_count": result.method.message_count,
                    "consumer_count": result.method.consumer_count,
                }
        except pika.exceptions.AMQPError as exc:
            raise RabbitMQChannelError(
                f"get_queue_info failed for {queue!r}: {exc}", cause=exc
            ) from exc


__all__ = [
    "BindQueueTool",
    "DeclareQueueTool",
    "DeleteQueueTool",
    "GetQueueInfoTool",
    "PurgeQueueTool",
    "UnbindQueueTool",
]
