"""
SQLite database storage for LeadIntel.

Persists researched businesses across searches and server sessions.
Uses standard library sqlite3 without external dependencies.
"""

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from ..config import settings
from ..models.business import Business

logger = logging.getLogger(__name__)

DEFAULT_DB_PATH = getattr(settings, "database_path", ".leadintel.db") or ".leadintel.db"


def _get_connection(db_path: Optional[str] = None) -> sqlite3.Connection:
    """Open a SQLite connection and configure row factory."""
    target_path = db_path or DEFAULT_DB_PATH
    if target_path != ":memory:":
        parent = Path(target_path).parent
        if parent and str(parent) != "." and not parent.exists():
            parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(target_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: Optional[str] = None) -> None:
    """Initialize the SQLite database schema if not already created."""
    conn = _get_connection(db_path)
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
        logger.debug("Database initialized at %s", db_path or DEFAULT_DB_PATH)
    finally:
        conn.close()


def save_businesses(
    businesses: list[Business], db_path: Optional[str] = None
) -> int:
    """
    Upsert businesses into the database.

    Stores the serialized business JSON and current UTC timestamp.
    Returns the count of businesses saved.
    """
    if not businesses:
        return 0

    init_db(db_path)
    conn = _get_connection(db_path)
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
    except Exception as exc:
        logger.warning("Failed to save businesses to database: %s", exc)
    finally:
        conn.close()

    return count


def get_business(business_id: str, db_path: Optional[str] = None) -> Optional[Business]:
    """
    Retrieve and deserialize a business from SQLite by ID.

    Returns the Business model if found, None otherwise.
    """
    if not business_id:
        return None

    init_db(db_path)
    conn = _get_connection(db_path)
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
    except Exception as exc:
        logger.warning("Error fetching business %s: %s", business_id, exc)
        return None
    finally:
        conn.close()


def get_all_businesses(
    min_score: Optional[float] = None,
    limit: int = 50,
    db_path: Optional[str] = None,
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
    init_db(db_path)
    conn = _get_connection(db_path)
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
    finally:
        conn.close()

    return results
