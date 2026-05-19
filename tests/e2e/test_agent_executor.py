"""End-to-end tests exercising the toolkit through ``AgentExecutor``.

A deterministic fake LLM drives the agent so the test does not depend on any
external model API. The agent is instructed to declare a queue, publish a
message and read it back.
"""

from __future__ import annotations

import json
import uuid

import pytest
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from langchain_rabbitmq import RabbitMQConfig, RabbitMQToolkit

pytestmark = [pytest.mark.e2e, pytest.mark.usefixtures("rabbitmq_env")]


def _agent_messages(queue: str) -> list[AIMessage]:
    """Pre-canned agent decisions for a tool-calling LLM."""

    return [
        AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "rabbitmq_declare_queue",
                    "args": {"queue": queue, "durable": False},
                    "id": "1",
                    "type": "tool_call",
                }
            ],
        ),
        AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "rabbitmq_publish_message",
                    "args": {
                        "routing_key": queue,
                        "json_body": {"hello": "world"},
                        "persistent": False,
                    },
                    "id": "2",
                    "type": "tool_call",
                }
            ],
        ),
        AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "rabbitmq_consume_message",
                    "args": {"queue": queue, "max_messages": 1, "auto_ack": True},
                    "id": "3",
                    "type": "tool_call",
                }
            ],
        ),
        AIMessage(content="done"),
    ]


def test_agent_executor_drives_rabbitmq_tools(
    rabbitmq_env: None,  # noqa: ARG001 - fixture side-effect
) -> None:
    queue = f"e2e-{uuid.uuid4().hex[:8]}"
    toolkit = RabbitMQToolkit(config=RabbitMQConfig.from_env(), include_async=False)
    tools = toolkit.get_tools()

    llm = GenericFakeChatModel(messages=iter(_agent_messages(queue)))
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", "You manage RabbitMQ via tools."),
            ("human", "{input}"),
            MessagesPlaceholder("agent_scratchpad"),
        ]
    )
    agent = create_tool_calling_agent(llm, tools, prompt)
    executor = AgentExecutor(agent=agent, tools=tools, max_iterations=6)
    result = executor.invoke(
        {"input": f"Create queue {queue}, publish a JSON message, consume it."}
    )
    assert result["output"] == "done"

    # Cleanup: delete the queue using the toolkit's delete tool.
    delete = next(t for t in tools if t.name == "rabbitmq_delete_queue")
    out = json.loads(delete.invoke({"queue": queue}))
    assert out["queue"] == queue
