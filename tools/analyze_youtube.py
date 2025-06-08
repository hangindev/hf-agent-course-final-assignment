import base64
from typing import TypedDict, Optional, List

from utils import YouTubeVideo
from langgraph.graph import StateGraph, START, END
from langchain_core.tools import tool
from langchain_core.messages import SystemMessage, HumanMessage

from langfuse.callback import CallbackHandler
from langchain_openai import ChatOpenAI
from openai import OpenAI

from config import (
    LANGFUSE_SECRET_KEY,
    LANGFUSE_PUBLIC_KEY,
    LANGFUSE_HOST,
)
from utils import load_prompt

ANALYZE_YOUTUBE_SYSTEM_PROMPT = load_prompt("analyze_youtube_system_prompt.md")


langfuse_handler = CallbackHandler(
    secret_key=LANGFUSE_SECRET_KEY, public_key=LANGFUSE_PUBLIC_KEY, host=LANGFUSE_HOST
)


class AgentState(TypedDict):
    url: str
    question: str
    video: Optional[YouTubeVideo]
    caption: Optional[str]
    frames: List[tuple[str, str, int]]
    current_frame_index: int
    memory: list[str]
    new_memory: Optional[str]
    answer: Optional[str]


model = ChatOpenAI(model="gpt-4.1")


def generate_caption(audio_path: str) -> str:
    audio_file = open(audio_path, "rb")
    client = OpenAI()
    transcription = client.audio.transcriptions.create(
        model="gpt-4o-mini-transcribe", file=audio_file
    )
    return transcription.text


def initialize(state: AgentState) -> AgentState:
    video = YouTubeVideo(state["url"])
    video.__enter__()  # Manually enter the context
    state["video"] = video
    if video.caption is None:
        state["caption"] = "No caption found"
    else:
        state["caption"] = video.caption
    state["frames"] = list(video.generate_frames(0.2))
    state["memory"] = []
    state["current_frame_index"] = 0
    return state


@tool
def answer(answer: str) -> str:
    """
    Answer the question based on the video content.

    Args:
        answer: The answer to the question.
    """
    pass


@tool
def update_memory(note: str) -> str:
    """
    Update the memory with the new information.

    Args:
        note: The new information to update the memory with.
    """
    pass


@tool
def next_frame() -> str:
    """
    Get the next frame of the video.
    """
    pass


def feed_frame(state: AgentState) -> AgentState:
    frame_path, timestamp, _ = state["frames"][state["current_frame_index"]]
    state["current_frame_index"] += 1

    tools = [answer]
    if state["current_frame_index"] < len(state["frames"]):
        tools.append(next_frame)
        tools.append(update_memory)

    with open(frame_path, "rb") as f:
        b64_frame = base64.b64encode(f.read()).decode("utf-8")

    frame_url = f"data:image/png;base64,{b64_frame}"

    response = model.bind_tools(tools, tool_choice="any").invoke(
        [
            SystemMessage(content=ANALYZE_YOUTUBE_SYSTEM_PROMPT),
            HumanMessage(
                content=[
                    {
                        "type": "text",
                        "text": f"""<TITLE>
{state["video"].title}
</TITLE>

<DESCRIPTION>
{state["video"].description}
</DESCRIPTION>

<CAPTION>
{state["caption"]}
</CAPTION>

{f'''<MEMORY>
{chr(10).join(f"- {note}" for note in state["memory"])}
</MEMORY>''' if state["memory"] else ""}

<QUERY>
{state["question"]}
</QUERY>

The attached frame is from the video at timestamp: {timestamp}""",
                    },
                    {
                        "type": "image_url",
                        "image_url": {"url": frame_url, "detail": "auto"},
                    },
                ]
            ),
        ]
    )

    if response.tool_calls:
        for tool_call in response.tool_calls:
            if tool_call["name"] == "answer":
                state["answer"] = tool_call["args"]["answer"]
            elif tool_call["name"] == "update_memory":
                state["new_memory"] = tool_call["args"]["note"]

    return state


def update_memory_in_state(state: AgentState) -> AgentState:
    if state.get("new_memory"):
        state["memory"].append(state["new_memory"])

    state["new_memory"] = None
    return state


def cleanup(state: AgentState) -> AgentState:
    video = state.get("video")
    if video:
        video.__exit__(None, None, None)
    return state


def should_continue(state: AgentState):
    if state.get("answer"):
        return "Answer"
    if state.get("new_memory"):
        return "New Information"
    return "Feed Frame"


workflow = StateGraph(AgentState)

workflow.add_node("Initialize", initialize)
workflow.add_node("Feed Frame", feed_frame)
workflow.add_node("Update Memory", update_memory_in_state)
workflow.add_node("Cleanup", cleanup)

workflow.add_edge(START, "Initialize")
workflow.add_edge("Initialize", "Feed Frame")
workflow.add_conditional_edges(
    "Feed Frame",
    should_continue,
    {
        "Feed Frame": "Feed Frame",
        "New Information": "Update Memory",
        "Answer": "Cleanup",
    },
)
workflow.add_edge("Update Memory", "Feed Frame")
workflow.add_edge("Cleanup", END)

youtube_analyst = workflow.compile()

graph_mermaid = youtube_analyst.get_graph().draw_mermaid()
with open("youtube_analyst.md", "wb") as f:
    f.write("```mermaid\n".encode("utf-8"))
    f.write(graph_mermaid.encode("utf-8"))
    f.write("```".encode("utf-8"))

analyze_youtube = youtube_analyst

if __name__ == "__main__":
    result = youtube_analyst.invoke(
        {
            "url": "https://www.youtube.com/watch?v=L1vXCYZAYYM",
            "question": "In the video https://www.youtube.com/watch?v=L1vXCYZAYYM, what is the highest number of bird species to be on camera simultaneously?",
            "memory": [],
        },
        config={"recursion_limit": 50, "callbacks": [langfuse_handler]},
    )
    print(result.get("answer"))
