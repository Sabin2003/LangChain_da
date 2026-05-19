"""Unit tests for utilities (sync + async connection managers)."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pika.exceptions
import pytest

from langchain_rabbitmq.config import RabbitMQConfig
from langchain_rabbitmq.exceptions import (
    RabbitMQChannelError,
    RabbitMQConnectionError,
)
from langchain_rabbitmq.utilities import (
    AsyncConnectionManager,
    SyncConnectionManager,
)

pytestmark = pytest.mark.unit


# --------------------------------------------------------------------------- #
# SyncConnectionManager
# --------------------------------------------------------------------------- #
def _fake_connection() -> MagicMock:
    conn = MagicMock()
    conn.is_open = True
    ch = MagicMock()
    ch.is_open = True
    conn.channel.return_value = ch
    return conn


def test_sync_connect_creates_blocking_connection() -> None:
    cfg = RabbitMQConfig()
    fake = _fake_connection()
    with patch("langchain_rabbitmq.utilities.BlockingConnection", return_value=fake) as bc:
        mgr = SyncConnectionManager(cfg)
        assert not mgr.is_open()
        result = mgr.connect()
        assert result is fake
        assert mgr.is_open()
        bc.assert_called_once()
        # Reusing returns same connection
        assert mgr.connect() is fake


def test_sync_connect_uses_url_override(monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = RabbitMQConfig(url_override="amqp://x:y@h:5672/v")
    fake = _fake_connection()
    with patch("langchain_rabbitmq.utilities.BlockingConnection", return_value=fake):
        mgr = SyncConnectionManager(cfg)
        mgr.connect()
        # Should not raise.


def test_sync_connect_wraps_amqp_error_and_retries() -> None:
    cfg = RabbitMQConfig()
    with patch(
        "langchain_rabbitmq.utilities.BlockingConnection",
        side_effect=pika.exceptions.AMQPConnectionError("nope"),
    ) as bc:
        mgr = SyncConnectionManager(cfg)
        with pytest.raises(RabbitMQConnectionError):
            mgr.connect()
        # Tenacity is configured to attempt 3 times for retryable errors.
        assert bc.call_count == 3


def test_sync_channel_context_manager_closes_channel() -> None:
    cfg = RabbitMQConfig()
    fake = _fake_connection()
    with patch("langchain_rabbitmq.utilities.BlockingConnection", return_value=fake):
        mgr = SyncConnectionManager(cfg)
        with mgr.channel() as ch:
            assert ch is fake.channel.return_value
        ch.close.assert_called_once()


def test_sync_channel_wraps_amqp_error() -> None:
    cfg = RabbitMQConfig()
    fake = _fake_connection()
    fake.channel.side_effect = pika.exceptions.AMQPError("nope")
    with patch("langchain_rabbitmq.utilities.BlockingConnection", return_value=fake):
        mgr = SyncConnectionManager(cfg)
        with pytest.raises(RabbitMQChannelError), mgr.channel():
            pass


def test_sync_close_idempotent() -> None:
    cfg = RabbitMQConfig()
    fake = _fake_connection()
    with patch("langchain_rabbitmq.utilities.BlockingConnection", return_value=fake):
        mgr = SyncConnectionManager(cfg)
        mgr.connect()
        mgr.close()
        # Calling again does not raise.
        mgr.close()


def test_sync_context_manager_protocol() -> None:
    cfg = RabbitMQConfig()
    fake = _fake_connection()
    patcher = patch("langchain_rabbitmq.utilities.BlockingConnection", return_value=fake)
    with patcher, SyncConnectionManager(cfg) as mgr:
        assert mgr.is_open()


# --------------------------------------------------------------------------- #
# AsyncConnectionManager
# --------------------------------------------------------------------------- #
class _FakeAsyncConn:
    def __init__(self) -> None:
        self.is_closed = False
        self._channel = MagicMock()

    async def close(self) -> None:
        self.is_closed = True

    async def channel(self) -> Any:
        return self._channel


@pytest.mark.asyncio
async def test_async_connect_and_reuse(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_conn = _FakeAsyncConn()
    fake_aio = MagicMock()
    fake_aio.connect_robust = AsyncMock(return_value=fake_conn)

    class _Excs:
        class AMQPError(Exception):
            pass

        class AMQPConnectionError(AMQPError):
            pass

    import sys

    monkeypatch.setitem(sys.modules, "aio_pika", fake_aio)
    monkeypatch.setitem(sys.modules, "aio_pika.exceptions", _Excs)

    mgr = AsyncConnectionManager(RabbitMQConfig())
    conn = await mgr.connect()
    assert conn is fake_conn
    # Reuse path.
    again = await mgr.connect()
    assert again is fake_conn
    fake_aio.connect_robust.assert_awaited_once()
    await mgr.close()
    assert fake_conn.is_closed is True


@pytest.mark.asyncio
async def test_async_connect_wraps_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Excs:
        class AMQPError(Exception):
            pass

        class AMQPConnectionError(AMQPError):
            pass

    fake_aio = MagicMock()
    fake_aio.connect_robust = AsyncMock(side_effect=_Excs.AMQPConnectionError("nope"))

    import sys

    monkeypatch.setitem(sys.modules, "aio_pika", fake_aio)
    monkeypatch.setitem(sys.modules, "aio_pika.exceptions", _Excs)

    mgr = AsyncConnectionManager(RabbitMQConfig())
    with pytest.raises(RabbitMQConnectionError):
        await mgr.connect()


@pytest.mark.asyncio
async def test_async_channel_wraps_error(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_conn = _FakeAsyncConn()

    async def broken_channel() -> Any:
        raise RuntimeError("kaboom")

    fake_conn.channel = broken_channel  # type: ignore[method-assign]
    fake_aio = MagicMock()
    fake_aio.connect_robust = AsyncMock(return_value=fake_conn)

    class _Excs:
        class AMQPError(Exception):
            pass

        class AMQPConnectionError(AMQPError):
            pass

    import sys

    monkeypatch.setitem(sys.modules, "aio_pika", fake_aio)
    monkeypatch.setitem(sys.modules, "aio_pika.exceptions", _Excs)

    mgr = AsyncConnectionManager(RabbitMQConfig())
    with pytest.raises(RabbitMQChannelError):
        await mgr.channel()
    await mgr.close()
