"""Tests for SQLite persistence storage in LeadIntel."""

import sqlite3
from pathlib import Path

import pytest

from leadintel.models.business import Business
from leadintel.storage.db import get_all_businesses, get_business, init_db, save_businesses


@pytest.fixture
def temp_db_path(tmp_path: Path) -> str:
    """Fixture providing a temporary database file path."""
    return str(tmp_path / "test_leadintel.db")


def test_init_db_creates_table(temp_db_path: str) -> None:
    """Verify init_db initializes the database and creates the businesses table."""
    init_db(temp_db_path)

    conn = sqlite3.connect(temp_db_path)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='businesses'"
    )
    table = cursor.fetchone()
    assert table is not None
    assert table[0] == "businesses"

    # Verify columns
    cursor.execute("PRAGMA table_info(businesses)")
    columns = {col[1]: col[2] for col in cursor.fetchall()}
    assert "id" in columns
    assert "model_json" in columns
    assert "updated_at" in columns
    conn.close()


def test_init_db_idempotent(temp_db_path: str) -> None:
    """Verify init_db can be called repeatedly without error."""
    init_db(temp_db_path)
    init_db(temp_db_path)
    init_db(temp_db_path)


def test_save_and_get_business(temp_db_path: str) -> None:
    """Verify saving a business and retrieving it restores all fields accurately."""
    biz = Business(
        id="biz_test_001",
        name="Acme Dental Care",
        category="Dentist",
        city="Pune",
        website="https://acmedental.example.com",
        website_status="website_verified",
        website_opportunity_score=35.0,
        distance_km=2.45,
        data_confidence=0.85,
    )

    saved_count = save_businesses([biz], db_path=temp_db_path)
    assert saved_count == 1

    retrieved = get_business("biz_test_001", db_path=temp_db_path)
    assert retrieved is not None
    assert retrieved.id == "biz_test_001"
    assert retrieved.name == "Acme Dental Care"
    assert retrieved.category == "Dentist"
    assert retrieved.city == "Pune"
    assert retrieved.website == "https://acmedental.example.com"
    assert retrieved.website_status == "website_verified"
    assert retrieved.website_opportunity_score == 35.0
    assert retrieved.distance_km == 2.45
    assert retrieved.data_confidence == 0.85


def test_save_businesses_upsert(temp_db_path: str) -> None:
    """Verify re-saving an existing business updates its data rather than duplicating."""
    biz = Business(
        id="biz_test_upsert",
        name="Original Name",
        website_status="website_not_checked",
    )
    save_businesses([biz], db_path=temp_db_path)

    # Verify initial state
    res1 = get_business("biz_test_upsert", db_path=temp_db_path)
    assert res1 is not None
    assert res1.name == "Original Name"

    # Update business data
    updated_biz = Business(
        id="biz_test_upsert",
        name="Updated Name",
        website_status="website_verified",
        website_opportunity_score=15.0,
    )
    save_businesses([updated_biz], db_path=temp_db_path)

    # Verify updated state
    res2 = get_business("biz_test_upsert", db_path=temp_db_path)
    assert res2 is not None
    assert res2.name == "Updated Name"
    assert res2.website_status == "website_verified"
    assert res2.website_opportunity_score == 15.0

    # Ensure only 1 row exists
    conn = sqlite3.connect(temp_db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM businesses")
    count = cursor.fetchone()[0]
    conn.close()
    assert count == 1


def test_get_nonexistent_business_returns_none(temp_db_path: str) -> None:
    """Verify get_business on an unknown ID returns None."""
    assert get_business("non_existent_id", db_path=temp_db_path) is None
    assert get_business("", db_path=temp_db_path) is None


def test_save_empty_list_returns_zero(temp_db_path: str) -> None:
    """Verify saving empty list returns 0 and does not fail."""
    assert save_businesses([], db_path=temp_db_path) == 0


def test_save_multiple_businesses(temp_db_path: str) -> None:
    """Verify batch saving multiple businesses."""
    businesses = [
        Business(id=f"biz_{i}", name=f"Business {i}", city="Mumbai")
        for i in range(5)
    ]
    saved_count = save_businesses(businesses, db_path=temp_db_path)
    assert saved_count == 5

    for i in range(5):
        b = get_business(f"biz_{i}", db_path=temp_db_path)
        assert b is not None
        assert b.name == f"Business {i}"


@pytest.mark.asyncio
async def test_search_businesses_tool_persists_to_storage(
    monkeypatch: pytest.MonkeyPatch, temp_db_path: str
) -> None:
    """Verify executing search_businesses tool persists businesses into SQLite database."""
    import leadintel.storage.db as db_module
    from leadintel.server import mcp

    # Point default DB path to temporary db
    monkeypatch.setattr(db_module, "DEFAULT_DB_PATH", temp_db_path)

    # Search demo businesses
    res = await mcp.call_tool(
        "search_businesses",
        {
            "query": "Bakery",
            "research_websites": False,
        },
    )
    data = res.content[0].text if hasattr(res.content[0], "text") else str(res.content[0])
    import json
    parsed = json.loads(data)
    assert parsed["total_found"] > 0
    first_biz = parsed["businesses"][0]
    biz_id = first_biz["id"]

    # Verify business is present in the database
    persisted = get_business(biz_id, db_path=temp_db_path)
    assert persisted is not None
    assert persisted.id == biz_id
    assert persisted.name == first_biz["name"]


def test_get_all_businesses_filtering_and_limit(temp_db_path: str) -> None:
    """Verify get_all_businesses filters by min_score and respects limit."""
    b1 = Business(id="b1", name="Low Opp", website_opportunity_score=20.0)
    b2 = Business(id="b2", name="Med Opp", website_opportunity_score=50.0)
    b3 = Business(id="b3", name="High Opp", website_opportunity_score=90.0)
    save_businesses([b1, b2, b3], db_path=temp_db_path)

    # All businesses without filter
    all_b = get_all_businesses(db_path=temp_db_path)
    assert len(all_b) == 3

    # Filter with min_score=60.0
    filtered = get_all_businesses(min_score=60.0, db_path=temp_db_path)
    assert len(filtered) == 1
    assert filtered[0].id == "b3"

    # Filter with min_score=30.0 and limit=1
    limited = get_all_businesses(min_score=30.0, limit=1, db_path=temp_db_path)
    assert len(limited) == 1


@pytest.mark.asyncio
async def test_get_saved_leads_mcp_tool(
    monkeypatch: pytest.MonkeyPatch, temp_db_path: str
) -> None:
    """Verify get_saved_leads MCP tool returns stored leads filtered by score."""
    import json

    import leadintel.storage.db as db_module
    from leadintel.server import mcp

    monkeypatch.setattr(db_module, "DEFAULT_DB_PATH", temp_db_path)

    b1 = Business(id="lead_1", name="Alpha Dental", website_opportunity_score=30.0)
    b2 = Business(id="lead_2", name="Beta Clinic", website_opportunity_score=85.0)
    save_businesses([b1, b2], db_path=temp_db_path)

    res = await mcp.call_tool("get_saved_leads", {"min_opportunity_score": 50.0})
    data_str = res.content[0].text if hasattr(res.content[0], "text") else str(res.content[0])
    parsed = json.loads(data_str)

    assert parsed["total_retrieved"] == 1
    assert parsed["businesses"][0]["name"] == "Beta Clinic"
    assert parsed["businesses"][0]["id"] == "lead_2"

