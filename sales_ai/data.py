"""Synthetic (but realistic) sales data for an Indian D2C / e-commerce business.

The generator bakes in patterns an analyst would expect to find:
  * year-over-year growth
  * festive-season peaks (Oct-Nov) with heavier discounting
  * weekend uplift
  * a few injected one-day spikes / outages so anomaly detection has something to find
"""
from __future__ import annotations

import numpy as np
import pandas as pd

START_DATE = "2023-01-01"
END_DATE = "2026-10-25"
BASE_ORDERS_PER_DAY = 38

REQUIRED_COLUMNS = [
    "date", "order_id", "region", "city", "category", "product",
    "channel", "customer_segment", "units", "discount", "revenue", "cost",
]

REGION_CITIES = {
    "North": ["Delhi", "Meerut", "Lucknow", "Chandigarh"],
    "South": ["Bengaluru", "Chennai", "Hyderabad", "Kochi"],
    "West": ["Mumbai", "Pune", "Ahmedabad", "Jaipur"],
    "East": ["Kolkata", "Patna", "Bhubaneswar", "Guwahati"],
}
REGION_WEIGHTS = {"North": 0.28, "South": 0.27, "West": 0.30, "East": 0.15}

# category, product, list price (INR), cost ratio, sales weight
PRODUCTS = [
    ("Electronics", "Smartphone", 18500, 0.82, 0.10),
    ("Electronics", "Laptop", 52000, 0.84, 0.03),
    ("Electronics", "Earbuds", 2400, 0.55, 0.12),
    ("Electronics", "Smartwatch", 6500, 0.62, 0.06),
    ("Home & Kitchen", "Air Fryer", 7200, 0.60, 0.06),
    ("Home & Kitchen", "Mixer Grinder", 3800, 0.58, 0.07),
    ("Home & Kitchen", "Water Purifier", 12500, 0.66, 0.03),
    ("Home & Kitchen", "Cookware Set", 2900, 0.52, 0.06),
    ("Fashion", "Sneakers", 3200, 0.48, 0.09),
    ("Fashion", "Backpack", 1800, 0.45, 0.07),
    ("Fashion", "Jacket", 4200, 0.50, 0.04),
    ("Fashion", "Sunglasses", 1500, 0.40, 0.04),
    ("Health & Fitness", "Whey Protein", 3200, 0.64, 0.05),
    ("Health & Fitness", "Yoga Mat", 900, 0.42, 0.04),
    ("Health & Fitness", "Dumbbell Set", 3500, 0.60, 0.03),
    ("Health & Fitness", "Fitness Band", 2800, 0.56, 0.04),
    ("Office", "Office Chair", 8500, 0.64, 0.02),
    ("Office", "Standing Desk", 15500, 0.68, 0.01),
    ("Office", "Monitor", 14000, 0.78, 0.02),
    ("Office", "Printer", 9500, 0.76, 0.01),
]

CHANNELS = {"Website": 0.38, "Mobile App": 0.32, "Marketplace": 0.20, "Retail Store": 0.10}
SEGMENTS = {"Consumer": 0.65, "Small Business": 0.25, "Enterprise": 0.10}

MONTH_SEASONALITY = {
    1: 0.90, 2: 0.85, 3: 0.95, 4: 0.95, 5: 0.90, 6: 0.85,
    7: 0.90, 8: 1.00, 9: 1.05, 10: 1.35, 11: 1.40, 12: 1.15,
}


def generate_sales_data(seed: int = 42, start: str = START_DATE, end: str = END_DATE) -> pd.DataFrame:
    """Return one row per order line with revenue, cost and profit in INR."""
    rng = np.random.default_rng(seed)
    days = pd.date_range(start, end, freq="D")
    t = (days - days[0]).days.to_numpy() / 365.25

    month_mult = days.month.map(MONTH_SEASONALITY).to_numpy()
    dow_mult = np.where(days.day_of_week >= 5, 1.15, 1.0)
    lam = BASE_ORDERS_PER_DAY * (1 + 0.22 * t) * month_mult * dow_mult

    # Inject a handful of abnormal days (promo spikes and outages)
    n_anom = 8
    anomaly_idx = rng.choice(np.arange(60, len(days) - 5), size=n_anom, replace=False)
    lam[anomaly_idx] *= rng.choice([2.6, 0.25], size=n_anom)

    n_orders = rng.poisson(lam)
    n = int(n_orders.sum())
    dates = np.repeat(days.to_numpy(), n_orders)
    t_order = np.repeat(t, n_orders)
    month = pd.DatetimeIndex(dates).month.to_numpy()

    # Product / price
    prod_df = pd.DataFrame(PRODUCTS, columns=["category", "product", "price", "cost_ratio", "weight"])
    p_idx = rng.choice(len(prod_df), size=n, p=prod_df["weight"] / prod_df["weight"].sum())
    list_price = prod_df["price"].to_numpy()[p_idx] * (1 + 0.03 * t_order) * rng.normal(1, 0.02, n)
    cost_ratio = prod_df["cost_ratio"].to_numpy()[p_idx] * rng.normal(1, 0.03, n)

    # Customer and channel attributes
    segment = rng.choice(list(SEGMENTS), size=n, p=list(SEGMENTS.values()))
    channel = rng.choice(list(CHANNELS), size=n, p=list(CHANNELS.values()))
    region = rng.choice(list(REGION_WEIGHTS), size=n, p=list(REGION_WEIGHTS.values()))
    city = np.empty(n, dtype=object)
    for r, cities in REGION_CITIES.items():
        m = region == r
        city[m] = rng.choice(cities, size=int(m.sum()))

    units = 1 + rng.poisson(0.4, n)
    ent = segment == "Enterprise"
    units[ent] = 2 + rng.poisson(3, int(ent.sum()))

    # Discounts are heavier in festive months
    levels = np.array([0, 0.05, 0.10, 0.15, 0.20])
    d_base = rng.choice(levels, size=n, p=[0.45, 0.25, 0.15, 0.10, 0.05])
    d_fest = rng.choice(levels, size=n, p=[0.15, 0.20, 0.25, 0.25, 0.15])
    discount = np.where(np.isin(month, [10, 11]), d_fest, d_base)

    gross = units * list_price
    revenue = gross * (1 - discount)
    cost = gross * cost_ratio

    df = pd.DataFrame({
        "date": pd.to_datetime(dates),
        "order_id": [f"ORD-{i:07d}" for i in range(1, n + 1)],
        "customer_id": [f"CUST-{c:05d}" for c in rng.integers(1, 12000, n)],
        "region": region,
        "city": city,
        "category": prod_df["category"].to_numpy()[p_idx],
        "product": prod_df["product"].to_numpy()[p_idx],
        "channel": channel,
        "customer_segment": segment,
        "units": units,
        "discount": discount,
        "revenue": revenue.round(2),
        "cost": cost.round(2),
    })
    df["profit"] = (df["revenue"] - df["cost"]).round(2)
    return df


def validate_sales_data(df: pd.DataFrame) -> pd.DataFrame:
    """Check a user-supplied dataframe, coerce types, and add `profit` if missing.

    Raises ValueError with a readable message when the schema is wrong.
    """
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {', '.join(missing)}")

    out = df.copy()
    out["date"] = pd.to_datetime(out["date"], errors="coerce").dt.normalize()
    for col in ["units", "discount", "revenue", "cost"]:
        out[col] = pd.to_numeric(out[col], errors="coerce")
    out = out.dropna(subset=["date", "revenue", "cost", "units"])
    if out.empty:
        raise ValueError("No valid rows after parsing dates and numbers.")
    out["discount"] = out["discount"].fillna(0)
    if out["discount"].max() > 1:  # given as percentages (e.g. 10 for 10%)
        out["discount"] = out["discount"] / 100
    if "profit" in out.columns:
        out["profit"] = pd.to_numeric(out["profit"], errors="coerce")
        if not np.isfinite(out["profit"]).all():
            raise ValueError("Profit must contain a finite number for every valid row.")
    else:
        out["profit"] = out["revenue"] - out["cost"]
    return out.sort_values("date").reset_index(drop=True)
