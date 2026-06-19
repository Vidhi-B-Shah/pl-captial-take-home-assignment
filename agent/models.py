"""Pydantic models for structured agent data."""

from typing import Any

from pydantic import BaseModel, Field


class ToolTrace(BaseModel):
    """Metadata for a single tool invocation within an agent turn."""

    tool_name: str = Field(..., description="Name of the tool that was called")
    tool_input: dict[str, Any] | None = Field(
        None, description="Parameters passed to the tool"
    )
    tool_output: str | None = Field(None, description="Raw output from the tool")
    sql_query: str | None = Field(
        None, description="Generated SQL if this was the SQL tool"
    )


class AgentResponse(BaseModel):
    """Structured response returned by the portfolio analytics agent.

    Carries both the user-facing answer and internal trace metadata
    used by the Streamlit UI and the evaluator.
    """

    answer: str = Field(..., description="The final text answer to show the user")
    tool_traces: list[ToolTrace] = Field(
        default_factory=list, description="Ordered list of tool calls made"
    )

    @property
    def tool_used(self) -> str | None:
        """Last tool called (backward-compatible with evaluator)."""
        return self.tool_traces[-1].tool_name if self.tool_traces else None

    @property
    def tool_input(self) -> dict[str, Any] | None:
        """Last tool's input (backward-compatible with evaluator)."""
        return self.tool_traces[-1].tool_input if self.tool_traces else None

    @property
    def tool_output(self) -> str | None:
        """Last tool's output (backward-compatible with evaluator)."""
        return self.tool_traces[-1].tool_output if self.tool_traces else None

    @property
    def sql_query(self) -> str | None:
        """SQL from the first SQL tool call, if any."""
        for trace in self.tool_traces:
            if trace.sql_query:
                return trace.sql_query
        return None
