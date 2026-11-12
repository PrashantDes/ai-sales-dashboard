from decimal import Decimal
from tests.retail_fixture import retail_rows
from scripts.profile_online_retail import COLUMNS, sha

def test_fixture_is_source_shaped_and_contains_required_edge_cases():
    rows = retail_rows()
    assert all(set(row) == set(COLUMNS) for row in rows)
    assert rows[0] == rows[1]
    assert any(row["CustomerID"] is None for row in rows)
    assert any(row["Description"] is None for row in rows)
    assert any(row["InvoiceDate"] == "invalid" for row in rows)
    assert any(row["InvoiceNo"].startswith("C") and row["Quantity"] == -1 for row in rows)
    assert any(row["InvoiceNo"].startswith("C") and row["Quantity"] == 1 for row in rows)
    assert any(Decimal(row["UnitPrice"]) < 0 for row in rows)
    assert any(Decimal(row["UnitPrice"]).as_tuple().exponent < -3 for row in rows)

def test_source_hash_is_content_based(tmp_path):
    p = tmp_path / "source"
    p.write_bytes(b"synthetic")
    first = sha(p)
    assert sha(p) == first
    p.write_bytes(b"changed")
    assert sha(p) != first
