"""Deterministic sector exposure calculator.

Computes the percentage weight of each sector in a portfolio's equity
holdings. No LLM is involved — the calculation is pure Python/SQL.
"""

import logging
from typing import Any

from db.connection import DatabaseManager

logger = logging.getLogger(__name__)

_PORTFOLIO_LOOKUP_SQL = """
SELECT portfolio_id, portfolio_name
FROM portfolios
WHERE LOWER(portfolio_name) LIKE '%' || LOWER(?) || '%'
"""

_ALL_PORTFOLIOS_SQL = "SELECT portfolio_name FROM portfolios ORDER BY portfolio_name"

_HOLDINGS_SQL = """
SELECT sec.sector_name, h.current_weight
FROM holdings h
JOIN securities s ON h.security_id = s.security_id
JOIN sectors sec ON s.sector_id = sec.sector_id
WHERE h.portfolio_id = ?
  AND s.asset_type = 'Stock'
"""


def _lookup_portfolio(db: DatabaseManager, name: str) -> dict[str, Any] | None:
    """Find a portfolio by fuzzy name match. Returns the first hit or None."""
    rows = db.execute_query(_PORTFOLIO_LOOKUP_SQL, (name,))
    return rows[0] if rows else None


def _available_portfolios(db: DatabaseManager) -> list[str]:
    """Return all portfolio names for helpful error messages."""
    rows = db.execute_query(_ALL_PORTFOLIOS_SQL)
    return [r["portfolio_name"] for r in rows]


def calculate_sector_exposure(portfolio_name: str) -> str:
    """Calculate the sector exposure breakdown for a specific portfolio.

    Queries equity holdings, groups by sector, normalises weights to
    percentages that sum to 100%, and returns a formatted string.

    Args:
        portfolio_name: Full or partial name of the target portfolio.

    Returns:
        A formatted breakdown string, or an error message.
    """
    db = DatabaseManager()

    portfolio = _lookup_portfolio(db, portfolio_name)
    if portfolio is None:
        names = _available_portfolios(db)
        names_list = "\n".join(f"- {n}" for n in names)
        return (
            f"Portfolio matching '{portfolio_name}' not found. "
            f"Available portfolios:\n{names_list}"
        )

    portfolio_id = portfolio["portfolio_id"]
    display_name = portfolio["portfolio_name"]

    rows = db.execute_query(_HOLDINGS_SQL, (portfolio_id,))

    if not rows:
        return f"No equity holdings found for {display_name}."

    sector_weights: dict[str, float] = {}
    for row in rows:
        weight = row["current_weight"] or 0.0
        sector = row["sector_name"]
        sector_weights[sector] = sector_weights.get(sector, 0.0) + weight

    total_weight = sum(sector_weights.values())
    if total_weight == 0:
        return f"All equity holdings in {display_name} have zero weight."

    exposures = {
        sector: (w / total_weight) * 100.0
        for sector, w in sector_weights.items()
    }

    sorted_exposures = sorted(exposures.items(), key=lambda x: x[1], reverse=True)

    lines = [f"Sector Exposure for {display_name}:"]
    for sector, pct in sorted_exposures:
        lines.append(f"  {sector}: {pct:.2f}%")

    return "\n".join(lines)
