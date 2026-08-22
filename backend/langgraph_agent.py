"""
Knowtis LangGraph Multi-Agent Architecture
Agnes (AI Academic Supervisor) + Specialist Worker Agents (Search, Event Scheduler, Study Planner)

Configured for Knowtis Academic Catch-Up & Study Management Platform.
"""

import sys
import os
import re
import json
import operator
from typing import Annotated, Sequence, TypedDict, Dict, Any, List, Optional
from datetime import datetime

# Path setup to import backend modules if executed as standalone or from backend
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)
BACKEND_DIR = os.path.join(ROOT_DIR, "backend")
if os.path.exists(BACKEND_DIR) and BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

# Load environment variables
from dotenv import load_dotenv
env_path = os.path.join(ROOT_DIR, ".env")
if os.path.exists(env_path):
    load_dotenv(env_path)
else:
    load_dotenv()

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage, AIMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import END, StateGraph
from langgraph.checkpoint.memory import MemorySaver

# Attempt to load backend services if available
DB_AVAILABLE = False
try:
    from app.config import settings
    from app.database import SessionLocal
    from app.services.ai_agent_service import AIAgentService
    from app.services.ai_tools import AIToolEngine, TOOL_SYSTEM_PROMPT
    DB_AVAILABLE = True
except Exception as e:
    DB_AVAILABLE = False


# =====================================================================
# 1. MODEL CLIENT SETUP
# =====================================================================

def create_llm_client(is_supervisor: bool = False) -> ChatOpenAI:
    """Initialize ChatOpenAI pointing to Groq, Agnes, or standard OpenAI endpoints."""
    groq_key = os.getenv("GROQ_API_KEY", "")
    groq_url = os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1")
    agnes_key = os.getenv("AGNES_API_KEY", "")
    agnes_url = os.getenv("AGNES_BASE_URL", "https://apihub.agnes-ai.com/v1")
    openai_key = os.getenv("OPENAI_API_KEY", "")

    if groq_key and groq_key != "gsk_dummy":
        model_name = os.getenv("AI_PREMIUM_MODEL", "llama-3.3-70b-versatile") if is_supervisor else os.getenv("AI_FREE_MODEL", "llama-3.1-8b-instant")
        return ChatOpenAI(
            base_url=groq_url,
            api_key=groq_key,
            model=model_name,
            temperature=0.4,
            timeout=60,
        )
    elif agnes_key:
        model_name = os.getenv("AGNES_MODEL", "agnes-2.0-flash")
        return ChatOpenAI(
            base_url=agnes_url,
            api_key=agnes_key,
            model=model_name,
            temperature=0.3,
            timeout=30,
        )
    elif openai_key:
        model_name = "gpt-4o-mini" if is_supervisor else "gpt-3.5-turbo"
        return ChatOpenAI(
            api_key=openai_key,
            model=model_name,
            temperature=0.4,
            timeout=60,
        )
    else:
        # Fallback dummy configuration
        return ChatOpenAI(
            base_url="https://api.groq.com/openai/v1",
            api_key="disabled",
            model="llama-3.3-70b-versatile",
            temperature=0.4,
            timeout=10,
        )

try:
    supervisor_llm = create_llm_client(is_supervisor=True)
    worker_llm = create_llm_client(is_supervisor=False)
except Exception as exc:
    supervisor_llm = None
    worker_llm = None


# =====================================================================
# 2. LANGGRAPH AGENT STATE DEFINITION
# =====================================================================

class KnowtisAgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], operator.add]
    user_id: str
    course_code: Optional[str]
    current_agent: str
    academic_context: Dict[str, Any]
    next_step: str
    final_answer: str


# =====================================================================
# 3. SPECIALIST AGENT NODES
# =====================================================================

def supervisor_node(state: KnowtisAgentState) -> Dict[str, Any]:
    """Agnes AI Supervisor: Analyzes request, selects specialist agent or answers directly."""
    query = ""
    for msg in reversed(state["messages"]):
        if isinstance(msg, HumanMessage):
            query = msg.content
            break

    query_lower = query.lower()

    if any(k in query_lower for k in ["deadline", "exam", "test", "schedule", "when", "due"]):
        next_step = "scheduler_agent"
    elif any(k in query_lower for k in ["plan", "timetable", "study", "catch up", "prepare", "revision"]):
        next_step = "study_planner_agent"
    elif any(k in query_lower for k in ["search", "find", "what is", "explain", "notes", "summary"]):
        next_step = "search_agent"
    else:
        next_step = "direct_answer"

    return {
        "current_agent": "supervisor",
        "next_step": next_step,
    }


def scheduler_agent_node(state: KnowtisAgentState) -> Dict[str, Any]:
    """Specialist Agent: Academic Event & Deadline Manager."""
    query = state["messages"][-1].content
    user_id = state.get("user_id", "")
    course_code = state.get("course_code")

    context_str = ""
    if DB_AVAILABLE and user_id:
        db = SessionLocal()
        try:
            res = AIToolEngine.query_academic_schedule(user_id=user_id, course_code=course_code, limit=5, db=db)
            context_str = json.dumps(res, default=str)
        finally:
            db.close()

    prompt = f"You are the Knowtis Academic Schedule Specialist. Answer the user's query using schedule context.\nContext: {context_str}\nQuery: {query}"
    
    if worker_llm:
        response = worker_llm.invoke([SystemMessage(content=prompt)])
        answer = response.content
    else:
        answer = f"Found schedule information: {context_str or 'No upcoming deadlines found.'}"

    return {
        "messages": [AIMessage(content=answer)],
        "current_agent": "scheduler_agent",
        "final_answer": answer,
    }


def study_planner_agent_node(state: KnowtisAgentState) -> Dict[str, Any]:
    """Specialist Agent: Catch-Up & Revision Timetable Planner."""
    query = state["messages"][-1].content
    user_id = state.get("user_id", "")
    course_code = state.get("course_code")

    context_str = ""
    if DB_AVAILABLE and user_id:
        db = SessionLocal()
        try:
            res = AIToolEngine.get_study_catchup_plan(user_id=user_id, course_code=course_code, db=db)
            context_str = json.dumps(res, default=str)
        finally:
            db.close()

    prompt = f"You are the Knowtis Study Planner Specialist. Create an actionable revision plan.\nContext: {context_str}\nQuery: {query}"

    if worker_llm:
        response = worker_llm.invoke([SystemMessage(content=prompt)])
        answer = response.content
    else:
        answer = f"Generated study plan context: {context_str or 'Review key lecture notes for your upcoming courses.'}"

    return {
        "messages": [AIMessage(content=answer)],
        "current_agent": "study_planner_agent",
        "final_answer": answer,
    }


def search_agent_node(state: KnowtisAgentState) -> Dict[str, Any]:
    """Specialist Agent: Academic Knowledge Search."""
    query = state["messages"][-1].content
    user_id = state.get("user_id", "")

    context_str = ""
    if DB_AVAILABLE and user_id:
        db = SessionLocal()
        try:
            res = AIToolEngine.search_course_materials(query=query, user_id=user_id, db=db)
            context_str = json.dumps(res, default=str)
        finally:
            db.close()

    prompt = f"You are the Knowtis Academic Search Specialist. Synthesize search context into a concise answer.\nContext: {context_str}\nQuery: {query}"

    if worker_llm:
        response = worker_llm.invoke([SystemMessage(content=prompt)])
        answer = response.content
    else:
        answer = f"Search results: {context_str or 'No relevant materials found for your query.'}"

    return {
        "messages": [AIMessage(content=answer)],
        "current_agent": "search_agent",
        "final_answer": answer,
    }


def direct_answer_node(state: KnowtisAgentState) -> Dict[str, Any]:
    """Agnes AI Supervisor Direct Conversational Response."""
    query = state["messages"][-1].content
    prompt = f"You are Agnes, the friendly AI Academic Supervisor for Knowtis. Assist the student clearly.\nQuery: {query}"

    if supervisor_llm:
        response = supervisor_llm.invoke([SystemMessage(content=prompt)])
        answer = response.content
    else:
        answer = f"Hello! I'm Agnes, your Knowtis academic assistant. How can I help you with your courses today?"

    return {
        "messages": [AIMessage(content=answer)],
        "current_agent": "supervisor_direct",
        "final_answer": answer,
    }


# =====================================================================
# 4. BUILD LANGGRAPH WORKFLOW
# =====================================================================

workflow = StateGraph(KnowtisAgentState)

workflow.add_node("supervisor", supervisor_node)
workflow.add_node("scheduler_agent", scheduler_agent_node)
workflow.add_node("study_planner_agent", study_planner_agent_node)
workflow.add_node("search_agent", search_agent_node)
workflow.add_node("direct_answer", direct_answer_node)

workflow.set_entry_point("supervisor")

workflow.add_conditional_edges(
    "supervisor",
    lambda state: state["next_step"],
    {
        "scheduler_agent": "scheduler_agent",
        "study_planner_agent": "study_planner_agent",
        "search_agent": "search_agent",
        "direct_answer": "direct_answer",
    }
)

workflow.add_edge("scheduler_agent", END)
workflow.add_edge("study_planner_agent", END)
workflow.add_edge("search_agent", END)
workflow.add_edge("direct_answer", END)

memory = MemorySaver()
agent_app = workflow.compile(checkpointer=memory)


# =====================================================================
# 5. PUBLIC INTERFACE FUNCTION
# =====================================================================

def run_knowtis_agent(
    query: str,
    user_id: str = "anonymous",
    course_code: Optional[str] = None,
    thread_id: str = "default_thread",
) -> Dict[str, Any]:
    """
    Main invocation point for the Knowtis LangGraph Agent.
    """
    initial_state: KnowtisAgentState = {
        "messages": [HumanMessage(content=query)],
        "user_id": str(user_id),
        "course_code": course_code,
        "current_agent": "supervisor",
        "academic_context": {},
        "next_step": "supervisor",
        "final_answer": "",
    }

    config = {"configurable": {"thread_id": thread_id}}

    try:
        final_state = agent_app.invoke(initial_state, config=config)
        answer = final_state.get("final_answer") or (
            final_state["messages"][-1].content if final_state.get("messages") else "Request processed."
        )
        return {
            "status": "success",
            "query": query,
            "answer": answer,
            "agent": final_state.get("current_agent", "supervisor"),
        }
    except Exception as e:
        return {
            "status": "error",
            "query": query,
            "answer": f"I processed your query: '{query}'. How else can I assist you with your academic schedule?",
            "error": str(e),
        }
