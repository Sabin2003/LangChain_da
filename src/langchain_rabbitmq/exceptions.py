"""Custom exception hierarchy for langchain-rabbitmq.

All exceptions raised by the tools, utilities and toolkit inherit from
:class:`RabbitMQToolException`. Catching this base class is enough for callers
that want to handle every error originating from the library.
"""

from __future__ import annotations

from typing import Optional


class RabbitMQToolException(Exception):
    """Base class for every exception raised by ``langchain-rabbitmq``."""

    def __init__(self, message: str, *, cause: Optional[BaseException] = None) -> None:
        super().__init__(message)
        self.message = message
        if cause is not None:
            self.__cause__ = cause

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.message


class RabbitMQConnectionError(RabbitMQToolException):
    """Raised when the library cannot establish or maintain a broker connection."""


class RabbitMQChannelError(RabbitMQToolException):
    """Raised for channel-level failures (declare/bind/delete/purge)."""


class RabbitMQMessageError(RabbitMQToolException):
    """Raised when publishing, consuming or acknowledging a message fails."""


class RabbitMQConfigurationError(RabbitMQToolException):
    """Raised when configuration (env vars, URL, TLS) is invalid."""


__all__ = [
    "RabbitMQChannelError",
    "RabbitMQConfigurationError",
    "RabbitMQConnectionError",
    "RabbitMQMessageError",
    "RabbitMQToolException",
]
