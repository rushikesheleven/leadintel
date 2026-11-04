"""Tests for CSV exporter."""

import csv
import io
import os
import tempfile

from leadintel.exporters.csv_exporter import _COLUMNS, export_to_csv
from leadintel.models.business import Business


def _make_biz(idx: int) -> Business:
    return Business(
        id=f"biz_{idx:03d}",
        name=f"Company {idx}",
        category="Technology",
        city="San Francisco",
        state="CA",
        country="US",
        phone=f"+1-415-555-{idx:04d}",
        email=f"info{idx}@example.com",
        website=f"https://company{idx}.example",
        rating=4.0,
        review_count=idx * 10,
        source="demo",
    )


class TestExportToCsv:
    def test_returns_string_when_no_path(self):
        businesses = [_make_biz(1)]
        content = export_to_csv(businesses)
        assert isinstance(content, str)

    def test_csv_has_header_row(self):
        content = export_to_csv([_make_biz(1)])
        reader = csv.DictReader(io.StringIO(content))
        assert set(_COLUMNS).issubset(set(reader.fieldnames or []))

    def test_csv_row_count(self):
        businesses = [_make_biz(i) for i in range(5)]
        content = export_to_csv(businesses)
        reader = csv.DictReader(io.StringIO(content))
        rows = list(reader)
        assert len(rows) == 5

    def test_csv_field_values(self):
        biz = _make_biz(42)
        content = export_to_csv([biz])
        reader = csv.DictReader(io.StringIO(content))
        row = next(reader)
        assert row["id"] == "biz_042"
        assert row["name"] == "Company 42"
        assert row["city"] == "San Francisco"
        assert row["source"] == "demo"

    def test_write_to_file(self):
        businesses = [_make_biz(i) for i in range(3)]
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
            path = f.name
        try:
            returned_path = export_to_csv(businesses, output_path=path)
            assert returned_path == os.path.abspath(path)
            assert os.path.exists(path)
            with open(path, encoding="utf-8") as f:
                content = f.read()
            reader = csv.DictReader(io.StringIO(content))
            rows = list(reader)
            assert len(rows) == 3
        finally:
            os.unlink(path)

    def test_empty_list_produces_header_only(self):
        content = export_to_csv([])
        reader = csv.DictReader(io.StringIO(content))
        rows = list(reader)
        assert rows == []
        assert reader.fieldnames is not None

    def test_no_latitude_longitude_in_output(self):
        content = export_to_csv([_make_biz(1)])
        assert "latitude" not in content
        assert "longitude" not in content

    def test_is_ai_generated_false_by_default(self):
        content = export_to_csv([_make_biz(1)])
        reader = csv.DictReader(io.StringIO(content))
        row = next(reader)
        assert row["is_ai_generated"] == "False"
