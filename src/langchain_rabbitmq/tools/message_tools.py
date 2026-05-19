"""Message publish / consume / ack tools (sync + async)."""

from __future__ import annotations

import json
from typing import Any, Optional

import pika
import pika.exceptions

from ..exceptions import RabbitMQMessageError
from ..models import (
    AckMessageInput,
    ConsumeMessageInput,
    NackMessageInput,
    PublishMessageInput,
    RejectMessageInput,
)
from .base import BaseAsyncRabbitMQTool, BaseRabbitMQTool

# --------------------------------------------------------------------------- #
# Helpers shared between sync & async publishers.
# --------------------------------------------------------------------------- #
_PERSISTENT = 2
_TRANSIENT = 1


def _serialize_payload(
    body: Optional[str],
    json_body: Optional[Any],
    content_type: Optional[str],
) -> tuple[bytes, str]:
    """Return ``(payload_bytes, content_type)`` from publish inputs."""

    if json_body is not None:
        encoded = json.dumps(json_body, ensure_ascii=False, sort_keys=True).encode("utf-8")
        return encoded, content_type or "application/json"
    if body is None:
        raise RabbitMQMessageError(
            "publish_message requires either 'body' or 'json_body'."
        )
    return body.encode("utf-8"), content_type or "text/plain"


# --------------------------------------------------------------------------- #
# Synchronous tools
# --------------------------------------------------------------------------- #
class PublishMessageTool(BaseRabbitMQTool):
    """Publish a single message to an exchange."""

    name: str = "rabbitmq_publish_message"
    description: str = (
        "Publish a message to a RabbitMQ exchange with a routing key. "
        "Supports text or JSON payloads, headers, TTL, priority, persistence, "
        "and other AMQP basic properties."
    )
    args_schema: type = PublishMessageInput

    def _execute(
        self,
        *,
        exchange: str = "",
        routing_key: str,
        body: Optional[str] = None,
        json_body: Optional[Any] = None,
        headers: Optional[dict[str, Any]] = None,
        content_type: Optional[str] = None,
        content_encoding: Optional[str] = None,
        persistent: bool = True,
        priority: Optional[int] = None,
        expiration_ms: Optional[int] = None,
        message_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
        reply_to: Optional[str] = None,
        mandatory: bool = False,
    ) -> dict[str, Any]:
        payload, ct = _serialize_payload(body, json_body, content_type)
        props = pika.BasicProperties(
            content_type=ct,
            content_encoding=content_encoding,
            headers=headers,
            delivery_mode=_PERSISTENT if persistent else _TRANSIENT,
            priority=priority,
            expiration=str(expiration_ms) if expiration_ms is not None else None,
            message_id=message_id,
            correlation_id=correlation_id,
            reply_to=reply_to,
        )
        try:
            with self.manager.channel() as ch:
                if mandatory:
                    ch.confirm_delivery()
                ch.basic_publish(
                    exchange=exchange,
                    routing_key=routing_key,
                    body=payload,
                    properties=props,
                    mandatory=mandatory,
                )
                return {
                    "published": True,
                    "exchange": exchange,
                    "routing_key": routing_key,
                    "bytes": len(payload),
                    "content_type": ct,
                }
        except pika.exceptions.UnroutableError as exc:
            raise RabbitMQMessageError(
                f"Message was unroutable for {exchange!r}/{routing_key!r}", cause=exc
            ) from exc
        except pika.exceptions.AMQPError as exc:
            raise RabbitMQMessageError(
                f"publish_message failed: {exc}", cause=exc
            ) from exc


class ConsumeMessageTool(BaseRabbitMQTool):
    """Poll a queue for up to N messages and return them."""

    name: str = "rabbitmq_consume_message"
    description: str = (
        "Fetch up to N messages from a RabbitMQ queue. Returns a list of "
        "{delivery_tag, properties, body} dictionaries. Use auto_ack=False "
        "to acknowledge manually via the ack/nack/reject tools."
    )
    args_schema: type = ConsumeMessageInput

    def _execute(
        self,
        *,
        queue: str,
        max_messages: int = 1,
        auto_ack: bool = True,
        timeout: float = 1.0,
    ) -> dict[str, Any]:
        del timeout  # basic_get is non-blocking; kept for schema compatibility
        messages: list[dict[str, Any]] = []
        try:
            with self.manager.channel() as ch:
                for _ in range(max_messages):
                    method, props, body = ch.basic_get(queue=queue, auto_ack=auto_ack)
                    if method is None:
                        break
                    messages.append(_serialize_message(method, props, body))
        except pika.exceptions.AMQPError as exc:
            raise RabbitMQMessageError(
                f"consume_message failed for {queue!r}: {exc}", cause=exc
            ) from exc
        return {"queue": queue, "count": len(messages), "messages": messages}


def _serialize_message(method: Any, props: Any, body: bytes) -> dict[str, Any]:
    decoded_body: Any
    content_type = getattr(props, "content_type", None)
    try:
        text = body.decode("utf-8")
    except UnicodeDecodeError:
        text = body.hex()
        content_type = content_type or "application/octet-stream"
    if content_type == "application/json":
        try:
            decoded_body = json.loads(text)
        except json.JSONDecodeError:
            decoded_body = text
    else:
        decoded_body = text
    return {
        "delivery_tag": method.delivery_tag,
        "redelivered": bool(method.redelivered),
        "exchange": method.exchange,
        "routing_key": method.routing_key,
        "properties": {
            "content_type": content_type,
            "content_encoding": getattr(props, "content_encoding", None),
            "headers": getattr(props, "headers", None),
            "delivery_mode": getattr(props, "delivery_mode", None),
            "priority": getattr(props, "priority", None),
            "correlation_id": getattr(props, "correlation_id", None),
            "reply_to": getattr(props, "reply_to", None),
            "expiration": getattr(props, "expiration", None),
            "message_id": getattr(props, "message_id", None),
            "timestamp": getattr(props, "timestamp", None),
        },
        "body": decoded_body,
    }


class AckMessageTool(BaseRabbitMQTool):
    """Acknowledge a previously consumed message."""

    name: str = "rabbitmq_ack_message"
    description: str = "Acknowledge a message by its delivery tag."
    args_schema: type = AckMessageInput

    def _execute(self, *, delivery_tag: int, multiple: bool = False) -> dict[str, Any]:
        try:
            with self.manager.channel() as ch:
                ch.basic_ack(delivery_tag=delivery_tag, multiple=multiple)
                return {"acked": True, "delivery_tag": delivery_tag, "multiple": multiple}
        except pika.exceptions.AMQPError as exc:
            raise RabbitMQMessageError(f"ack_message failed: {exc}", cause=exc) from exc


class NackMessageTool(BaseRabbitMQTool):
    """Negatively acknowledge a message (optionally requeue)."""

    name: str = "rabbitmq_nack_message"
    description: str = "Negatively acknowledge a message, optionally requeuing it."
    args_schema: type = NackMessageInput

    def _execute(
        self, *, delivery_tag: int, multiple: bool = False, requeue: bool = True
    ) -> dict[str, Any]:
        try:
            with self.manager.channel() as ch:
                ch.basic_nack(
                    delivery_tag=delivery_tag, multiple=multiple, requeue=requeue
                )
                return {
                    "nacked": True,
                    "delivery_tag": delivery_tag,
                    "multiple": multiple,
                    "requeue": requeue,
                }
        except pika.exceptions.AMQPError as exc:
            raise RabbitMQMessageError(f"nack_message failed: {exc}", cause=exc) from exc


class RejectMessageTool(BaseRabbitMQTool):
    """Reject a single message."""

    name: str = "rabbitmq_reject_message"
    description: str = "Reject a single message, optionally requeuing it."
    args_schema: type = RejectMessageInput

    def _execute(self, *, delivery_tag: int, requeue: bool = False) -> dict[str, Any]:
        try:
            with self.manager.channel() as ch:
                ch.basic_reject(delivery_tag=delivery_tag, requeue=requeue)
                return {
                    "rejected": True,
                    "delivery_tag": delivery_tag,
                    "requeue": requeue,
                }
        except pika.exceptions.AMQPError as exc:
            raise RabbitMQMessageError(f"reject_message failed: {exc}", cause=exc) from exc


# --------------------------------------------------------------------------- #
# Asynchronous tools (aio-pika)
# --------------------------------------------------------------------------- #
class AsyncPublishMessageTool(BaseAsyncRabbitMQTool):
    """Async variant of :class:`PublishMessageTool` using ``aio-pika``."""

    name: str = "rabbitmq_publish_message_async"
    description: str = "Asynchronously publish a message to a RabbitMQ exchange."
    args_schema: type = PublishMessageInput

    async def _aexecute(
        self,
        *,
        exchange: str = "",
        routing_key: str,
        body: Optional[str] = None,
        json_body: Optional[Any] = None,
        headers: Optional[dict[str, Any]] = None,
        content_type: Optional[str] = None,
        content_encoding: Optional[str] = None,
        persistent: bool = True,
        priority: Optional[int] = None,
        expiration_ms: Optional[int] = None,
        message_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
        reply_to: Optional[str] = None,
        mandatory: bool = False,
    ) -> dict[str, Any]:
        import aio_pika
        from aio_pika.exceptions import AMQPError as AioAMQPError

        payload, ct = _serialize_payload(body, json_body, content_type)
        try:
            channel = await self.async_manager.channel()
            try:
                if exchange == "":
                    target = channel.default_exchange
                else:
                    target = await channel.get_exchange(exchange, ensure=True)
                message = aio_pika.Message(
                    body=payload,
                    headers=headers,
                    content_type=ct,
                    content_encoding=content_encoding,
                    delivery_mode=(
                        aio_pika.DeliveryMode.PERSISTENT
                        if persistent
                        else aio_pika.DeliveryMode.NOT_PERSISTENT
                    ),
                    priority=priority,
                    expiration=(expiration_ms / 1000.0) if expiration_ms is not None else None,
                    message_id=message_id,
                    correlation_id=correlation_id,
                    reply_to=reply_to,
                )
                await target.publish(message, routing_key=routing_key, mandatory=mandatory)
                return {
                    "published": True,
                    "exchange": exchange,
                    "routing_key": routing_key,
                    "bytes": len(payload),
                    "content_type": ct,
                }
            finally:
                await channel.close()
        except AioAMQPError as exc:
            raise RabbitMQMessageError(
                f"async publish_message failed: {exc}", cause=exc
            ) from exc


__all__ = [
    "AckMessageTool",
    "AsyncPublishMessageTool",
    "ConsumeMessageTool",
    "NackMessageTool",
    "PublishMessageTool",
    "RejectMessageTool",
]
