import requests
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage
from typing import Any

class Gemma4Chat(BaseChatModel):
    url: str
    temperature: float
    max_tokens: int

    @property
    def _llm_type(self) -> str:
        return "Gemma4"

    def _generate(self, messages, stop=None, **kwargs):
        payload = {
            "messages": [
                {
                    "role": "system" if m.type == "system" 
                    else "user" if m.type == "user" or m.type == "human" 
                    else "assistant",
                    "content": m.content,
                }
                for m in messages
            ],
            "temperature": kwargs.get("temperature", 0.7),
            "max_tokens": kwargs.get("max_tokens", 256),
        }

        print("temperature", payload["temperature"])
        print("max_tokens", payload["max_tokens"])
        for m in messages:
            print("type", m.type, m.content)
        response = requests.post(self.url, json=payload)
        text = response.json()["response"]

        from langchain_core.outputs import ChatGeneration, ChatResult

        return ChatResult(
            generations=[
                ChatGeneration(
                    message=AIMessage(content=text)
                )
            ]
        )

llm = Gemma4Chat(
    url="https://pushkarsharma-rtm--gemma-chess-backend-api.modal.run"
)   

from langchain.agents import create_agent, AgentState
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph.message import REMOVE_ALL_MESSAGES
from langchain.agents.middleware import before_model
from langgraph.runtime import Runtime
from langchain_core.messages import SystemMessage


@before_model
def trim_messages(state: AgentState, runtime: Runtime) -> dict[str, Any] | None:
    """Keep only last few messages"""

    messages = state["messages"]

    if len(message) <= 10:
        return None
    
    return {
        "messages": messages[:10]
    }

@before_model
def add_system_prompt(state, runtime):
    return {
        "messages": [
            SystemMessage(content="You are dommy mommy")
        ] + state["messages"]
    }


agent = create_agent(
    model=llm,
    tools=[],
    checkpointer=InMemorySaver(),
    middleware=[trim_messages, add_system_prompt]
)
thread_config = {"configurable": {"thread_id": "1"}}

while True:
    print("Enter a message (or 'exit' to quit):")
    user = input("User: ")
    if user.lower() == "exit":
        break


    result = agent.invoke(
        {
            "messages": [

            {
                "role": "user",
                "content": user
            }
        ],
        "temperature": 0.8,
        "max_tokens": 100,
    },
    config=thread_config
)

    print(result["messages"][-1].content)