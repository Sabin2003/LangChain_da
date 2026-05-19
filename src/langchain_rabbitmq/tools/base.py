"""Shared base classes for langchain-rabbitmq tools."""

from __future__ import annotations

import json
from typing import Any, Optional

from langchain_core.callbacks import (
    AsyncCallbackManagerForToolRun,
    CallbackManagerForToolRun,
)
from langchain_core.tools import BaseTool
from pydantic import ConfigDict, PrivateAttr

from ..config import RabbitMQConfig
from ..utilities import AsyncConnectionManager, SyncConnectionManager


class BaseRabbitMQTool(BaseTool):
    """Base class for every synchronous RabbitMQ tool.

    Stores a :class:`SyncConnectionManager` that is shared across tool
    invocations to avoid reconnecting on every call.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    _manager: SyncConnectionManager = PrivateAttr()

    def __init__(
        self,
        manager: Optional[SyncConnectionManager] = None,
        *,
        config: Optional[RabbitMQConfig] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        if manager is None:
            manager = SyncConnectionManager(config or RabbitMQConfig.from_env())
        self._manager = manager

    @property
    def manager(self) -> SyncConnectionManager:
        return self._manager

    # Synchronous default - subclasses must implement _execute.
    def _run(
        self,
        *args: Any,
        run_manager: Optional[CallbackManagerForToolRun] = None,
        **kwargs: Any,
    ) -> str:
        del args, run_manager
        result = self._execute(**kwargs)
        return _to_json(result)

    # Async fallback runs the sync version in a thread.
    async def _arun(
        self,
        *args: Any,
        run_manager: Optional[AsyncCallbackManagerForToolRun] = None,
        **kwargs: Any,
    ) -> str:
        import asyncio

        del args, run_manager
        return await asyncio.to_thread(lambda: _to_json(self._execute(**kwargs)))

    # Subclass contract.
    def _execute(self, **kwargs: Any) -> Any:  # pragma: no cover - abstract
        raise NotImplementedError


class BaseAsyncRabbitMQTool(BaseTool):
    """Base class for native asynchronous RabbitMQ tools (aio-pika)."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    _async_manager: AsyncConnectionManager = PrivateAttr()

    def __init__(
        self,
        manager: Optional[AsyncConnectionManager] = None,
        *,
        config: Optional[RabbitMQConfig] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        if manager is None:
            manager = AsyncConnectionManager(config or RabbitMQConfig.from_env())
        self._async_manager = manager

    @property
    def async_manager(self) -> AsyncConnectionManager:
        return self._async_manager

    def _run(
        self,
        *args: Any,
        run_manager: Optional[CallbackManagerForToolRun] = None,
        **kwargs: Any,
    ) -> str:
        import asyncio

        del args, run_manager
        return asyncio.get_event_loop().run_until_complete(
            self._aexecute_to_json(**kwargs)
        )

    async def _arun(
        self,
        *args: Any,
        run_manager: Optional[AsyncCallbackManagerForToolRun] = None,
        **kwargs: Any,
    ) -> str:
        del args, run_manager
        return await self._aexecute_to_json(**kwargs)

    async def _aexecute_to_json(self, **kwargs: Any) -> str:
        result = await self._aexecute(**kwargs)
        return _to_json(result)

    async def _aexecute(self, **kwargs: Any) -> Any:  # pragma: no cover - abstract
        raise NotImplementedError


def _to_json(value: Any) -> str:
    """Render a tool result as a deterministic JSON string for the LLM."""

    if isinstance(value, str):
        # Already a human-readable string; wrap in a JSON object for consistency.
        return json.dumps({"result": value}, sort_keys=True, ensure_ascii=False)
    try:
        return json.dumps(value, sort_keys=True, default=str, ensure_ascii=False)
    except TypeError:
        return json.dumps({"result": str(value)}, sort_keys=True, ensure_ascii=False)


__all__ = ["BaseAsyncRabbitMQTool", "BaseRabbitMQTool"]
