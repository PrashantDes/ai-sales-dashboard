"""Entirely invented source-shaped records; no real customer rows."""
BASE = dict(InvoiceNo="TEST-1", StockCode="12345A", Description="Synthetic item", Quantity=2, InvoiceDate="2011-01-01 10:00", UnitPrice="1.125", CustomerID="TEST-CUSTOMER", Country="Testland")
def retail_rows():
    rows = [dict(BASE), dict(BASE)]  # legitimate-looking repeated lines
    for change in [dict(CustomerID=None), dict(Description=None), dict(InvoiceNo="CTEST-2", Quantity=-1), dict(Quantity=-1), dict(UnitPrice="0"), dict(UnitPrice="-1"), dict(InvoiceDate="invalid"), dict(Quantity="NaN"), dict(StockCode="POST"), dict(InvoiceNo="CTEST-3", Quantity=1), dict(InvoiceDate="2011-01-01 10:01"), dict(UnitPrice="0.0001")]:
        rows.append({**BASE, **change})
    return rows
