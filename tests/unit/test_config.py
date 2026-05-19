"""Unit tests for RabbitMQConfig."""

from __future__ import annotations

import ssl
from collections.abc import Iterator

import pytest

from langchain_rabbitmq.config import RabbitMQConfig
from langchain_rabbitmq.exceptions import RabbitMQConfigurationError

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    for var in list(filter(lambda k: k.startswith("RABBITMQ_"), list(__import__("os").environ))):
        monkeypatch.delenv(var, raising=False)
    return


def test_defaults() -> None:
    cfg = RabbitMQConfig.from_env()
    assert cfg.host == "localhost"
    assert cfg.port == 5672
    assert cfg.virtual_host == "/"
    assert cfg.username == "guest"
    assert cfg.password == "guest"
    assert cfg.ssl_enabled is False
    assert cfg.connection_timeout == 10.0
    assert cfg.heartbeat == 60


def test_amqp_url_quotes_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RABBITMQ_USERNAME", "user@x")
    monkeypatch.setenv("RABBITMQ_PASSWORD", "p/ss:w@rd")
    monkeypatch.setenv("RABBITMQ_VHOST", "my/vh")
    cfg = RabbitMQConfig.from_env()
    url = cfg.amqp_url()
    assert url.startswith("amqp://")
    assert "user%40x" in url
    assert "p%2Fss%3Aw%40rd" in url
    assert "my%2Fvh" in url


def test_amqp_url_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RABBITMQ_URL", "amqp://alice:s3cr3t@broker:5673/prod")
    cfg = RabbitMQConfig.from_env()
    assert cfg.url_override is not None
    assert cfg.amqp_url() == "amqp://alice:s3cr3t@broker:5673/prod"


def test_ssl_enabled_changes_scheme_and_port(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RABBITMQ_SSL", "true")
    cfg = RabbitMQConfig.from_env()
    assert cfg.ssl_enabled is True
    assert cfg.port == 5671
    assert cfg.amqp_url().startswith("amqps://")


def test_build_ssl_context_when_disabled() -> None:
    cfg = RabbitMQConfig()
    assert cfg.build_ssl_context() is None


def test_build_ssl_context_when_enabled() -> None:
    cfg = RabbitMQConfig(ssl_enabled=True, ssl_verify=False)
    ctx = cfg.build_ssl_context()
    assert isinstance(ctx, ssl.SSLContext)
    assert ctx.check_hostname is False
    assert ctx.verify_mode == ssl.CERT_NONE


def test_invalid_boolean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RABBITMQ_SSL", "maybe")
    with pytest.raises(RabbitMQConfigurationError):
        RabbitMQConfig.from_env()


def test_invalid_int_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RABBITMQ_HEARTBEAT", "fast")
    with pytest.raises(RabbitMQConfigurationError):
        RabbitMQConfig.from_env()


def test_invalid_float_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RABBITMQ_CONNECTION_TIMEOUT", "soon")
    with pytest.raises(RabbitMQConfigurationError):
        RabbitMQConfig.from_env()


def test_management_url_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RABBITMQ_HOST", "broker.example")
    cfg = RabbitMQConfig.from_env()
    assert cfg.management_http_url() == "http://broker.example:15672"


def test_management_url_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RABBITMQ_MANAGEMENT_URL", "https://mgmt.example:443/")
    cfg = RabbitMQConfig.from_env()
    assert cfg.management_http_url() == "https://mgmt.example:443"


def test_management_url_requires_scheme(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RABBITMQ_MANAGEMENT_URL", "mgmt.example")
    cfg = RabbitMQConfig.from_env()
    with pytest.raises(RabbitMQConfigurationError):
        cfg.management_http_url()


def test_management_credentials_default_to_amqp_creds() -> None:
    cfg = RabbitMQConfig(username="u", password="p")
    assert cfg.management_credentials() == ("u", "p")


def test_management_credentials_overridable() -> None:
    cfg = RabbitMQConfig(
        username="u",
        password="p",
        management_username="admin",
        management_password="admin-pw",
    )
    assert cfg.management_credentials() == ("admin", "admin-pw")


def test_validation_rejects_empty_vhost() -> None:
    with pytest.raises(Exception):
        RabbitMQConfig(virtual_host="")
