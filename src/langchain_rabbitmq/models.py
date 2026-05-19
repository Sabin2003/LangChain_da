"""Pydantic v2 schemas used as ``args_schema`` for the LangChain tools.

The schemas are intentionally narrow: they validate user/agent input *before*
any network call is made, providing rich docstrings for LLM tool selection and
strict typing for downstream code.
"""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

ExchangeType = Literal["direct", "fanout", "topic", "headers"]
"""AMQP 0-9-1 exchange type."""


class _StrictModel(BaseModel):
    """Base class enforcing strict validation across all tool schemas."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


# --------------------------------------------------------------------------- #
# Queue management
# --------------------------------------------------------------------------- #
class DeclareQueueInput(_StrictModel):
    """Arguments for declaring a queue."""

    queue: str = Field(
        description="Name of the queue. Empty string lets the broker generate one."
    )
    durable: bool = Field(default=True, description="Survive broker restarts.")
    exclusive: bool = Field(
        default=False, description="Restricted to this connection and auto-deleted on close."
    )
    auto_delete: bool = Field(
        default=False, description="Delete the queue when the last consumer disconnects."
    )
    arguments: Optional[dict[str, Any]] = Field(
        default=None,
        description=(
            "Optional AMQP arguments (e.g. x-message-ttl, x-max-length, "
            "x-dead-letter-exchange)."
        ),
    )


class DeleteQueueInput(_StrictModel):
    """Arguments for deleting a queue."""

    queue: str = Field(description="Queue name.")
    if_unused: bool = Field(default=False, description="Only delete if there are no consumers.")
    if_empty: bool = Field(default=False, description="Only delete if the queue has no messages.")


class PurgeQueueInput(_StrictModel):
    """Arguments for purging all messages from a queue."""

    queue: str = Field(description="Queue name.")


class QueueBindingInput(_StrictModel):
    """Arguments for binding or unbinding a queue to an exchange."""

    queue: str = Field(description="Queue name.")
    exchange: str = Field(description="Exchange name.")
    routing_key: str = Field(default="", description="Routing key or topic pattern.")
    arguments: Optional[dict[str, Any]] = Field(
        default=None,
        description="Binding arguments (used for headers exchanges, e.g. x-match=all).",
    )


class QueueInfoInput(_StrictModel):
    """Arguments for inspecting a queue."""

    queue: str = Field(description="Queue name.")


# --------------------------------------------------------------------------- #
# Exchange management
# --------------------------------------------------------------------------- #
class DeclareExchangeInput(_StrictModel):
    """Arguments for declaring an exchange."""

    exchange: str = Field(description="Exchange name.")
    exchange_type: ExchangeType = Field(default="direct", description="AMQP exchange type.")
    durable: bool = Field(default=True, description="Survive broker restarts.")
    auto_delete: bool = Field(
        default=False, description="Delete the exchange when no queues are bound."
    )
    internal: bool = Field(
        default=False, description="Exchange may only be published to by other exchanges."
    )
    arguments: Optional[dict[str, Any]] = Field(default=None, description="Optional arguments.")


class DeleteExchangeInput(_StrictModel):
    """Arguments for deleting an exchange."""

    exchange: str = Field(description="Exchange name.")
    if_unused: bool = Field(
        default=False, description="Only delete if no queues or exchanges are bound."
    )


class ExchangeBindingInput(_StrictModel):
    """Arguments for binding two exchanges (exchange-to-exchange)."""

    source: str = Field(description="Source exchange.")
    destination: str = Field(description="Destination exchange.")
    routing_key: str = Field(default="", description="Routing key or topic pattern.")
    arguments: Optional[dict[str, Any]] = Field(default=None, description="Binding arguments.")


# --------------------------------------------------------------------------- #
# Message operations
# --------------------------------------------------------------------------- #
class PublishMessageInput(_StrictModel):
    """Arguments for publishing a message.

    Provide *either* ``body`` (text) *or* ``json_body`` (structured data) –
    if both are supplied, ``json_body`` wins and ``content_type`` defaults
    to ``application/json``.
    """

    exchange: str = Field(default="", description="Exchange name. Use '' for the default exchange.")
    routing_key: str = Field(description="Routing key (or queue name on default exchange).")
    body: Optional[str] = Field(default=None, description="Plain text payload.")
    json_body: Optional[Any] = Field(
        default=None, description="JSON-serializable payload (dict, list, scalar)."
    )
    headers: Optional[dict[str, Any]] = Field(default=None, description="Custom message headers.")
    content_type: Optional[str] = Field(
        default=None, description="MIME content-type (auto-detected when omitted)."
    )
    content_encoding: Optional[str] = Field(default=None, description="Content encoding.")
    persistent: bool = Field(default=True, description="If True, delivery_mode=2 (persistent).")
    priority: Optional[int] = Field(
        default=None, ge=0, le=255, description="Message priority (0-255). Queue must support it."
    )
    expiration_ms: Optional[int] = Field(
        default=None, ge=0, description="Per-message TTL in milliseconds."
    )
    message_id: Optional[str] = Field(default=None, description="Application message identifier.")
    correlation_id: Optional[str] = Field(default=None, description="Correlation identifier.")
    reply_to: Optional[str] = Field(default=None, description="Reply-to queue for RPC.")
    mandatory: bool = Field(
        default=False, description="Return message to publisher if it cannot be routed."
    )

    @field_validator("routing_key")
    @classmethod
    def _validate_routing_key(cls, value: str) -> str:
        # An empty routing key is valid for fanout exchanges, so we don't enforce non-empty.
        return value


class ConsumeMessageInput(_StrictModel):
    """Arguments for synchronously fetching messages from a queue.

    This uses ``basic_get`` semantics (poll-based) so it is safe for use in a
    tool call. For streaming consumption, use the async ``aio-pika`` API
    directly.
    """

    queue: str = Field(description="Queue name.")
    max_messages: int = Field(
        default=1, ge=1, le=1000, description="Maximum number of messages to fetch."
    )
    auto_ack: bool = Field(
        default=True, description="Automatically acknowledge messages once fetched."
    )
    timeout: float = Field(
        default=1.0, gt=0, description="Per-message wait timeout in seconds."
    )


class AckMessageInput(_StrictModel):
    """Arguments for acknowledging a previously fetched message."""

    delivery_tag: int = Field(ge=0, description="Delivery tag returned by consume.")
    multiple: bool = Field(
        default=False, description="Ack all messages up to and including the delivery_tag."
    )


class NackMessageInput(_StrictModel):
    """Arguments for negatively acknowledging a message."""

    delivery_tag: int = Field(ge=0, description="Delivery tag returned by consume.")
    multiple: bool = Field(default=False, description="Nack all messages up to delivery_tag.")
    requeue: bool = Field(default=True, description="Requeue the message instead of dropping it.")


class RejectMessageInput(_StrictModel):
    """Arguments for rejecting a message."""

    delivery_tag: int = Field(ge=0, description="Delivery tag returned by consume.")
    requeue: bool = Field(default=False, description="Requeue the message instead of dropping it.")


# --------------------------------------------------------------------------- #
# Monitoring
# --------------------------------------------------------------------------- #
class EmptyInput(_StrictModel):
    """Used by tools that take no arguments."""


class ListResourceInput(_StrictModel):
    """Arguments for listing resources (queues, exchanges, bindings) via the HTTP API."""

    vhost: Optional[str] = Field(
        default=None, description="Filter to a specific virtual host. Defaults to all."
    )


__all__ = [
    "AckMessageInput",
    "ConsumeMessageInput",
    "DeclareExchangeInput",
    "DeclareQueueInput",
    "DeleteExchangeInput",
    "DeleteQueueInput",
    "EmptyInput",
    "ExchangeBindingInput",
    "ExchangeType",
    "ListResourceInput",
    "NackMessageInput",
    "PublishMessageInput",
    "PurgeQueueInput",
    "QueueBindingInput",
    "QueueInfoInput",
    "RejectMessageInput",
]
