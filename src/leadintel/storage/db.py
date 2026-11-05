"""
SQLite database storage for LeadIntel.

Persists researched businesses across searches and server sessions.
Uses standard library sqlite3 without external dependencies.
Stores the database safely in the user's home directory.
"""

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from ..models.business import Business

logger = logging.getLogger(__name__)

DB_DIR = Path.home() / ".local" / "share" / "leadintel"
DB_PATH = DB_DIR / "leadintel.db"
DEFAULT_DB_PATH = str(DB_PATH)


def _resolve_path(db_path: Optional[str | Path] = None) -> str:
    """Resolve database path, honoring test overrides or parameters."""
    if db_path:
        return str(db_path)
    if DEFAULT_DB_PATH != str(DB_PATH):
        return str(DEFAULT_DB_PATH)
    return str(DB_PATH)


def _get_connection(db_path: Optional[str | Path] = None) -> sqlite3.Connection:
    """Open a SQLite connection and configure row factory."""
    target_path = _resolve_path(db_path)
    if target_path != ":memory:":
        parent = Path(target_path).parent
        parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(target_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: Optional[str | Path] = None) -> None:
    """Initialize the SQLite database schema if not already created."""
    try:
        DB_DIR.mkdir(parents=True, exist_ok=True)
        target = _resolve_path(db_path)
        conn = _get_connection(target)
        try:
            with conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS businesses (
                        id TEXT PRIMARY KEY,
                        model_json TEXT,
                        updated_at DATETIME
                    )
                    """
                )
            logger.debug("Database initialized at %s", target)
        finally:
            conn.close()
    except Exception as e:
        logger.error(f"Failed to initialize SQLite database: {e}")


def save_businesses(
    businesses: list[Business], db_path: Optional[str | Path] = None
) -> int:
    """
    Upsert businesses into the database.

    Stores the serialized business JSON and current UTC timestamp.
    Returns the count of businesses saved.
    """
    if not businesses:
        return 0

    try:
        init_db(db_path)
        target = _resolve_path(db_path)
        conn = _get_connection(target)
        count = 0
        now_iso = datetime.now(timezone.utc).isoformat()
        try:
            with conn:
                for b in businesses:
                    if not b.id:
                        continue
                    model_json = b.model_dump_json()
                    conn.execute(
                        """
                        INSERT INTO businesses (id, model_json, updated_at)
                        VALUES (?, ?, ?)
                        ON CONFLICT(id) DO UPDATE SET
                            model_json = excluded.model_json,
                            updated_at = excluded.updated_at
                        """,
                        (b.id, model_json, now_iso),
                    )
                    count += 1
            logger.debug("Saved %d businesses to database", count)
            return count
        finally:
            conn.close()
    except Exception as e:
        logger.error(f"Failed to save businesses to database: {e}")
        return 0


def get_business(business_id: str, db_path: Optional[str | Path] = None) -> Optional[Business]:
    """
    Retrieve and deserialize a business from SQLite by ID.

    Returns the Business model if found, None otherwise.
    """
    if not business_id:
        return None

    try:
        init_db(db_path)
        target = _resolve_path(db_path)
        conn = _get_connection(target)
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT model_json FROM businesses WHERE id = ?",
                (business_id,),
            )
            row = cursor.fetchone()
            if not row or not row["model_json"]:
                return None
            return Business.model_validate_json(row["model_json"])
        finally:
            conn.close()
    except Exception as e:
        logger.error(f"Error fetching business {business_id}: {e}")
        return None


def get_all_businesses(
    min_score: Optional[float] = None,
    limit: int = 50,
    db_path: Optional[str | Path] = None,
) -> list[Business]:
    """
    Retrieve saved businesses from SQLite, optionally filtered by minimum opportunity score.

    Args:
        min_score: Optional minimum website_opportunity_score threshold.
        limit: Maximum number of businesses to return.
        db_path: Optional database path override (e.g. for testing).

    Returns:
        List of matching Business objects ordered by updated_at descending.
    """
    try:
        init_db(db_path)
        target = _resolve_path(db_path)
        conn = _get_connection(target)
        results: list[Business] = []
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT model_json FROM businesses ORDER BY updated_at DESC")
            rows = cursor.fetchall()
            for row in rows:
                if not row or not row["model_json"]:
                    continue
                try:
                    biz = Business.model_validate_json(row["model_json"])
                    if min_score is not None:
                        opp_score = biz.website_opportunity_score
                        if opp_score is None or opp_score < min_score:
                            continue
                    results.append(biz)
                    if len(results) >= limit:
                        break
                except Exception as exc:
                    logger.debug("Skipping unparseable business record: %s", exc)
            return results
        finally:
            conn.close()
    except Exception as e:
        logger.error(f"Failed to retrieve businesses from database: {e}")
        return []
