# langchain-rabbitmq

A first-class, production-grade RabbitMQ integration for [LangChain](https://www.langchain.com/).

`langchain-rabbitmq` exposes a complete set of typed `BaseTool` and `BaseToolkit`
classes that let an LLM agent fully administer a RabbitMQ broker — declaring
queues and exchanges, publishing and consuming messages, binding, acknowledging,
and monitoring the cluster.

## Highlights

* Sync (`pika`) and async (`aio-pika`) support.
* SSL/TLS, configurable timeouts and tenacity-based retries.
* Strict typing — passes `pyright --strict`.
* Pydantic v2 schemas for every tool argument.
* 90%+ unit-test coverage, integration tests via `testcontainers`, and a 1000-message load test.
* AgentExecutor and LCEL ready.

## Getting started

```bash
pip install langchain-rabbitmq
```

```python
from langchain_rabbitmq import RabbitMQToolkit
toolkit = RabbitMQToolkit.from_env()
tools = toolkit.get_tools()
```

See [Getting started](getting_started.md) for the full quick-start guide and
[Cookbooks](cookbooks/basic_agent.md) for end-to-end examples.
