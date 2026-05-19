"""Cookbook: minimal AgentExecutor driving the RabbitMQ toolkit.

Run with::

    OPENAI_API_KEY=... python cookbooks/basic_agent.py

Set ``RABBITMQ_HOST`` / ``RABBITMQ_*`` env vars to target your broker.
"""

from __future__ import annotations

from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_openai import ChatOpenAI  # type: ignore[import-not-found]

from langchain_rabbitmq import RabbitMQToolkit


def main() -> None:
    toolkit = RabbitMQToolkit.from_env(include_async=False)
    tools = toolkit.get_tools()

    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "You are a RabbitMQ operations assistant. Use the provided tools to "
                "manage queues, exchanges, and messages. Always confirm what you did.",
            ),
            ("human", "{input}"),
            MessagesPlaceholder("agent_scratchpad"),
        ]
    )
    agent = create_tool_calling_agent(llm, tools, prompt)
    executor = AgentExecutor(agent=agent, tools=tools, verbose=True)

    result = executor.invoke(
        {
            "input": (
                "Create a durable queue named 'orders', publish a JSON message "
                "{'sku': 'A-100', 'qty': 2} to it, then read it back and confirm."
            )
        }
    )
    print("Agent output:", result["output"])


if __name__ == "__main__":
    main()
