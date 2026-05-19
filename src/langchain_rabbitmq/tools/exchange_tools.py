"""Exchange management tools."""

from __future__ import annotations

from typing import Any, Optional

import pika.exceptions

from ..exceptions import RabbitMQChannelError
from ..models import (
    DeclareExchangeInput,
    DeleteExchangeInput,
    ExchangeBindingInput,
    ExchangeType,
)
from .base import BaseRabbitMQTool


class DeclareExchangeTool(BaseRabbitMQTool):
    """Declare (create if missing) an AMQP exchange."""

    name: str = "rabbitmq_declare_exchange"
    description: str = (
        "Declare a RabbitMQ exchange (direct, fanout, topic or headers). "
        "Creates the exchange if it does not exist."
    )
    args_schema: type = DeclareExchangeInput

    def _execute(
        self,
        *,
        exchange: str,
        exchange_type: ExchangeType = "direct",
        durable: bool = True,
        auto_delete: bool = False,
        internal: bool = False,
        arguments: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        try:
            with self.manager.channel() as ch:
                ch.exchange_declare(
                    exchange=exchange,
                    exchange_type=exchange_type,
                    durable=durable,
                    auto_delete=auto_delete,
                    internal=internal,
                    arguments=arguments,
                )
                return {
                    "exchange": exchange,
                    "type": exchange_type,
                    "durable": durable,
                    "auto_delete": auto_delete,
                    "internal": internal,
                }
        except pika.exceptions.AMQPError as exc:
            raise RabbitMQChannelError(
                f"declare_exchange failed for {exchange!r}: {exc}", cause=exc
            ) from exc


class DeleteExchangeTool(BaseRabbitMQTool):
    """Delete an AMQP exchange."""

    name: str = "rabbitmq_delete_exchange"
    description: str = "Delete a RabbitMQ exchange. Optionally only if unused."
    args_schema: type = DeleteExchangeInput

    def _execute(self, *, exchange: str, if_unused: bool = False) -> dict[str, Any]:
        try:
            with self.manager.channel() as ch:
                ch.exchange_delete(exchange=exchange, if_unused=if_unused)
                return {"exchange": exchange, "deleted": True}
        except pika.exceptions.AMQPError as exc:
            raise RabbitMQChannelError(
                f"delete_exchange failed for {exchange!r}: {exc}", cause=exc
            ) from exc


class BindExchangeTool(BaseRabbitMQTool):
    """Bind two exchanges (source -> destination)."""

    name: str = "rabbitmq_bind_exchange"
    description: str = (
        "Bind two RabbitMQ exchanges so that messages routed to the source exchange "
        "are also routed to the destination exchange."
    )
    args_schema: type = ExchangeBindingInput

    def _execute(
        self,
        *,
        source: str,
        destination: str,
        routing_key: str = "",
        arguments: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        try:
            with self.manager.channel() as ch:
                ch.exchange_bind(
                    source=source,
                    destination=destination,
                    routing_key=routing_key,
                    arguments=arguments,
                )
                return {
                    "source": source,
                    "destination": destination,
                    "routing_key": routing_key,
                    "bound": True,
                }
        except pika.exceptions.AMQPError as exc:
            raise RabbitMQChannelError(
                f"bind_exchange failed for {source!r}->{destination!r}: {exc}", cause=exc
            ) from exc


__all__ = ["BindExchangeTool", "DeclareExchangeTool", "DeleteExchangeTool"]
