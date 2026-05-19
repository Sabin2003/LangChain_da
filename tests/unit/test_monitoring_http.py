"""Tests for HTTP-based management tools."""

from __future__ import annotations

import io
import json
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError, URLError

import pytest

from langchain_rabbitmq.config import RabbitMQConfig
from langchain_rabbitmq.exceptions import RabbitMQConnectionError
from langchain_rabbitmq.tools import (
    GetNodeStatsTool,
    ListBindingsTool,
    ListExchangesTool,
    ListQueuesTool,
)

pytestmark = pytest.mark.unit


class FakeManager:
    def __init__(self) -> None:
        self.config = RabbitMQConfig(host="broker.example")

    @contextmanager
    def channel(self) -> Iterator[MagicMock]:  # pragma: no cover - unused here
        yield MagicMock()

    def close(self) -> None:  # pragma: no cover
        return None

    def is_open(self) -> bool:  # pragma: no cover
        return True


def _fake_urlopen(body: Any) -> Any:
    raw = json.dumps(body).encode("utf-8")
    fake_resp = MagicMock()
    fake_resp.read.return_value = raw
    fake_resp.__enter__ = lambda self=fake_resp: fake_resp  # type: ignore[assignment]
    fake_resp.__exit__ = lambda self, *a, **kw: None  # type: ignore[assignment]
    return fake_resp


_URLOPEN = "langchain_rabbitmq.tools.monitoring_tools.urllib.request.urlopen"


def test_list_queues_calls_management_api() -> None:
    tool = ListQueuesTool(manager=FakeManager())  # type: ignore[arg-type]
    fake = _fake_urlopen([{"name": "q1"}, {"name": "q2"}])
    with patch(_URLOPEN, return_value=fake) as up:
        out = json.loads(tool.invoke({}))
    assert out["count"] == 2
    assert up.called
    req = up.call_args.args[0]
    assert req.full_url.endswith("/api/queues")
    assert req.headers["Authorization"].startswith("Basic ")


def test_list_queues_with_vhost() -> None:
    tool = ListQueuesTool(manager=FakeManager())  # type: ignore[arg-type]
    fake = _fake_urlopen([])
    with patch(_URLOPEN, return_value=fake) as up:
        tool.invoke({"vhost": "/"})
    req = up.call_args.args[0]
    assert "/api/queues/" in req.full_url


def test_list_exchanges_and_bindings() -> None:
    tool_ex = ListExchangesTool(manager=FakeManager())  # type: ignore[arg-type]
    tool_bi = ListBindingsTool(manager=FakeManager())  # type: ignore[arg-type]
    with patch(
        "langchain_rabbitmq.tools.monitoring_tools.urllib.request.urlopen",
        return_value=_fake_urlopen([{"name": "amq.direct"}]),
    ):
        out = json.loads(tool_ex.invoke({}))
    assert out["count"] == 1

    with patch(
        "langchain_rabbitmq.tools.monitoring_tools.urllib.request.urlopen",
        return_value=_fake_urlopen([]),
    ):
        out = json.loads(tool_bi.invoke({}))
    assert out["count"] == 0


def test_management_http_error() -> None:
    tool = ListQueuesTool(manager=FakeManager())  # type: ignore[arg-type]
    err = HTTPError(
        url="http://broker.example:15672/api/queues",
        code=401,
        msg="Unauthorized",
        hdrs=None,  # type: ignore[arg-type]
        fp=io.BytesIO(b""),
    )
    with patch(
        "langchain_rabbitmq.tools.monitoring_tools.urllib.request.urlopen",
        side_effect=err,
    ), pytest.raises(RabbitMQConnectionError):
        tool.invoke({})


def test_management_url_error() -> None:
    tool = ListQueuesTool(manager=FakeManager())  # type: ignore[arg-type]
    with patch(
        "langchain_rabbitmq.tools.monitoring_tools.urllib.request.urlopen",
        side_effect=URLError("dns"),
    ), pytest.raises(RabbitMQConnectionError):
        tool.invoke({})


def test_management_non_json_response() -> None:
    tool = ListQueuesTool(manager=FakeManager())  # type: ignore[arg-type]
    bad = MagicMock()
    bad.read.return_value = b"not json"
    bad.__enter__ = lambda self=bad: bad  # type: ignore[assignment]
    bad.__exit__ = lambda self, *a, **kw: None  # type: ignore[assignment]
    with patch(
        "langchain_rabbitmq.tools.monitoring_tools.urllib.request.urlopen",
        return_value=bad,
    ), pytest.raises(RabbitMQConnectionError):
        tool.invoke({})


def test_get_node_stats_uses_tcp_probe() -> None:
    tool = GetNodeStatsTool(manager=FakeManager())  # type: ignore[arg-type]
    fake = _fake_urlopen([{"name": "rabbit@node1"}])
    with patch(
        "langchain_rabbitmq.tools.monitoring_tools.urllib.request.urlopen",
        return_value=fake,
    ), patch(
        "langchain_rabbitmq.tools.monitoring_tools._probe_tcp", return_value=True
    ) as probe:
        out = json.loads(tool.invoke({}))
    assert out["amqp_port_reachable"] is True
    assert out["nodes"][0]["name"] == "rabbit@node1"
    probe.assert_called_once()


def test_management_url_scheme_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    """ftp:// schemes are explicitly refused for security."""
    monkeypatch.setenv("RABBITMQ_MANAGEMENT_URL", "ftp://x:21")
    cfg = RabbitMQConfig.from_env()
    from langchain_rabbitmq.tools.monitoring_tools import _management_get

    with pytest.raises(RabbitMQConnectionError):
        _management_get(cfg, "/api/queues")
