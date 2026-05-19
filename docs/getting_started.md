# Getting started

## 1. Install

```bash
pip install langchain-rabbitmq
```

The package requires Python **3.9+**. It depends on `langchain-core`, `pika`,
`aio-pika`, `pydantic>=2`, and `tenacity`.

## 2. Configure the broker

Set the `RABBITMQ_*` environment variables. The minimum is:

```bash
export RABBITMQ_HOST=localhost
export RABBITMQ_PORT=5672
export RABBITMQ_USERNAME=guest
export RABBITMQ_PASSWORD=guest
```

For a TLS-protected broker:

```bash
export RABBITMQ_SSL=true
export RABBITMQ_SSL_CA_CERTS=/etc/ssl/certs/ca.pem
export RABBITMQ_SSL_CERTFILE=/etc/ssl/client.crt
export RABBITMQ_SSL_KEYFILE=/etc/ssl/client.key
```

See [Configuration](configuration.md) for every supported variable.

## 3. Use the toolkit

```python
from langchain_rabbitmq import RabbitMQToolkit

toolkit = RabbitMQToolkit.from_env()
tools = toolkit.get_tools()
```

Each tool is a `langchain_core.tools.BaseTool` and is fully compatible with any
LangChain agent (`AgentExecutor`, LangGraph nodes, LCEL chains, ...).

## 4. Direct use without an agent

You can call any tool yourself — they validate inputs with Pydantic v2:

```python
from langchain_rabbitmq import DeclareQueueTool, PublishMessageTool

DeclareQueueTool().invoke({"queue": "orders", "durable": True})

PublishMessageTool().invoke(
    {
        "exchange": "",
        "routing_key": "orders",
        "json_body": {"id": 42, "total": 19.99},
        "headers": {"trace_id": "abc"},
        "priority": 5,
    }
)
```

## 5. Cleaning up

The connection managers are lazy: they connect on first use and stay open for
the lifetime of the toolkit. Close them when shutting down:

```python
import asyncio

asyncio.run(toolkit.aclose())
```
