"""Builds a small CSV in the Superstore schema (Tableau 'Sample - Superstore' layout) for tests.

This is NOT the real dataset: it only mimics its columns, quirks (cp1252 text, m/d/Y dates,
one duplicate row, deep discounts that lose money) so the cleaning layer can be tested offline.
"""
import numpy as np
import pandas as pd


def make_fake_superstore(n_orders: int = 2500, seed: int = 7) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    dates = pd.to_datetime("2014-01-01") + pd.to_timedelta(rng.integers(0, 4 * 365, n_orders), unit="D")
    lines = rng.integers(1, 5, n_orders)
    rows = []
    cats = {"Furniture": ["Chairs", "Tables"], "Office Supplies": ["Binders", "Paper"],
            "Technology": ["Phones", "Accessories"]}
    for i, (d, k) in enumerate(zip(dates, lines)):
        oid = f"CA-{d.year}-{100000 + i}"
        for _ in range(k):
            cat = rng.choice(list(cats))
            disc = float(rng.choice([0, 0, 0.1, 0.2, 0.3, 0.5, 0.8]))
            sales = round(float(rng.lognormal(4.5, 1.0)), 2)
            profit = round(sales * (0.25 - 0.55 * disc) + rng.normal(0, 3), 2)
            rows.append({
                "Row ID": len(rows) + 1, "Order ID": oid, "Order Date": f"{d.month}/{d.day}/{d.year}",
                "Ship Date": f"{(d + pd.Timedelta(days=4)).month}/{(d + pd.Timedelta(days=4)).day}/{(d + pd.Timedelta(days=4)).year}",
                "Ship Mode": rng.choice(["Standard Class", "Second Class", "First Class", "Same Day"]),
                "Customer ID": f"CU-{rng.integers(1, 800)}", "Customer Name": "José Müller ",
                "Segment": rng.choice(["Consumer", "Corporate", "Home Office"], p=[0.52, 0.30, 0.18]),
                "Country": "United States", "City": rng.choice(["New York City", "Los Angeles", "Houston", "Chicago"]),
                "State": "CA", "Postal Code": 90001,
                "Region": rng.choice(["West", "East", "Central", "South"]),
                "Product ID": "FUR-1", "Category": cat, "Sub-Category": rng.choice(cats[cat]),
                "Product Name": f"Item {rng.integers(1, 300)} – deluxe", "Sales": sales,
                "Quantity": int(rng.integers(1, 8)), "Discount": disc, "Profit": profit,
            })
    df = pd.DataFrame(rows)
    return pd.concat([df, df.iloc[[0]]], ignore_index=True)  # one exact duplicate


if __name__ == "__main__":
    make_fake_superstore().to_csv("Sample - Superstore.csv", index=False, encoding="cp1252")
