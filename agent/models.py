"""Pydantic models for structured agent data."""

from typing import Any

from pydantic import BaseModel, Field


class AgentResponse(BaseModel):
    """Structured response returned by the portfolio analytics agent.

    Carries both the user-facing answer and internal trace metadata
    used by the Streamlit UI and the evaluator.
    """

    answer: str = Field(..., description="The final text answer to show the user")
    tool_used: str | None = Field(None, description="Which tool was called")
    tool_input: dict[str, Any] | None = Field(
        None, description="Parameters passed to the tool"
    )
    tool_output: str | None = Field(None, description="Raw output from the tool")
    sql_query: str | None = Field(
        None, description="Generated SQL if SQL tool was used"
    )
