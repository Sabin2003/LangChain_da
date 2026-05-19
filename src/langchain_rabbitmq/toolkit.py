"""Toolkit assembling every RabbitMQ tool for easy use with AgentExecutor."""

from __future__ import annotations

from typing import Any, Optional

from langchain_core.tools import BaseTool, BaseToolkit
from pydantic import ConfigDict, PrivateAttr

from .config import RabbitMQConfig
from .tools import (
    AckMessageTool,
    AsyncPublishMessageTool,
    BindExchangeTool,
    BindQueueTool,
    CheckHealthTool,
    CloseConnectionTool,
    ConsumeMessageTool,
    DeclareExchangeTool,
    DeclareQueueTool,
    DeleteExchangeTool,
    DeleteQueueTool,
    GetConnectionInfoTool,
    GetNodeStatsTool,
    GetQueueInfoTool,
    ListBindingsTool,
    ListExchangesTool,
    ListQueuesTool,
    NackMessageTool,
    PublishMessageTool,
    PurgeQueueTool,
    RejectMessageTool,
    UnbindQueueTool,
)
from .utilities import AsyncConnectionManager, SyncConnectionManager


class RabbitMQToolkit(BaseToolkit):
    """Bundle every ``langchain-rabbitmq`` tool for one shared connection.

    Example
    -------
    >>> from langchain_rabbitmq import RabbitMQToolkit
    >>> toolkit = RabbitMQToolkit.from_env()
    >>> tools = toolkit.get_tools()
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    _config: RabbitMQConfig = PrivateAttr()
    _sync_manager: SyncConnectionManager = PrivateAttr()
    _async_manager: AsyncConnectionManager = PrivateAttr()
    _include_async: bool = PrivateAttr(default=True)

    def __init__(
        self,
        config: Optional[RabbitMQConfig] = None,
        *,
        include_async: bool = True,
        sync_manager: Optional[SyncConnectionManager] = None,
        async_manager: Optional[AsyncConnectionManager] = None,
        **data: Any,
    ) -> None:
        super().__init__(**data)
        self._config = config or RabbitMQConfig.from_env()
        self._sync_manager = sync_manager or SyncConnectionManager(self._config)
        self._async_manager = async_manager or AsyncConnectionManager(self._config)
        self._include_async = include_async

    @classmethod
    def from_env(cls, *, include_async: bool = True) -> RabbitMQToolkit:
        """Create a toolkit from environment variables."""

        return cls(config=RabbitMQConfig.from_env(), include_async=include_async)

    @property
    def config(self) -> RabbitMQConfig:
        return self._config

    @property
    def sync_manager(self) -> SyncConnectionManager:
        return self._sync_manager

    @property
    def async_manager(self) -> AsyncConnectionManager:
        return self._async_manager

    def get_tools(self) -> list[BaseTool]:
        """Return every tool, sharing the toolkit's connection managers."""

        m = self._sync_manager
        # The kwargs are forwarded to each tool's __init__ which accepts a
        # `manager=` parameter; pyright does not see that override because
        # BaseTool synthesises its __init__ from pydantic fields.
        def _sync(cls: type[BaseTool]) -> BaseTool:
            return cls(manager=m)  # type: ignore[call-arg]

        sync_tools: list[BaseTool] = [
            _sync(DeclareQueueTool),
            _sync(DeleteQueueTool),
            _sync(PurgeQueueTool),
            _sync(BindQueueTool),
            _sync(UnbindQueueTool),
            _sync(GetQueueInfoTool),
            _sync(DeclareExchangeTool),
            _sync(DeleteExchangeTool),
            _sync(BindExchangeTool),
            _sync(PublishMessageTool),
            _sync(ConsumeMessageTool),
            _sync(AckMessageTool),
            _sync(NackMessageTool),
            _sync(RejectMessageTool),
            _sync(CheckHealthTool),
            _sync(GetConnectionInfoTool),
            _sync(CloseConnectionTool),
            _sync(ListQueuesTool),
            _sync(ListExchangesTool),
            _sync(ListBindingsTool),
            _sync(GetNodeStatsTool),
        ]
        if self._include_async:
            sync_tools.append(
                AsyncPublishMessageTool(manager=self._async_manager)  # type: ignore[call-arg]
            )
        return sync_tools

    async def aclose(self) -> None:
        """Close both sync and async connection managers."""

        self._sync_manager.close()
        await self._async_manager.close()


__all__ = ["RabbitMQToolkit"]
