"""Load CSV data into SQLite. Runs once at startup."""

import logging
from pathlib import Path

import pandas as pd

from db.connection import DatabaseManager

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
SCHEMA_PATH = PROJECT_ROOT / "database_schema.sql"

# Ordered by foreign-key dependencies so parent tables load first.
CSV_TABLE_MAP: list[tuple[str, str]] = [
    ("sectors.csv", "sectors"),
    ("securities.csv", "securities"),
    ("benchmarks.csv", "benchmarks"),
    ("portfolios.csv", "portfolios"),
    ("holdings.csv", "holdings"),
    ("transactions.csv", "transactions"),
    ("historical_prices.csv", "historical_prices"),
    ("portfolio_performance.csv", "portfolio_performance"),
    ("risk_metrics.csv", "risk_metrics"),
]


def initialize_database(db_manager: DatabaseManager) -> None:
    """Create tables from schema and load all CSV data into SQLite.

    Args:
        db_manager: The shared DatabaseManager instance.
    """
    _create_schema(db_manager)
    _load_csvs(db_manager)
    _validate_tables(db_manager)


def _create_schema(db_manager: DatabaseManager) -> None:
    """Read and execute the SQL schema file."""
    if not SCHEMA_PATH.exists():
        logger.error("Schema file not found at %s", SCHEMA_PATH)
        raise FileNotFoundError(f"Schema file not found: {SCHEMA_PATH}")

    schema_sql = SCHEMA_PATH.read_text(encoding="utf-8")
    db_manager.execute_script(schema_sql)
    logger.info("Database schema created from %s", SCHEMA_PATH.name)


def _load_csvs(db_manager: DatabaseManager) -> None:
    """Load each CSV into its corresponding SQLite table."""
    conn = db_manager.get_connection()

    for csv_filename, table_name in CSV_TABLE_MAP:
        csv_path = DATA_DIR / csv_filename
        if not csv_path.exists():
            logger.warning("CSV not found, skipping: %s", csv_path)
            continue

        df = pd.read_csv(csv_path)
        df.to_sql(table_name, conn, if_exists="replace", index=False)
        logger.info("Loaded %d rows into '%s' from %s", len(df), table_name, csv_filename)


def _validate_tables(db_manager: DatabaseManager) -> None:
    """Log row counts for every loaded table as a sanity check."""
    for _, table_name in CSV_TABLE_MAP:
        try:
            rows = db_manager.execute_query(f"SELECT COUNT(*) AS cnt FROM {table_name}")
            count = rows[0]["cnt"] if rows else 0
            logger.info("Validation — %s: %d rows", table_name, count)
        except Exception:
            logger.warning("Validation failed for table '%s'", table_name, exc_info=True)
