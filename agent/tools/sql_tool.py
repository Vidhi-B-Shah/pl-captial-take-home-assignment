"""Natural-language-to-SQL tool.

Converts a user question into a SQL query via Gemini, validates it,
executes it against the portfolio database, and returns a formatted result.
"""

import logging
import re
import sqlite3
from typing import Any

from google import genai
from google.genai import types

from agent.constants import FORBIDDEN_SQL_PATTERNS, MODEL_NAME, SQL_RESULT_LIMIT
from agent.prompts import SQL_GENERATION_PROMPT
from db.connection import DatabaseManager

logger = logging.getLogger(__name__)

_last_generated_sql: str | None = None
"""Module-level store so the AgentManager can surface the SQL in traces."""


def _strip_markdown_fences(text: str) -> str:
    """Remove ```sql ... ``` wrappers that Gemini sometimes adds."""
    cleaned = re.sub(r"^```(?:sql)?\s*\n?", "", text.strip(), flags=re.IGNORECASE)
    cleaned = re.sub(r"\n?```\s*$", "", cleaned.strip())
    return cleaned.strip()


def _validate_sql(sql: str) -> str | None:
    """Return an error message if the SQL contains forbidden statements."""
    if FORBIDDEN_SQL_PATTERNS.search(sql):
        return (
            "I can only run read-only queries against the database. "
            "Please rephrase your question."
        )
    return None


def _ensure_limit(sql: str) -> str:
    """Append a safety LIMIT if the query does not already contain one."""
    if not re.search(r"\bLIMIT\b", sql, re.IGNORECASE):
        sql = sql.rstrip().rstrip(";")
        sql = f"{sql} LIMIT {SQL_RESULT_LIMIT};"
    return sql


def _format_results(rows: list[dict[str, Any]]) -> str:
    """Convert query result rows into a human-readable string."""
    if not rows:
        return "No results found for this query."

    if len(rows) == 1 and len(rows[0]) == 1:
        value = list(rows[0].values())[0]
        return f"The answer is: {value}"

    if len(rows[0]) == 1:
        key = list(rows[0].keys())[0]
        items = [str(row[key]) for row in rows]
        return "\n".join(f"- {item}" for item in items)

    columns = list(rows[0].keys())
    col_widths = [len(c) for c in columns]
    for row in rows:
        for i, col in enumerate(columns):
            col_widths[i] = max(col_widths[i], len(str(row[col])))

    header = " | ".join(c.ljust(col_widths[i]) for i, c in enumerate(columns))
    separator = "-+-".join("-" * w for w in col_widths)
    body_lines = []
    for row in rows:
        line = " | ".join(
            str(row[col]).ljust(col_widths[i]) for i, col in enumerate(columns)
        )
        body_lines.append(line)

    return "\n".join([header, separator, *body_lines])


def query_database(question: str) -> str:
    """Query the portfolio database using natural language.

    Translates the question into SQL via Gemini, validates and executes it,
    then returns a formatted result string.

    Args:
        question: A natural language question about portfolio data.

    Returns:
        A formatted string with the query results or an error message.
    """
    global _last_generated_sql
    _last_generated_sql = None

    try:
        prompt = SQL_GENERATION_PROMPT.format(question=question)

        client = genai.Client()
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=prompt,
            config=types.GenerateContentConfig(temperature=0.0),
        )

        raw_sql = response.text.strip() if response.text else ""
        sql = _strip_markdown_fences(raw_sql)
        _last_generated_sql = sql
        logger.info("Generated SQL: %s", sql)

        error = _validate_sql(sql)
        if error:
            return error

        sql = _ensure_limit(sql)

        db = DatabaseManager()
        results = db.execute_query(sql)
        return _format_results(results)

    except sqlite3.OperationalError as exc:
        logger.error("SQL execution error: %s", exc)
        return (
            "I wasn't able to find the data you're looking for. The available "
            "data covers portfolios, securities, holdings, transactions, "
            "performance metrics, and risk metrics."
        )
    except Exception as exc:
        logger.error("Unexpected error in query_database: %s", exc, exc_info=True)
        return "Something went wrong while processing your question. Please try again."
