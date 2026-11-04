"""Tests for the provider registry."""

from __future__ import annotations

import pytest

from leadintel.models.business import Business
from leadintel.providers.demo_provider import DemoProvider
from leadintel.providers.registry import ProviderRegistry

# ── Stub provider for testing ─────────────────────────────────────────────────

class StubProvider:
    """Configurable stub that returns preset results."""

    name: str = "stub"
    requires_auth: bool = False

    def __init__(self, results: list[Business] | None = None, raises: bool = False):
        self._results = results or []
        self._raises = raises
        self.search_called = 0
        self.details_called = 0

    async def search(self, query, location, category, limit) -> list[Business]:
        self.search_called += 1
        if self._raises:
            raise RuntimeError("Stub provider exploded")
        return self._results[:limit]

    async def get_details(self, business_id: str) -> Business | None:
        self.details_called += 1
        if self._raises:
            raise RuntimeError("Stub provider exploded")
        for b in self._results:
            if b.id == business_id:
                return b
        return None


def _make_biz(idx: int = 1, source: str = "stub") -> Business:
    return Business(id=f"stub_{idx:03d}", name=f"Stub Business {idx}", source=source)


# ── ProviderRegistry tests ────────────────────────────────────────────────────

class TestProviderRegistry:
    def test_registry_requires_at_least_one_provider(self):
        with pytest.raises(ValueError):
            ProviderRegistry([])

    def test_primary_is_first_provider(self):
        p1 = StubProvider()
        p1.name = "first"
        p2 = StubProvider()
        p2.name = "second"
        registry = ProviderRegistry([p1, p2])  # type: ignore[arg-type]
        assert registry.primary.name == "first"

    def test_provider_names_order(self):
        p1, p2 = StubProvider(), StubProvider()
        p1.name = "alpha"
        p2.name = "beta"
        registry = ProviderRegistry([p1, p2])  # type: ignore[arg-type]
        assert registry.provider_names() == ["alpha", "beta"]


@pytest.mark.asyncio
class TestProviderRegistrySearch:
    async def test_returns_first_non_empty_result(self):
        empty = StubProvider(results=[])
        winner = StubProvider(results=[_make_biz(1), _make_biz(2)])
        registry = ProviderRegistry([empty, winner])  # type: ignore[arg-type]
        businesses, name = await registry.search("*", None, None, 10)
        assert len(businesses) == 2
        assert name == "stub"

    async def test_falls_back_when_first_raises(self):
        broken = StubProvider(raises=True)
        working = StubProvider(results=[_make_biz(1)])
        registry = ProviderRegistry([broken, working])  # type: ignore[arg-type]
        businesses, name = await registry.search("*", None, None, 10)
        assert len(businesses) == 1

    async def test_returns_empty_when_all_fail(self):
        b1 = StubProvider(raises=True)
        b2 = StubProvider(raises=True)
        registry = ProviderRegistry([b1, b2])  # type: ignore[arg-type]
        businesses, _ = await registry.search("*", None, None, 10)
        assert businesses == []

    async def test_returns_empty_when_all_return_empty(self):
        registry = ProviderRegistry([StubProvider(), StubProvider()])  # type: ignore[arg-type]
        businesses, _ = await registry.search("*", None, None, 10)
        assert businesses == []

    async def test_skips_empty_tries_next(self):
        """First provider returns empty, second returns results — second wins."""
        p1 = StubProvider(results=[])
        p2 = StubProvider(results=[_make_biz(5)])
        registry = ProviderRegistry([p1, p2])  # type: ignore[arg-type]
        businesses, _ = await registry.search("*", None, None, 10)
        assert len(businesses) == 1
        assert p1.search_called == 1
        assert p2.search_called == 1

    async def test_short_circuits_after_first_success(self):
        """Second provider is never called when first returns results."""
        p1 = StubProvider(results=[_make_biz(1)])
        p2 = StubProvider(results=[_make_biz(2)])
        registry = ProviderRegistry([p1, p2])  # type: ignore[arg-type]
        await registry.search("*", None, None, 10)
        assert p1.search_called == 1
        assert p2.search_called == 0

    async def test_limit_passed_through(self):
        stub = StubProvider(results=[_make_biz(i) for i in range(20)])
        registry = ProviderRegistry([stub])  # type: ignore[arg-type]
        businesses, _ = await registry.search("*", None, None, 3)
        assert len(businesses) <= 3

    async def test_demo_provider_always_returns_results(self):
        """DemoProvider should always return data for wildcard queries."""
        registry = ProviderRegistry([DemoProvider()])  # type: ignore[arg-type]
        businesses, name = await registry.search("*", None, None, 50)
        assert len(businesses) > 0
        assert name == "demo"


@pytest.mark.asyncio
class TestProviderRegistryGetDetails:
    async def test_returns_first_match(self):
        biz = _make_biz(1)
        p = StubProvider(results=[biz])
        registry = ProviderRegistry([p])  # type: ignore[arg-type]
        result, name = await registry.get_details("stub_001")
        assert result is not None
        assert result.id == "stub_001"

    async def test_returns_none_when_not_found(self):
        registry = ProviderRegistry([StubProvider()])  # type: ignore[arg-type]
        result, _ = await registry.get_details("nonexistent")
        assert result is None

    async def test_falls_back_on_exception(self):
        broken = StubProvider(raises=True)
        biz = _make_biz(1)
        biz.id  # make sure id is set
        working = StubProvider(results=[biz])
        registry = ProviderRegistry([broken, working])  # type: ignore[arg-type]
        result, _ = await registry.get_details("stub_001")
        assert result is not None
