"""Portfolio analytics agent with ADK routing and session memory.

Wires together the root Agent, Runner, and InMemorySessionService so that
user messages are routed to the correct tool (SQL or exposure calculator)
and conversation history is maintained per session.
"""

import logging

from google.adk.agents import Agent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from agent.constants import AGENT_NAME, MODEL_NAME
from agent.models import AgentResponse
from agent.prompts import ROOT_AGENT_SYSTEM_PROMPT
from agent.tools.sql_tool import query_database
from agent.tools.exposure_tool import calculate_sector_exposure
from agent.tools import sql_tool

logger = logging.getLogger(__name__)


class AgentManager:
    """Manages the ADK agent lifecycle: creation, session handling, execution.

    Usage::

        manager = AgentManager()
        response = await manager.run("How many portfolios?", "user1", "sess1")
    """

    def __init__(self) -> None:
        self._agent = Agent(
            name=AGENT_NAME,
            model=MODEL_NAME,
            instruction=ROOT_AGENT_SYSTEM_PROMPT,
            tools=[query_database, calculate_sector_exposure],
        )

        self._session_service = InMemorySessionService()

        self._runner = Runner(
            agent=self._agent,
            app_name=AGENT_NAME,
            session_service=self._session_service,
            auto_create_session=True,
        )

        logger.info("AgentManager initialised (model=%s)", MODEL_NAME)

    async def run(
        self, user_message: str, user_id: str, session_id: str
    ) -> AgentResponse:
        """Send a user message through the agent and return a structured response.

        Args:
            user_message: The natural-language question from the user.
            user_id: Identifier for the user (one per browser session).
            session_id: Identifier for the conversation session.

        Returns:
            An AgentResponse with the answer and trace metadata.
        """
        content = types.Content(
            role="user", parts=[types.Part(text=user_message)]
        )

        final_text = ""
        tool_used = None
        tool_input = None
        tool_output = None

        async for event in self._runner.run_async(
            user_id=user_id,
            session_id=session_id,
            new_message=content,
        ):
            if not event.content or not event.content.parts:
                continue

            for part in event.content.parts:
                if part.function_call:
                    tool_used = part.function_call.name
                    tool_input = part.function_call.args

                if part.function_response:
                    raw = part.function_response.response
                    tool_output = str(raw) if raw else None

                if part.text and event.author == AGENT_NAME:
                    final_text = part.text

        generated_sql = sql_tool._last_generated_sql if tool_used == "query_database" else None

        return AgentResponse(
            answer=final_text or "I was unable to process your request.",
            tool_used=tool_used,
            tool_input=tool_input,
            tool_output=tool_output,
            sql_query=generated_sql,
        )
