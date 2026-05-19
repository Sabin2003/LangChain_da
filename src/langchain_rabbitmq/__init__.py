"""langchain-rabbitmq — LangChain tools and toolkit for managing RabbitMQ.

Public re-exports keep the import path stable for downstream users::

    from langchain_rabbitmq import (
        RabbitMQConfig,
        RabbitMQToolkit,
        SyncConnectionManager,
        AsyncConnectionManager,
    )
"""

from __future__ import annotations

from .config import RabbitMQConfig
from .exceptions import (
    RabbitMQChannelError,
    RabbitMQConfigurationError,
    RabbitMQConnectionError,
    RabbitMQMessageError,
    RabbitMQToolException,
)
from .toolkit import RabbitMQToolkit
from .tools import (
    AckMessageTool,
    AsyncPublishMessageTool,
    BaseAsyncRabbitMQTool,
    BaseRabbitMQTool,
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

__version__ = "0.1.0"

__all__ = [
    "AckMessageTool",
    "AsyncConnectionManager",
    "AsyncPublishMessageTool",
    "BaseAsyncRabbitMQTool",
    "BaseRabbitMQTool",
    "BindExchangeTool",
    "BindQueueTool",
    "CheckHealthTool",
    "CloseConnectionTool",
    "ConsumeMessageTool",
    "DeclareExchangeTool",
    "DeclareQueueTool",
    "DeleteExchangeTool",
    "DeleteQueueTool",
    "GetConnectionInfoTool",
    "GetNodeStatsTool",
    "GetQueueInfoTool",
    "ListBindingsTool",
    "ListExchangesTool",
    "ListQueuesTool",
    "NackMessageTool",
    "PublishMessageTool",
    "PurgeQueueTool",
    "RabbitMQChannelError",
    "RabbitMQConfig",
    "RabbitMQConfigurationError",
    "RabbitMQConnectionError",
    "RabbitMQMessageError",
    "RabbitMQToolException",
    "RabbitMQToolkit",
    "RejectMessageTool",
    "SyncConnectionManager",
    "UnbindQueueTool",
    "__version__",
]
