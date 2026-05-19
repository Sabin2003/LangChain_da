"""Unit tests for exceptions module."""

from __future__ import annotations

import pytest

from langchain_rabbitmq.exceptions import (
    RabbitMQChannelError,
    RabbitMQConfigurationError,
    RabbitMQConnectionError,
    RabbitMQMessageError,
    RabbitMQToolException,
)

pytestmark = pytest.mark.unit


def test_base_exception_message_and_cause() -> None:
    original = ValueError("boom")
    err = RabbitMQToolException("wrapped", cause=original)
    assert err.message == "wrapped"
    assert err.__cause__ is original
    assert str(err) == "wrapped"


@pytest.mark.parametrize(
    "cls",
    [
        RabbitMQConnectionError,
        RabbitMQChannelError,
        RabbitMQMessageError,
        RabbitMQConfigurationError,
    ],
)
def test_subclasses_inherit_from_base(cls: type[RabbitMQToolException]) -> None:
    err = cls("oops")
    assert isinstance(err, RabbitMQToolException)
    assert err.message == "oops"
