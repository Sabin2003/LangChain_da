# langchain-rabbitmq

[![CI](https://github.com/Sabin2003/LangChain_da/actions/workflows/ci.yml/badge.svg)](https://github.com/Sabin2003/LangChain_da/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.9%20%7C%203.10%20%7C%203.11%20%7C%203.12-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Type-checked: pyright strict](https://img.shields.io/badge/types-pyright%20strict-blueviolet.svg)](https://microsoft.github.io/pyright/)

**Production-grade RabbitMQ integration for [LangChain](https://www.langchain.com/).**
A first-class set of typed `BaseTool` and `BaseToolkit` implementations that let
an LLM agent fully administer a RabbitMQ broker — declaring queues and exchanges,
publishing/consuming messages, binding, acknowledging, and monitoring the cluster.

The package follows the same conventions as the official `langchain-community`
integrations (Pinecone, Redis, Weaviate, Elasticsearch) so it can be merged
upstream with no changes.

---

## Features

| Category | Tools |
|---|---|
| **Queue management** | `declare_queue` · `delete_queue` · `purge_queue` · `bind_queue` · `unbind_queue` · `get_queue_info` |
| **Exchange management** | `declare_exchange` · `delete_exchange` · `bind_exchange` |
| **Message operations** | `publish_message` (sync + async) · `consume_message` · `ack_message` · `nack_message` · `reject_message` |
| **Monitoring** | `check_health` · `get_connection_info` · `close_connection` · `list_queues` · `list_exchanges` · `list_bindings` · `get_node_stats` |

* **Sync & async** support via `pika.BlockingConnection` and `aio_pika.connect_robust`.
* **SSL/TLS** support with certificate validation, custom CA bundles and client certs.
* **Strict typing** — passes `pyright --strict` over `src/`.
* **Pydantic v2** schemas validate every tool call before any AMQP traffic.
* **Tenacity retries** with exponential backoff on transient broker errors.
* **Typed exception hierarchy** (`RabbitMQToolException` and subclasses).
* **Configuration via environment variables only** — twelve-factor friendly.
* **AgentExecutor & LCEL ready** — the toolkit returns vanilla `BaseTool`s.

## Installation

```bash
pip install langchain-rabbitmq
```

From source (editable, with tests & lint extras):

```bash
git clone https://github.com/Sabin2003/LangChain_da.git
cd LangChain_da
make install
```

## Quick start

```python
from langchain_rabbitmq import RabbitMQToolkit

# Reads RABBITMQ_* env vars (host, port, credentials, TLS, ...)
toolkit = RabbitMQToolkit.from_env()
tools = toolkit.get_tools()

for tool in tools:
    print(tool.name, "—", tool.description.split('.')[0])
```

Use the tools with any LangChain agent:

```python
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

prompt = ChatPromptTemplate.from_messages([
    ("system", "You are a RabbitMQ operations assistant."),
    ("human", "{input}"),
    MessagesPlaceholder("agent_scratchpad"),
])

agent = create_tool_calling_agent(llm, tools, prompt)
executor = AgentExecutor(agent=agent, tools=tools)

executor.invoke({"input": "Create a durable queue 'orders' and publish a test message."})
```

## Configuration

All configuration comes from environment variables (read by `RabbitMQConfig.from_env()`):

| Variable | Default | Purpose |
|---|---|---|
| `RABBITMQ_URL` | _unset_ | Full AMQP(S) URL. Overrides the granular vars. |
| `RABBITMQ_HOST` | `localhost` | Broker host. |
| `RABBITMQ_PORT` | `5672` (`5671` w/ TLS) | Broker port. |
| `RABBITMQ_VHOST` | `/` | Virtual host. |
| `RABBITMQ_USERNAME` | `guest` | AMQP username. |
| `RABBITMQ_PASSWORD` | `guest` | AMQP password. |
| `RABBITMQ_SSL` | `false` | Enable TLS. |
| `RABBITMQ_SSL_CA_CERTS` | _unset_ | Path to CA bundle. |
| `RABBITMQ_SSL_CERTFILE` | _unset_ | Client certificate. |
| `RABBITMQ_SSL_KEYFILE` | _unset_ | Client private key. |
| `RABBITMQ_SSL_VERIFY` | `true` | Verify peer certificate. |
| `RABBITMQ_CONNECTION_TIMEOUT` | `10.0` | Connection timeout (seconds). |
| `RABBITMQ_HEARTBEAT` | `60` | Heartbeat interval (seconds). |
| `RABBITMQ_MANAGEMENT_URL` | derived | HTTP API URL for monitoring tools. |
| `RABBITMQ_MANAGEMENT_USERNAME` | falls back to `RABBITMQ_USERNAME` | Management UI user. |
| `RABBITMQ_MANAGEMENT_PASSWORD` | falls back to `RABBITMQ_PASSWORD` | Management UI password. |

## Architecture

```
src/langchain_rabbitmq/
├── __init__.py        — Public re-exports
├── config.py          — RabbitMQConfig (Pydantic v2, env loader)
├── exceptions.py      — Typed exception hierarchy
├── models.py          — Pydantic args_schema for every tool
├── utilities.py       — SyncConnectionManager / AsyncConnectionManager
├── toolkit.py         — RabbitMQToolkit (BaseToolkit)
└── tools/
    ├── base.py        — BaseRabbitMQTool / BaseAsyncRabbitMQTool
    ├── queue_tools.py
    ├── exchange_tools.py
    ├── message_tools.py
    └── monitoring_tools.py
```

The toolkit holds a single sync (and a single async) connection manager and
hands them to every tool, so the agent reuses one connection across calls.

## Development

```bash
make install            # editable install + dev extras
make lint               # ruff
make typecheck          # pyright --strict
make security           # bandit
make test               # unit tests + coverage report
make test-integration   # tests against testcontainers RabbitMQ
make test-e2e           # AgentExecutor end-to-end tests
make test-load          # 1 000-message throughput test
make docs               # build MkDocs site
```

CI runs the full matrix on **Linux, macOS and Windows × Python 3.9, 3.10, 3.11, 3.12**.

## Cookbooks

* [`cookbooks/basic_agent.py`](cookbooks/basic_agent.py) — minimal AgentExecutor example.
* [`cookbooks/async_agent.py`](cookbooks/async_agent.py) — async publishing & consumption.
* [`cookbooks/rpc.py`](cookbooks/rpc.py) — request/reply RPC pattern using a temporary
  reply queue and `correlation_id`.
* [`cookbooks/routing.py`](cookbooks/routing.py) — topic exchange routing.

## License

MIT — see [`LICENSE`](LICENSE).

## Contributing

Issues and pull requests are welcome. Please run `make lint typecheck security test`
before submitting a PR. See [`CONTRIBUTING.md`](CONTRIBUTING.md) for details.
