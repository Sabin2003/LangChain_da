"""Configuration loaded from environment variables.

Configuration is loaded **only from environment variables** as required by the
project's design constraints. The supported variables are::

    RABBITMQ_URL                  AMQP / AMQPS URL (overrides individual fields)
    RABBITMQ_HOST                 Broker host (default: localhost)
    RABBITMQ_PORT                 Broker port (default: 5672, or 5671 with TLS)
    RABBITMQ_VHOST                Virtual host (default: "/")
    RABBITMQ_USERNAME             Username (default: guest)
    RABBITMQ_PASSWORD             Password (default: guest)
    RABBITMQ_SSL                  "true"/"false" – enable TLS (default: false)
    RABBITMQ_SSL_CA_CERTS         Path to CA bundle (optional)
    RABBITMQ_SSL_CERTFILE         Client certificate path (optional)
    RABBITMQ_SSL_KEYFILE          Client key path (optional)
    RABBITMQ_SSL_VERIFY           "true"/"false" – verify peer cert (default: true)
    RABBITMQ_CONNECTION_TIMEOUT   Connection timeout in seconds (default: 10.0)
    RABBITMQ_HEARTBEAT            Heartbeat interval seconds (default: 60)
    RABBITMQ_MANAGEMENT_URL       HTTP API URL (default: derived from host)
    RABBITMQ_MANAGEMENT_USERNAME  Defaults to RABBITMQ_USERNAME
    RABBITMQ_MANAGEMENT_PASSWORD  Defaults to RABBITMQ_PASSWORD
"""

from __future__ import annotations

import os
import ssl
from typing import Optional, Union
from urllib.parse import quote, urlparse, urlunparse

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .exceptions import RabbitMQConfigurationError


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    value = raw.strip().lower()
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"0", "false", "no", "off"}:
        return False
    raise RabbitMQConfigurationError(
        f"Invalid boolean value for {name}: {raw!r}. Expected true/false."
    )


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError as exc:
        raise RabbitMQConfigurationError(
            f"Invalid float value for {name}: {raw!r}."
        ) from exc


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise RabbitMQConfigurationError(
            f"Invalid integer value for {name}: {raw!r}."
        ) from exc


class RabbitMQConfig(BaseModel):
    """Strongly typed RabbitMQ connection configuration.

    The configuration is normally created via :meth:`from_env`. It can also be
    instantiated directly for tests or programmatic use.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    host: str = Field(default="localhost")
    port: int = Field(default=5672, ge=1, le=65535)
    virtual_host: str = Field(default="/")
    username: str = Field(default="guest")
    password: str = Field(default="guest")
    ssl_enabled: bool = Field(default=False)
    ssl_ca_certs: Optional[str] = Field(default=None)
    ssl_certfile: Optional[str] = Field(default=None)
    ssl_keyfile: Optional[str] = Field(default=None)
    ssl_verify: bool = Field(default=True)
    connection_timeout: float = Field(default=10.0, gt=0)
    heartbeat: int = Field(default=60, ge=0)
    management_url: Optional[str] = Field(default=None)
    management_username: Optional[str] = Field(default=None)
    management_password: Optional[str] = Field(default=None)
    url_override: Optional[str] = Field(default=None)

    @field_validator("virtual_host")
    @classmethod
    def _validate_vhost(cls, value: str) -> str:
        if not value:
            raise ValueError("virtual_host must not be empty")
        return value

    @classmethod
    def from_env(cls) -> RabbitMQConfig:
        """Build a :class:`RabbitMQConfig` from process environment variables."""

        url_override = os.environ.get("RABBITMQ_URL")
        ssl_enabled = _env_bool("RABBITMQ_SSL", False)
        default_port = 5671 if ssl_enabled else 5672
        try:
            return cls(
                host=os.environ.get("RABBITMQ_HOST", "localhost"),
                port=_env_int("RABBITMQ_PORT", default_port),
                virtual_host=os.environ.get("RABBITMQ_VHOST", "/"),
                username=os.environ.get("RABBITMQ_USERNAME", "guest"),
                password=os.environ.get("RABBITMQ_PASSWORD", "guest"),
                ssl_enabled=ssl_enabled,
                ssl_ca_certs=os.environ.get("RABBITMQ_SSL_CA_CERTS"),
                ssl_certfile=os.environ.get("RABBITMQ_SSL_CERTFILE"),
                ssl_keyfile=os.environ.get("RABBITMQ_SSL_KEYFILE"),
                ssl_verify=_env_bool("RABBITMQ_SSL_VERIFY", True),
                connection_timeout=_env_float("RABBITMQ_CONNECTION_TIMEOUT", 10.0),
                heartbeat=_env_int("RABBITMQ_HEARTBEAT", 60),
                management_url=os.environ.get("RABBITMQ_MANAGEMENT_URL"),
                management_username=os.environ.get("RABBITMQ_MANAGEMENT_USERNAME"),
                management_password=os.environ.get("RABBITMQ_MANAGEMENT_PASSWORD"),
                url_override=url_override,
            )
        except RabbitMQConfigurationError:
            raise
        except Exception as exc:
            raise RabbitMQConfigurationError(
                f"Invalid RabbitMQ configuration: {exc}"
            ) from exc

    def amqp_url(self) -> str:
        """Build the AMQP(S) URL used by ``pika`` and ``aio-pika``."""

        if self.url_override:
            return self.url_override
        scheme = "amqps" if self.ssl_enabled else "amqp"
        user = quote(self.username, safe="")
        pwd = quote(self.password, safe="")
        vhost = quote(self.virtual_host, safe="")
        return f"{scheme}://{user}:{pwd}@{self.host}:{self.port}/{vhost}"

    def management_http_url(self) -> str:
        """Build the RabbitMQ management HTTP API base URL."""

        if self.management_url:
            parsed = urlparse(self.management_url)
            if not parsed.scheme:
                raise RabbitMQConfigurationError(
                    f"RABBITMQ_MANAGEMENT_URL must include a scheme: {self.management_url!r}"
                )
            return urlunparse(parsed._replace(path=parsed.path.rstrip("/")))
        scheme = "https" if self.ssl_enabled else "http"
        # Management plugin default port is 15672 for HTTP, 15671 for HTTPS
        port = 15671 if self.ssl_enabled else 15672
        return f"{scheme}://{self.host}:{port}"

    def management_credentials(self) -> tuple[str, str]:
        """Return management HTTP API credentials (defaults to AMQP creds)."""

        return (
            self.management_username or self.username,
            self.management_password or self.password,
        )

    def build_ssl_context(self) -> Optional[ssl.SSLContext]:
        """Build an :class:`ssl.SSLContext` honoring the configuration."""

        if not self.ssl_enabled:
            return None
        ctx = ssl.create_default_context(cafile=self.ssl_ca_certs)
        if not self.ssl_verify:
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
        if self.ssl_certfile:
            ctx.load_cert_chain(certfile=self.ssl_certfile, keyfile=self.ssl_keyfile)
        return ctx


DeliveryMode = Union[int]
"""Type alias for AMQP delivery mode (1 = transient, 2 = persistent)."""


__all__ = ["DeliveryMode", "RabbitMQConfig"]
