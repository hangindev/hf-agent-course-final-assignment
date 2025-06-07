from typing import TypedDict, Optional

import re

from langchain_core.messages import (
    SystemMessage,
    HumanMessage,
)
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, START, END
from langfuse.openai import OpenAI

from utils import load_prompt

ANALYZE_AUDIO_SYSTEM_PROMPT = load_prompt("analyze_audio_system_prompt.md")

analyze_model = ChatOpenAI(model="gpt-4o-mini")


class AgentState(TypedDict):

    file_path: str
    transcript: Optional[str]
    question: str
    answer: Optional[str]


def transcribe_audio(state: AgentState):
    client = OpenAI()

    audio_file = open(state["file_path"], "rb")

    transcription = client.audio.transcriptions.create(
        model="gpt-4o-mini-transcribe", file=audio_file
    )

    return {**state, "transcript": transcription.text}


def analyze(state: AgentState):
    response = analyze_model.invoke(
        [
            SystemMessage(content=ANALYZE_AUDIO_SYSTEM_PROMPT),
            HumanMessage(
                content=f"""
<transcript>
{state["transcript"]}
</transcript>

<query>
{state["question"]}
</query>                
""",
            ),
        ],
    )

    final_answer_pattern = r"FINAL_ANSWER:\s*(.*?)\s*$"
    match = re.search(final_answer_pattern, response.content, re.DOTALL)
    answer = match.group(1).strip() if match else response.content
    return {**state, "answer": answer}


workflow = StateGraph(AgentState)

workflow.add_node("Transcribe", transcribe_audio)
workflow.add_node("Analyze", analyze)

workflow.add_edge(START, "Transcribe")
workflow.add_edge("Transcribe", "Analyze")

workflow.add_edge("Analyze", END)

audio_agent = workflow.compile()

graph_mermaid = audio_agent.get_graph().draw_mermaid()
with open("audio_agent_graph.md", "w") as f:
    f.write("```mermaid\n")
    f.write(graph_mermaid)
    f.write("```")
