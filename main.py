"""
Main application entry point for the Hugging Face Agents Course Final Assignment.
"""

from typing import TypedDict, Optional

import json
import base64
from hf_client import HFClient

from langchain_core.messages import (
    AnyMessage,
    ToolMessage,
    SystemMessage,
    HumanMessage,
)
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, START, END
from langfuse.callback import CallbackHandler

from utils import load_prompt
from tools import query_resource, search_web, search_arxiv
from config import (
    BASE_URL,
    QUESTIONS_JSON_PATH,
    PREVIOUS_ANSWERS_JSON_PATH,
    ATTACHMENTS_DIR,
    LANGFUSE_SECRET_KEY,
    LANGFUSE_PUBLIC_KEY,
    LANGFUSE_HOST,
    USERNAME,
    AGENT_CODE,
)

recursion_limit = 20

langfuse_handler = CallbackHandler(
    secret_key=LANGFUSE_SECRET_KEY, public_key=LANGFUSE_PUBLIC_KEY, host=LANGFUSE_HOST
)

TRIAGE_SYSTEM_PROMPT = load_prompt("triage_system_prompt.md")
PLANNING_SYSTEM_PROMPT = load_prompt("planning_system_prompt.md")
TASK_SUMMARIZATION_SYSTEM_PROMPT = load_prompt("task_summarization_prompt.md")
EXECUTION_SYSTEM_PROMPT = load_prompt("execution_system_prompt.md")
FORMAT_ANSWER_SYSTEM_PROMPT = load_prompt("format_answer_system_prompt.md")


@tool(parse_docstring=True)
def final_answer(answer: str):
    """
    Final answer to the question.

    Args:
        answer: The answer to the question.
    """
    pass


@tool(parse_docstring=True)
def delegate_to_research_agent():
    """
    Delegates the question to a research agent if the question cannot be answered with the provided information.
    """
    pass


tools = [
    query_resource,
    search_web,
    search_arxiv,
    final_answer,
]
tools_by_name = {tool.name: tool for tool in tools}

triage_model = ChatOpenAI(model="o4-mini")
planning_model = ChatOpenAI(model="gpt-4.1")
tool_calling_model = ChatOpenAI(model="gpt-4.1-mini")
task_summarization_model = ChatOpenAI(model="gpt-4.1")
format_answer_model = ChatOpenAI(model="gpt-4.1-mini")


class AgentState(TypedDict):

    messages: list[AnyMessage]
    proposed_answer: Optional[str]
    final_answer: Optional[str]
    question: str


def triage_node(state: AgentState):
    triage_tools = [final_answer, delegate_to_research_agent]
    response = triage_model.bind_tools(triage_tools, tool_choice="any").invoke(
        [
            SystemMessage(content=TRIAGE_SYSTEM_PROMPT),
            HumanMessage(content=state["question"]),
        ]
    )

    if response.tool_calls and response.tool_calls[0]["name"] == "final_answer":
        return {
            "messages": state["messages"],
            "question": state["question"],
            "proposed_answer": response.tool_calls[0]["args"]["answer"],
        }
    else:
        # delegate_to_research_agent was called or no tool was called
        # Pass original state through to next node
        return state


def plan(state: AgentState):
    response = planning_model.invoke(
        [
            SystemMessage(content=PLANNING_SYSTEM_PROMPT),
            HumanMessage(content=state["question"]),
        ]
    )
    return {
        "messages": [HumanMessage(content=state["question"])] + [response],
        "question": state["question"],
        "proposed_answer": state.get("proposed_answer"),
    }


def tool_node(state: AgentState):

    response = tool_calling_model.bind_tools(tools, tool_choice="any").invoke(
        state["messages"] + [SystemMessage(EXECUTION_SYSTEM_PROMPT)],
    )

    tool_calls = response.tool_calls

    outputs = [response]
    for tool_call in tool_calls:
        if tool_call["name"] == "final_answer":
            return {
                "messages": state["messages"] + [tool_call],
                "question": state["question"],
                "proposed_answer": tool_call["args"]["answer"],
            }

        tool_result = tools_by_name[tool_call["name"]].invoke(tool_call["args"])
        outputs.append(
            ToolMessage(
                content=json.dumps(tool_result),
                name=tool_call["name"],
                tool_call_id=tool_call["id"],
            )
        )

    return {
        "messages": state["messages"] + outputs,
        "question": state["question"],
        "proposed_answer": state.get("proposed_answer"),
    }


def evaluate(
    state: AgentState,
):
    response = task_summarization_model.invoke(
        state["messages"] + [SystemMessage(TASK_SUMMARIZATION_SYSTEM_PROMPT)]
    )

    return {
        "messages": state["messages"] + [response],
        "question": state["question"],
        "proposed_answer": state.get("proposed_answer"),
    }


def format_answer(state: AgentState):
    response = format_answer_model.invoke(
        [
            SystemMessage(content=FORMAT_ANSWER_SYSTEM_PROMPT),
            HumanMessage(
                content=f"USER_QUESTION: {state["question"]}\n\nLONG_FORM_ANSWER: {state["proposed_answer"]}"
            ),
        ]
    )
    return {
        "messages": state["messages"],
        "question": state["question"],
        "proposed_answer": state.get("proposed_answer"),
        "final_answer": response.content,
    }


workflow = StateGraph(AgentState)

workflow.add_node("Triage", triage_node)
workflow.add_node("Set Action Plan", plan)
workflow.add_node("Call tool", tool_node)
workflow.add_node("Evaluate Outcome", evaluate)
workflow.add_node("Format Answer", format_answer)

workflow.add_edge(START, "Triage")
workflow.add_conditional_edges(
    "Triage",
    lambda state: (
        "Answer Proposed" if state.get("proposed_answer") is not None else "Continue"
    ),
    {"Answer Proposed": "Format Answer", "Continue": "Set Action Plan"},
)
workflow.add_edge("Set Action Plan", "Call tool")
workflow.add_conditional_edges(
    "Call tool",
    lambda state: (
        "Answer Proposed" if state.get("proposed_answer") is not None else "Continue"
    ),
    {"Answer Proposed": "Format Answer", "Continue": "Evaluate Outcome"},
)
workflow.add_edge("Evaluate Outcome", "Call tool")
workflow.add_edge("Format Answer", END)

agent = workflow.compile().with_config(config={"callbacks": [langfuse_handler]})

graph_mermaid = agent.get_graph().draw_mermaid()
with open("graph.md", "w") as f:
    f.write("```mermaid\n")
    f.write(graph_mermaid)
    f.write("```")


def main():
    hf = HFClient(
        base_url=BASE_URL,
        questions_json_path=QUESTIONS_JSON_PATH,
        attachments_dir=ATTACHMENTS_DIR,
    )
    questions = hf.get_questions()

    answers = list(
        map(
            lambda question: {
                "task_id": question["task_id"],
                "submitted_answer": "This is a default answer.",
            },
            questions,
        )
    )

    # Check if any question has 'only': true
    only_questions = [q for q in questions if q.get("only", False)]
    if only_questions:
        questions = [only_questions[0]]
    else:
        questions = [q for q in questions if not q.get("skip")]

    for question in questions:
        print("\n---\n")
        expected_answer = question.get("answer")
        print(f"❓ {question['question']} (Expected answer: {expected_answer})")
        content = [{"type": "text", "text": question["question"]}]
        file_path = question["file_path"]
        if file_path.endswith(
            (".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tiff", ".webp")
        ):
            print(f"Attaching image file: {file_path}")
            with open(file_path, "rb") as image_file:
                encoded_image = base64.b64encode(image_file.read()).decode("utf-8")
                content.append(
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{encoded_image}"},
                    }
                )
        try:
            print("🤖 Invoking agent...")
            response = agent.invoke(
                {
                    "messages": [HumanMessage(content=content)],
                    "question": question["question"],
                    "proposed_answer": None,
                    "final_answer": None,
                },
                config={"recursion_limit": recursion_limit},
            )
            answer = response["final_answer"]
            # Update answer in existing list instead of appending a new entry
            for ans in answers:
                if ans["task_id"] == question["task_id"]:
                    ans["submitted_answer"] = answer
                    break
            if expected_answer:
                print(f"{"✅" if answer == expected_answer else "❌"} {answer}")
            else:
                print(f"🙋🏻 {answer}")

        except Exception as e:
            print(f"🚨 {e}")

    # Write the answers to a JSON file for reference
    print("\nSaving answers locally...")
    with open(PREVIOUS_ANSWERS_JSON_PATH, "w") as f:
        json.dump(answers, f, indent=2)
    print("Answers saved successfully.")

    print("\nSubmitting answers to the API...")
    submission_response = hf.submit_answers(USERNAME, AGENT_CODE, answers)
    print("\nSubmission result:")
    print(submission_response)


if __name__ == "__main__":
    main()
