"""Pytest fixtures spinning up a real RabbitMQ broker via ``testcontainers``.

These fixtures are only used by tests marked ``@pytest.mark.integration`` /
``@pytest.mark.e2e`` / ``@pytest.mark.load``. They are skipped automatically
when Docker is unavailable.
"""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest

try:
    from testcontainers.rabbitmq import RabbitMqContainer  # type: ignore[import-not-found]
except Exception:  # pragma: no cover - import-time guard
    RabbitMqContainer = None  # type: ignore[assignment]


@pytest.fixture(scope="session")
def rabbitmq_container() -> Iterator[object]:
    """Start a ``rabbitmq:3-management`` container for the test session."""

    if RabbitMqContainer is None:
        pytest.skip("testcontainers[rabbitmq] not installed")
    try:
        import docker  # type: ignore[import-not-found]

        docker.from_env().ping()
    except Exception:
        pytest.skip("Docker daemon not reachable; skipping integration tests")
    container = RabbitMqContainer("rabbitmq:3-management")
    container.start()
    try:
        yield container
    finally:
        container.stop()


@pytest.fixture(scope="session")
def rabbitmq_env(rabbitmq_container: object) -> Iterator[None]:
    """Export ``RABBITMQ_*`` env vars pointing at the running container."""

    cont = rabbitmq_container
    host = cont.get_container_host_ip()  # type: ignore[attr-defined]
    port = int(cont.get_exposed_port(5672))  # type: ignore[attr-defined]
    mgmt_port = int(cont.get_exposed_port(15672))  # type: ignore[attr-defined]

    previous: dict[str, str | None] = {}
    overrides = {
        "RABBITMQ_HOST": host,
        "RABBITMQ_PORT": str(port),
        "RABBITMQ_USERNAME": "guest",
        "RABBITMQ_PASSWORD": "guest",
        "RABBITMQ_VHOST": "/",
        "RABBITMQ_MANAGEMENT_URL": f"http://{host}:{mgmt_port}",
    }
    for k, v in overrides.items():
        previous[k] = os.environ.get(k)
        os.environ[k] = v
    try:
        yield
    finally:
        for k, v in previous.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
