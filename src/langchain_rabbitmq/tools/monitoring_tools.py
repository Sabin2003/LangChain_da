"""Monitoring & admin tools.

AMQP-level tools use the same :class:`SyncConnectionManager`; HTTP-only tools
(``list_queues``, ``list_exchanges``, ``list_bindings``, ``get_node_stats``)
query the RabbitMQ management plugin via :mod:`urllib.request` to avoid an
extra ``requests`` dependency.
"""

from __future__ import annotations

import base64
import json
import socket
import ssl
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Optional

import pika.exceptions

from ..config import RabbitMQConfig
from ..exceptions import RabbitMQChannelError, RabbitMQConnectionError
from ..models import EmptyInput, ListResourceInput
from .base import BaseRabbitMQTool


def _management_get(
    config: RabbitMQConfig, path: str, *, timeout: float = 10.0
) -> Any:
    """Issue an authenticated GET against the RabbitMQ management plugin."""

    base = config.management_http_url().rstrip("/")
    url = f"{base}{path}"
    user, password = config.management_credentials()
    token = base64.b64encode(f"{user}:{password}".encode()).decode("ascii")
    req = urllib.request.Request(  # noqa: S310 - http(s) only, scheme validated below
        url, headers={"Authorization": f"Basic {token}", "Accept": "application/json"}
    )
    scheme = urllib.parse.urlparse(url).scheme
    if scheme not in {"http", "https"}:
        raise RabbitMQConnectionError(
            f"Unsupported management URL scheme: {scheme!r}"
        )
    ctx: Optional[ssl.SSLContext] = None
    if scheme == "https":
        ctx = config.build_ssl_context() or ssl.create_default_context()
    try:
        # The URL scheme is validated above to be http/https only — addressing
        # bandit B310 (audit url open for permitted schemes).
        with urllib.request.urlopen(  # noqa: S310
            req, timeout=timeout, context=ctx
        ) as resp:  # nosec B310
            raw = resp.read()
    except urllib.error.HTTPError as exc:
        raise RabbitMQConnectionError(
            f"Management API HTTP {exc.code} on {path}: {exc.reason}", cause=exc
        ) from exc
    except urllib.error.URLError as exc:
        raise RabbitMQConnectionError(
            f"Management API unreachable at {url}: {exc.reason}", cause=exc
        ) from exc
    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RabbitMQConnectionError(
            f"Management API returned non-JSON response from {path}", cause=exc
        ) from exc


class CheckHealthTool(BaseRabbitMQTool):
    """Open a channel and run a no-op to verify the broker is reachable."""

    name: str = "rabbitmq_check_health"
    description: str = "Verify connectivity to the RabbitMQ broker by opening a channel."
    args_schema: type = EmptyInput

    def _execute(self) -> dict[str, Any]:
        try:
            with self.manager.channel() as ch:
                return {"healthy": True, "is_open": bool(ch.is_open)}
        except pika.exceptions.AMQPError as exc:  # pragma: no cover - exercised via mocks
            raise RabbitMQChannelError(f"check_health failed: {exc}", cause=exc) from exc


class GetConnectionInfoTool(BaseRabbitMQTool):
    """Return information about the active connection (no credentials)."""

    name: str = "rabbitmq_get_connection_info"
    description: str = "Return information about the active RabbitMQ connection."
    args_schema: type = EmptyInput

    def _execute(self) -> dict[str, Any]:
        cfg = self.manager.config
        return {
            "is_open": self.manager.is_open(),
            "host": cfg.host,
            "port": cfg.port,
            "virtual_host": cfg.virtual_host,
            "ssl_enabled": cfg.ssl_enabled,
            "heartbeat": cfg.heartbeat,
            "username": cfg.username,
        }


class CloseConnectionTool(BaseRabbitMQTool):
    """Close the underlying connection (re-opened lazily next call)."""

    name: str = "rabbitmq_close_connection"
    description: str = "Close the underlying RabbitMQ connection."
    args_schema: type = EmptyInput

    def _execute(self) -> dict[str, Any]:
        self.manager.close()
        return {"closed": True}


class ListQueuesTool(BaseRabbitMQTool):
    """List queues via the management HTTP API."""

    name: str = "rabbitmq_list_queues"
    description: str = (
        "List RabbitMQ queues using the management HTTP API. "
        "Requires the rabbitmq_management plugin."
    )
    args_schema: type = ListResourceInput

    def _execute(self, *, vhost: Optional[str] = None) -> dict[str, Any]:
        path = (
            "/api/queues"
            if vhost is None
            else f"/api/queues/{urllib.parse.quote(vhost, safe='')}"
        )
        data = _management_get(self.manager.config, path)
        return {"count": len(data), "queues": data}


class ListExchangesTool(BaseRabbitMQTool):
    """List exchanges via the management HTTP API."""

    name: str = "rabbitmq_list_exchanges"
    description: str = "List RabbitMQ exchanges using the management HTTP API."
    args_schema: type = ListResourceInput

    def _execute(self, *, vhost: Optional[str] = None) -> dict[str, Any]:
        path = (
            "/api/exchanges"
            if vhost is None
            else f"/api/exchanges/{urllib.parse.quote(vhost, safe='')}"
        )
        data = _management_get(self.manager.config, path)
        return {"count": len(data), "exchanges": data}


class ListBindingsTool(BaseRabbitMQTool):
    """List bindings via the management HTTP API."""

    name: str = "rabbitmq_list_bindings"
    description: str = "List RabbitMQ bindings using the management HTTP API."
    args_schema: type = ListResourceInput

    def _execute(self, *, vhost: Optional[str] = None) -> dict[str, Any]:
        path = (
            "/api/bindings"
            if vhost is None
            else f"/api/bindings/{urllib.parse.quote(vhost, safe='')}"
        )
        data = _management_get(self.manager.config, path)
        return {"count": len(data), "bindings": data}


class GetNodeStatsTool(BaseRabbitMQTool):
    """Return RabbitMQ cluster node statistics."""

    name: str = "rabbitmq_get_node_stats"
    description: str = "Return RabbitMQ cluster node statistics via the management HTTP API."
    args_schema: type = EmptyInput

    def _execute(self) -> dict[str, Any]:
        # Sanity check: also confirm TCP reachability of AMQP port.
        cfg = self.manager.config
        reachable = _probe_tcp(cfg.host, cfg.port, timeout=cfg.connection_timeout)
        nodes = _management_get(cfg, "/api/nodes")
        return {"amqp_port_reachable": reachable, "nodes": nodes}


def _probe_tcp(host: str, port: int, *, timeout: float) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


__all__ = [
    "CheckHealthTool",
    "CloseConnectionTool",
    "GetConnectionInfoTool",
    "GetNodeStatsTool",
    "ListBindingsTool",
    "ListExchangesTool",
    "ListQueuesTool",
]
