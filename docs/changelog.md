# Changelog

All notable changes to **langchain-rabbitmq** are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html)
from version `0.1.0` onwards.

## [0.1.0] — 2026-05-19

### Added

- Initial public release.
- Strongly typed configuration loader (`RabbitMQConfig`) sourced from `RABBITMQ_*`
  environment variables with full SSL/TLS support.
- Synchronous (`pika`) and asynchronous (`aio-pika`) connection managers with
  `tenacity`-based exponential-backoff retries on transient errors.
- LangChain `BaseTool` implementations for:
  - **Queue management**: `DeclareQueueTool`, `DeleteQueueTool`, `PurgeQueueTool`,
    `BindQueueTool`, `UnbindQueueTool`, `GetQueueInfoTool`.
  - **Exchange management**: `DeclareExchangeTool`, `DeleteExchangeTool`,
    `BindExchangeTool`.
  - **Message operations**: `PublishMessageTool`, `ConsumeMessageTool`,
    `AckMessageTool`, `NackMessageTool`, `RejectMessageTool`,
    `AsyncPublishMessageTool`.
  - **Monitoring**: `CheckHealthTool`, `GetConnectionInfoTool`,
    `CloseConnectionTool`, `ListQueuesTool`, `ListExchangesTool`,
    `ListBindingsTool`, `GetNodeStatsTool`.
- `RabbitMQToolkit` (BaseToolkit) bundling every tool for one-call agent setup.
- Pydantic v2 `args_schema` for every tool, enforcing strict input validation
  and providing rich docstrings for LLM tool selection.
- Hierarchy of typed exceptions rooted at `RabbitMQToolException`.
- Comprehensive unit-test suite (75 tests, **92%+ coverage**) using `pytest`,
  `pytest-asyncio`, `pytest-mock` and `unittest.mock`.
- Integration test suite running against `rabbitmq:3-management` via
  `testcontainers`.
- End-to-end test driving the toolkit through LangChain's `AgentExecutor`
  with a deterministic fake LLM.
- Load test publishing & consuming 1 000 messages.
- GitHub Actions CI matrix (Linux/macOS/Windows × Python 3.9–3.12) with
  `ruff`, `pyright` (strict), `bandit`, `pytest`, and a PyPI trusted-publishing
  release workflow.
- MkDocs + mkdocstrings documentation site and cookbooks (basic, async, RPC,
  routing exchanges).

[0.1.0]: https://github.com/Sabin2003/LangChain_da/releases/tag/v0.1.0
