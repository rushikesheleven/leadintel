"""Demo data for development and testing — no real API calls."""

from __future__ import annotations

from ..models.business import Business

DEMO_BUSINESSES: list[Business] = [
    Business(
        id="demo_001",
        name="Acme Tech Solutions",
        category="Software Development",
        address="100 Innovation Drive, San Francisco, CA 94105, USA",
        city="San Francisco",
        state="CA",
        country="US",
        postal_code="94105",
        latitude=37.7749,
        longitude=-122.4194,
        phone="+1-415-555-0101",
        email="hello@acmetech.example",
        website="https://acmetech.example",
        linkedin_url="https://linkedin.com/company/acmetech-example",
        rating=4.5,
        review_count=128,
        employee_count_estimate="50–200",
        source="demo",
    ),
    Business(
        id="demo_002",
        name="BrightSpark Digital",
        category="Digital Marketing",
        address="200 Market Street, New York, NY 10001, USA",
        city="New York",
        state="NY",
        country="US",
        postal_code="10001",
        latitude=40.7128,
        longitude=-74.0060,
        phone="+1-212-555-0202",
        email="info@brightsparkdigital.example",
        website="https://brightsparkdigital.example",
        twitter_url="https://twitter.com/brightsparkdigital",
        rating=4.2,
        review_count=89,
        employee_count_estimate="10–50",
        source="demo",
    ),
    Business(
        id="demo_003",
        name="GreenLeaf Consulting",
        category="Management Consulting",
        address="300 Michigan Avenue, Chicago, IL 60601, USA",
        city="Chicago",
        state="IL",
        country="US",
        postal_code="60601",
        latitude=41.8827,
        longitude=-87.6233,
        phone="+1-312-555-0303",
        email="contact@greenleafconsulting.example",
        website="https://greenleafconsulting.example",
        linkedin_url="https://linkedin.com/company/greenleaf-consulting-example",
        facebook_url="https://facebook.com/greenleafconsulting.example",
        rating=4.8,
        review_count=54,
        employee_count_estimate="10–50",
        source="demo",
    ),
    Business(
        id="demo_004",
        name="Nexus Cloud Systems",
        category="Cloud Computing",
        address="400 Congress Avenue, Austin, TX 78701, USA",
        city="Austin",
        state="TX",
        country="US",
        postal_code="78701",
        latitude=30.2672,
        longitude=-97.7431,
        phone="+1-512-555-0404",
        website="https://nexuscloud.example",
        rating=4.0,
        review_count=210,
        employee_count_estimate="200–500",
        source="demo",
    ),
    Business(
        id="demo_005",
        name="Pinnacle HR Partners",
        category="Human Resources",
        address="500 Peachtree Street NE, Atlanta, GA 30308, USA",
        city="Atlanta",
        state="GA",
        country="US",
        postal_code="30308",
        latitude=33.7490,
        longitude=-84.3880,
        phone="+1-404-555-0505",
        email="team@pinnacleHR.example",
        website="https://pinnacleHR.example",
        rating=3.9,
        review_count=37,
        employee_count_estimate="10–50",
        source="demo",
    ),
]


def search_demo_businesses(
    query: str,
    location: str | None = None,
    category: str | None = None,
    limit: int = 10,
) -> list[Business]:
    """Filter demo businesses by query / location / category."""
    q = query.lower()
    results = []

    for biz in DEMO_BUSINESSES:
        name_match = q in biz.name.lower()
        cat_match = biz.category and q in biz.category.lower()
        loc_match = location and biz.city and location.lower() in biz.city.lower()
        filter_cat = (
            not category
            or (biz.category and category.lower() in biz.category.lower())
        )
        filter_loc = not location or loc_match

        if (name_match or cat_match or not q or q == "*") and filter_cat and filter_loc:
            results.append(biz)

    # If no query-level match, return all that pass location/category filters
    if not results and (location or category):
        for biz in DEMO_BUSINESSES:
            loc_match = (
                not location
                or (biz.city and location.lower() in biz.city.lower())
            )
            cat_match = (
                not category
                or (biz.category and category.lower() in biz.category.lower())
            )
            if loc_match and cat_match:
                results.append(biz)

    return results[:limit]


def get_demo_business(business_id: str) -> Business | None:
    """Return a single demo business by id."""
    for biz in DEMO_BUSINESSES:
        if biz.id == business_id:
            return biz
    return None
