"""Connection management utilities.

Two managers are provided:

* :class:`SyncConnectionManager` – wraps :mod:`pika.BlockingConnection`.
* :class:`AsyncConnectionManager` – wraps :mod:`aio_pika`.

Both managers:

* read configuration from :class:`~langchain_rabbitmq.config.RabbitMQConfig`,
* enforce ``connection_timeout`` and ``heartbeat``,
* honour TLS settings via :meth:`RabbitMQConfig.build_ssl_context`,
* re-raise broker errors as :class:`~langchain_rabbitmq.exceptions.RabbitMQConnectionError`
  / :class:`~langchain_rabbitmq.exceptions.RabbitMQChannelError`,
* expose context-manager / async-context-manager APIs for deterministic cleanup,
* retry transient failures with :mod:`tenacity` (exponential backoff, 3 attempts).
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from contextlib import contextmanager
from types import TracebackType
from typing import (
    TYPE_CHECKING,
    Optional,
)

import pika
import pika.exceptions
from pika.adapters.blocking_connection import BlockingChannel, BlockingConnection
from tenacity import (
    AsyncRetrying,
    Retrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from .config import RabbitMQConfig
from .exceptions import RabbitMQChannelError, RabbitMQConnectionError

if TYPE_CHECKING:  # pragma: no cover - typing only
    from aio_pika.abc import AbstractRobustChannel, AbstractRobustConnection

logger = logging.getLogger("langchain_rabbitmq")

_RETRYABLE_PIKA = (
    pika.exceptions.AMQPConnectionError,
    pika.exceptions.ConnectionClosedByBroker,
    pika.exceptions.StreamLostError,
)


def _sync_retry() -> Retrying:
    return Retrying(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=0.2, min=0.2, max=2.0),
        retry=retry_if_exception_type(_RETRYABLE_PIKA),
        reraise=True,
    )


def _async_retry(exc_types: tuple[type[BaseException], ...]) -> AsyncRetrying:
    return AsyncRetrying(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=0.2, min=0.2, max=2.0),
        retry=retry_if_exception_type(exc_types),
        reraise=True,
    )


# --------------------------------------------------------------------------- #
# Sync (pika.BlockingConnection)
# --------------------------------------------------------------------------- #
class SyncConnectionManager:
    """Lazy, lifecycle-managed wrapper around ``pika.BlockingConnection``.

    The connection is established on first use and re-used across calls.
    Use :meth:`channel` (a context manager) to get a fresh channel, which is
    always closed even when an exception propagates.
    """

    def __init__(self, config: RabbitMQConfig) -> None:
        self._config = config
        self._connection: Optional[BlockingConnection] = None

    # -- lifecycle --------------------------------------------------------- #
    @property
    def config(self) -> RabbitMQConfig:
        return self._config

    def is_open(self) -> bool:
        return self._connection is not None and self._connection.is_open

    def connect(self) -> BlockingConnection:
        """Open (or return an existing) :class:`pika.BlockingConnection`."""

        if self.is_open():
            assert self._connection is not None  # for type checkers
            return self._connection

        ssl_options: Optional[pika.SSLOptions] = None
        ssl_ctx = self._config.build_ssl_context()
        if ssl_ctx is not None:
            ssl_options = pika.SSLOptions(ssl_ctx, server_hostname=self._config.host)

        params = pika.ConnectionParameters(
            host=self._config.host,
            port=self._config.port,
            virtual_host=self._config.virtual_host,
            credentials=pika.PlainCredentials(
                self._config.username, self._config.password
            ),
            ssl_options=ssl_options,
            heartbeat=self._config.heartbeat,
            blocked_connection_timeout=self._config.connection_timeout,
            socket_timeout=self._config.connection_timeout,
        )
        # The URL override path: build params from URL if provided.
        if self._config.url_override:
            try:
                params = pika.URLParameters(self._config.url_override)
                params.heartbeat = self._config.heartbeat
                params.socket_timeout = self._config.connection_timeout
                if ssl_options is not None:
                    params.ssl_options = ssl_options
            except Exception as exc:  # pragma: no cover - defensive
                raise RabbitMQConnectionError(
                    f"Invalid RABBITMQ_URL: {exc}", cause=exc
                ) from exc

        try:
            for attempt in _sync_retry():
                with attempt:
                    self._connection = BlockingConnection(params)
        except pika.exceptions.AMQPError as exc:
            raise RabbitMQConnectionError(
                f"Unable to connect to RabbitMQ at {self._config.host}:{self._config.port}: {exc}",
                cause=exc,
            ) from exc
        assert self._connection is not None
        return self._connection

    @contextmanager
    def channel(self) -> Iterator[BlockingChannel]:
        """Yield a fresh AMQP channel and close it deterministically."""

        conn = self.connect()
        try:
            ch = conn.channel()
        except pika.exceptions.AMQPError as exc:
            raise RabbitMQChannelError(
                f"Could not open channel: {exc}", cause=exc
            ) from exc
        try:
            yield ch
        finally:
            try:
                if ch.is_open:
                    ch.close()
            except pika.exceptions.AMQPError:
                logger.debug("Ignoring error while closing channel", exc_info=True)

    def close(self) -> None:
        """Close the underlying connection if open."""

        if self._connection is not None and self._connection.is_open:
            try:
                self._connection.close()
            except pika.exceptions.AMQPError:
                logger.debug("Ignoring error while closing connection", exc_info=True)
        self._connection = None

    # -- context manager protocol ----------------------------------------- #
    def __enter__(self) -> SyncConnectionManager:
        self.connect()
        return self

    def __exit__(
        self,
        exc_type: Optional[type[BaseException]],
        exc: Optional[BaseException],
        tb: Optional[TracebackType],
    ) -> None:
        self.close()


# --------------------------------------------------------------------------- #
# Async (aio_pika)
# --------------------------------------------------------------------------- #
class AsyncConnectionManager:
    """Lifecycle-managed wrapper around ``aio_pika.connect_robust``."""

    def __init__(self, config: RabbitMQConfig) -> None:
        self._config = config
        self._connection: Optional[AbstractRobustConnection] = None

    @property
    def config(self) -> RabbitMQConfig:
        return self._config

    def is_open(self) -> bool:
        return self._connection is not None and not self._connection.is_closed

    async def connect(self) -> AbstractRobustConnection:
        """Open (or return) a robust async connection."""

        if self.is_open():
            assert self._connection is not None
            return self._connection

        # Import lazily so that strict typing does not fail when aio_pika isn't
        # installed during static analysis.
        import aio_pika
        from aio_pika.exceptions import AMQPConnectionError as AioAMQPConnectionError
        from aio_pika.exceptions import AMQPError as AioAMQPError

        ssl_ctx = self._config.build_ssl_context()
        url = self._config.amqp_url()
        try:
            async for attempt in _async_retry((AioAMQPConnectionError, ConnectionError)):
                with attempt:
                    self._connection = await aio_pika.connect_robust(
                        url=url,
                        timeout=self._config.connection_timeout,
                        heartbeat=self._config.heartbeat,
                        ssl_context=ssl_ctx,
                    )
        except AioAMQPError as exc:
            raise RabbitMQConnectionError(
                f"Unable to connect to RabbitMQ (async) at {self._config.host}: {exc}",
                cause=exc,
            ) from exc
        assert self._connection is not None
        return self._connection

    async def channel(self) -> AbstractRobustChannel:
        """Return a new channel from the underlying connection."""

        conn = await self.connect()
        try:
            # aio_pika's robust connection returns a robust channel.
            return await conn.channel()  # type: ignore[return-value]
        except Exception as exc:
            raise RabbitMQChannelError(
                f"Could not open async channel: {exc}", cause=exc
            ) from exc

    async def close(self) -> None:
        if self._connection is not None and not self._connection.is_closed:
            try:
                await self._connection.close()
            except Exception:
                logger.debug("Ignoring error while closing async connection", exc_info=True)
        self._connection = None

    async def __aenter__(self) -> AsyncConnectionManager:
        await self.connect()
        return self

    async def __aexit__(
        self,
        exc_type: Optional[type[BaseException]],
        exc: Optional[BaseException],
        tb: Optional[TracebackType],
    ) -> None:
        await self.close()


__all__ = ["AsyncConnectionManager", "SyncConnectionManager"]
