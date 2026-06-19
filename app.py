"""Streamlit chat interface for the Portfolio Analytics Agent."""

import asyncio
import uuid
import logging

import streamlit as st
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO)

from db.connection import DatabaseManager
from db.loader import initialize_database
from agent.portfolio_agent import AgentManager

### PAGE CONFIG

st.set_page_config(
    page_title="Portfolio Analytics Agent",
    page_icon="📊",
    layout="centered",
)

### CACHED STARTUP (RUNS ONCE)

@st.cache_resource
def _init_db() -> DatabaseManager:
    db = DatabaseManager()
    initialize_database(db)
    return db


@st.cache_resource
def _init_agent() -> AgentManager:
    return AgentManager()


_init_db()
agent_manager = _init_agent()

### SESSION STATE

if "messages" not in st.session_state:
    st.session_state.messages = []
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())

USER_ID = "streamlit_user"

### HEADER

st.title("📊 Portfolio Analytics Agent")
st.caption("Ask questions about your portfolio data")

### EXAMPLE QUESTION CHIPS

EXAMPLE_QUESTIONS = [
    "How many portfolios do we have?",
    "What are the names of all active portfolios?",
    "Sector exposures for Tech Innovation Fund?",
    "Top 5 holdings by cost basis in Growth Equity Fund",
]

cols = st.columns(len(EXAMPLE_QUESTIONS))
for col, question in zip(cols, EXAMPLE_QUESTIONS):
    if col.button(question, use_container_width=True):
        st.session_state.pending_question = question

### CHAT HISTORY

def _render_trace(response_data: dict | None) -> None:
    """Show an expandable agent trace section if metadata is available."""
    if not response_data:
        return
    tool = response_data.get("tool_used")
    if not tool:
        return
    with st.expander("⚙️ Agent Trace"):
        st.markdown(f"**Tool:** `{tool}`")
        if response_data.get("sql_query"):
            st.markdown("**Generated SQL:**")
            st.code(response_data["sql_query"], language="sql")
        if response_data.get("tool_input"):
            st.markdown("**Tool Input:**")
            st.json(response_data["tool_input"])
        if response_data.get("tool_output"):
            st.markdown("**Raw Output:**")
            st.text(response_data["tool_output"])


for msg in st.session_state.messages:
    role = msg["role"]
    with st.chat_message(role):
        st.markdown(msg["content"])
        if role == "assistant":
            _render_trace(msg.get("response"))

### CHAT INPUT HANDLING

user_input = st.chat_input("Ask a question about your portfolio data...")

pending = st.session_state.pop("pending_question", None)
question = pending or user_input

if question:
    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)

    with st.chat_message("assistant"):
        with st.spinner("Analyzing..."):
            try:
                response = asyncio.run(
                    agent_manager.run(
                        question, USER_ID, st.session_state.session_id
                    )
                )
                answer = response.answer
            except Exception as exc:
                logging.getLogger(__name__).error("Agent error: %s", exc, exc_info=True)
                answer = (
                    "I wasn't able to process that query. Could you try rephrasing?"
                )
                response = None

        st.markdown(answer)
        if response:
            _render_trace(response.model_dump())

    st.session_state.messages.append({
        "role": "assistant",
        "content": answer,
        "response": response.model_dump() if response else None,
    })
    st.rerun()
