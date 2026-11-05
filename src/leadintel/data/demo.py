"""Demo data for development and testing — no real API calls."""

from __future__ import annotations

from typing import Any

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
    # Pune Central Businesses (Core Urban Area: Shivajinagar, FC Road, Deccan, Koregaon Park, Kothrud)
    Business(
        id="demo_pune_001",
        name="Vaishali Restaurant",
        category="Food & Beverage",
        address="FC Road, Shivajinagar, Pune, Maharashtra 411004, India",
        city="Pune",
        state="MH",
        country="IN",
        postal_code="411004",
        latitude=18.5246,
        longitude=73.8415,
        phone="+91-20-25531244",
        website=None,
        rating=4.6,
        review_count=12500,
        employee_count_estimate="50–100",
        source="demo",
    ),
    Business(
        id="demo_pune_002",
        name="Cafe Goodluck",
        category="Food & Beverage",
        address="Deccan Gymkhana, Pune, Maharashtra 411004, India",
        city="Pune",
        state="MH",
        country="IN",
        postal_code="411004",
        latitude=18.5168,
        longitude=73.8415,
        phone="+91-20-25676893",
        website=None,
        rating=4.4,
        review_count=8900,
        employee_count_estimate="20–50",
        source="demo",
    ),
    Business(
        id="demo_pune_003",
        name="German Bakery",
        category="Food & Beverage",
        address="North Main Road, Koregaon Park, Pune, Maharashtra 411001, India",
        city="Pune",
        state="MH",
        country="IN",
        postal_code="411001",
        latitude=18.5362,
        longitude=73.8940,
        phone="+91-20-26156543",
        website="https://germanbakerypune.example",
        rating=4.3,
        review_count=4200,
        employee_count_estimate="20–50",
        source="demo",
    ),
    Business(
        id="demo_pune_004",
        name="Kothrud Software Labs",
        category="Technology",
        address="Paud Road, Kothrud, Pune, Maharashtra 411038, India",
        city="Pune",
        state="MH",
        country="IN",
        postal_code="411038",
        latitude=18.5074,
        longitude=73.8077,
        website="https://kothrudsoftware.example",
        rating=4.5,
        review_count=180,
        employee_count_estimate="10–50",
        source="demo",
    ),
    # Pune Outlying / Distant Municipalities (Outside Central Core > 6km)
    Business(
        id="demo_pune_dist_001",
        name="Alandi Pilgrim Refreshments",
        category="Food & Beverage",
        address="Temple Road, Alandi, Pune District, Maharashtra 412105, India",
        city="Alandi",
        state="MH",
        country="IN",
        postal_code="412105",
        latitude=18.6775,
        longitude=73.8967,
        website=None,
        rating=4.0,
        review_count=310,
        employee_count_estimate="5–20",
        source="demo",
    ),
    Business(
        id="demo_pune_dist_002",
        name="Pimpri Auto Spare Parts",
        category="Automotive",
        address="Old Mumbai-Pune Highway, Pimpri, Maharashtra 411018, India",
        city="Pimpri-Chinchwad",
        state="MH",
        country="IN",
        postal_code="411018",
        latitude=18.6279,
        longitude=73.8009,
        website="https://pimpriauto.example",
        rating=4.1,
        review_count=520,
        employee_count_estimate="10–50",
        source="demo",
    ),
]


def search_demo_businesses(
    query: str,
    location: str | None = None,
    category: str | None = None,
    limit: int | None = None,
    latitude: float | None = None,
    longitude: float | None = None,
    radius_meters: int | None = None,
    wider_metro: bool = False,
    **kwargs: Any,
) -> list[Business]:
    """Filter demo businesses by query / location / category and enforce geographic distance."""
    from ..providers.overpass_provider import haversine_distance_meters

    q = (query or "").lower().strip()
    results = []

    # Center coordinates resolution
    center_lat: float | None = None
    center_lon: float | None = None
    if latitude is not None and longitude is not None:
        center_lat, center_lon = float(latitude), float(longitude)
    elif location:
        loc_lower = location.lower().strip()
        if "pune" in loc_lower:
            center_lat, center_lon = 18.5204, 73.8567
        elif "san francisco" in loc_lower or "sf" in loc_lower:
            center_lat, center_lon = 37.7749, -122.4194
        elif "new york" in loc_lower or "nyc" in loc_lower:
            center_lat, center_lon = 40.7128, -74.0060

    eff_radius = (
        (radius_meters if radius_meters is not None else 25_000)
        if wider_metro
        else (radius_meters if radius_meters is not None else 6_000)
    )

    for biz in DEMO_BUSINESSES:
        name_match = not q or q == "*" or q in biz.name.lower()
        cat_match = not q or (biz.category and q in biz.category.lower())

        # Location filtering
        loc_match = True
        if location and biz.city:
            loc_l = location.lower()
            # If searching for "pune", exclude separate municipalities like Alandi or Pimpri unless wider_metro
            if "pune" in loc_l and not wider_metro:
                loc_match = biz.city.lower() == "pune"
            else:
                loc_match = loc_l in biz.city.lower() or loc_l in (biz.address or "").lower()

        filter_cat = (
            not category
            or (biz.category and category.lower() in biz.category.lower())
        )
        filter_loc = not location or loc_match

        if (name_match or cat_match) and filter_cat and filter_loc:
            # Clone model for annotation
            b_copy = biz.model_copy()
            if center_lat is not None and center_lon is not None and b_copy.latitude and b_copy.longitude:
                dist_m = haversine_distance_meters(center_lat, center_lon, b_copy.latitude, b_copy.longitude)
                b_copy.distance_meters = round(dist_m, 1)
                b_copy.distance_km = round(dist_m / 1000.0, 2)
                if not wider_metro and dist_m > eff_radius:
                    continue  # Strict radius exclusion
            results.append(b_copy)

    # If no results matched query text, fallback to location/category matches
    if not results and (location or category):
        for biz in DEMO_BUSINESSES:
            loc_match = not location or (
                biz.city and location.lower() in biz.city.lower()
            )
            cat_match = not category or (
                biz.category and category.lower() in biz.category.lower()
            )
            if loc_match and cat_match:
                b_copy = biz.model_copy()
                if center_lat is not None and center_lon is not None and b_copy.latitude and b_copy.longitude:
                    dist_m = haversine_distance_meters(center_lat, center_lon, b_copy.latitude, b_copy.longitude)
                    b_copy.distance_meters = round(dist_m, 1)
                    b_copy.distance_km = round(dist_m / 1000.0, 2)
                    if not wider_metro and dist_m > eff_radius:
                        continue
                results.append(b_copy)

    if limit is not None:
        return results[:limit]
    return results


def get_demo_business(business_id: str) -> Business | None:
    """Return a single demo business by id."""
    for biz in DEMO_BUSINESSES:
        if biz.id == business_id:
            return biz
    return None
