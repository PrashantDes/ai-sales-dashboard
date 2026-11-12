"""Data-cleaning layer for the Superstore Sales dataset (Tableau sample / Kaggle versions).

`clean_superstore` returns the app's standard schema plus a step-by-step report that the
dashboard shows in its "Data & EDA" tab (so a reviewer can see what was done and why).
"""
from __future__ import annotations

import re

import numpy as np
import pandas as pd

from sales_ai.data import normalize_discounts

# Needed for the full dashboard (margin analysis needs Profit; discount analysis needs Discount)
_REQUIRED = ["order id", "order date", "segment", "region", "category",
             "product name", "sales", "quantity", "discount", "profit"]
_CORE = {"order id", "order date", "sales", "category", "region"}


def _norm(col: str) -> str:
    """'Sub-Category' / 'Sub_Category' / 'sub.category' -> 'sub category'."""
    return re.sub(r"[^a-z0-9]+", " ", str(col).lower()).strip()


def read_csv_flexible(src) -> pd.DataFrame:
    """Superstore CSVs are often Windows-1252 encoded: try UTF-8, then fall back."""
    last: Exception | None = None
    for enc in ("utf-8", "cp1252", "latin-1"):
        try:
            if hasattr(src, "seek"):
                src.seek(0)
            return pd.read_csv(src, encoding=enc)
        except UnicodeDecodeError as exc:
            last = exc
    raise ValueError(f"Could not decode the CSV file: {last}")


def looks_like_superstore(df: pd.DataFrame) -> bool:
    return _CORE <= {_norm(c) for c in df.columns}


def _detect_dayfirst(dates: pd.Series) -> bool:
    s = dates.astype(str).str.strip()
    if s.str.match(r"^\d{4}-").mean() > 0.5:  # ISO format
        return False
    first = pd.to_numeric(s.str.extract(r"^(\d{1,2})[/\-.]")[0], errors="coerce")
    return bool((first > 12).any())


def clean_superstore(raw: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Clean a raw Superstore frame. Returns (clean_df, report_df)."""
    steps: list[tuple[str, str]] = []
    df = raw.copy()
    df.columns = [_norm(c) for c in df.columns]
    if not df.columns.is_unique:
        raise ValueError("Duplicate column names after normalization. Keep one column for each field.")

    missing = [c for c in _REQUIRED if c not in df.columns]
    if missing:
        hint = ""
        if {"profit", "discount", "quantity"} & set(missing):
            hint = (" This version of the dataset has no Profit/Discount/Quantity columns. "
                    "Use one that includes them (e.g. the Tableau 'Sample - Superstore' or Kaggle's "
                    "'Superstore Dataset' with a Profit column) to get margin analysis.")
        raise ValueError("Missing columns: " + ", ".join(missing) + "." + hint)

    steps.append(("Rows loaded", f"{len(df):,} rows × {df.shape[1]} columns"))

    # 1. whitespace in text columns
    text_cols = df.select_dtypes(include=["object", "string"]).columns
    for c in text_cols:
        df[c] = df[c].astype("string").str.strip()
    steps.append(("Trimmed whitespace", f"{len(text_cols)} text columns"))

    # 2. exact duplicates
    n_dup = int(df.duplicated().sum())
    df = df.drop_duplicates()
    steps.append(("Exact duplicate rows removed", f"{n_dup:,}"))
    identifiers = df["order id"].astype("string").str.strip()
    missing_ids = identifiers.isna() | identifiers.eq("")
    df = df.loc[~missing_ids].copy()
    steps.append(("Rows with missing order IDs dropped", f"{int(missing_ids.sum()):,}"))

    # 3. dates
    dayfirst = _detect_dayfirst(df["order date"])
    df["order date"] = pd.to_datetime(df["order date"], dayfirst=dayfirst, errors="coerce", format="mixed")
    if "ship date" in df.columns:
        df["ship date"] = pd.to_datetime(df["ship date"], dayfirst=dayfirst, errors="coerce", format="mixed")
    bad_dates = int(df["order date"].isna().sum())
    df = df.dropna(subset=["order date"])
    steps.append(("Order dates parsed", f"{'day-first' if dayfirst else 'month-first / ISO'} format detected; "
                                        f"{bad_dates:,} unparseable rows dropped"))

    # 4. numerics
    for c in ["sales", "quantity", "discount", "profit"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    numeric_cols = ["sales", "quantity", "discount", "profit"]
    invalid_numbers = ~np.isfinite(df[numeric_cols]).all(axis=1)
    df = df.loc[~invalid_numbers].copy()
    steps.append(("Rows with missing or non-finite numbers dropped", f"{int(invalid_numbers.sum()):,}"))

    n_nonpos = int((df["sales"] <= 0).sum())
    df = df[df["sales"] > 0]
    steps.append(("Non-positive sales rows dropped", f"{n_nonpos:,}"))
    invalid_units = (df["quantity"] <= 0) | (df["quantity"] % 1 != 0)
    df = df.loc[~invalid_units].copy()
    steps.append(("Rows without positive whole quantities dropped", f"{int(invalid_units.sum()):,}"))
    if df.empty:
        raise ValueError("No valid Superstore sales rows remain after cleaning. Check dates, order IDs, Sales, Quantity, Discount and Profit.")
    df["discount"], rescaled = normalize_discounts(df["discount"])
    if rescaled:
        steps.append(("Discount rescaled", "values were 0–100, converted to 0–1"))
    invalid_cost = df["profit"] > df["sales"]
    steps.append(("Lines where reported profit exceeds Sales (kept, review source)",
                  f"{int(invalid_cost.sum()):,}"))

    # 5. derived fields (kept, not dropped)
    n_loss = int((df["profit"] < 0).sum())
    steps.append(("Loss-making order lines (kept, flagged)",
                  f"{n_loss:,} ({n_loss / max(len(df), 1) * 100:.1f}% of lines)"))
    steps.append(("Cost derived", "cost = sales − profit (Superstore reports Sales after discount)"))
    if "ship date" in df.columns:
        steps.append(("Ship days derived", "ship date − order date"))

    # 6. map to the app schema
    missing_labels = 0

    def col(name: str, default: str = "Unknown") -> pd.Series:
        nonlocal missing_labels
        if name not in df.columns:
            return pd.Series(default, index=df.index)
        labels = df[name].astype("string").str.strip().replace("", pd.NA)
        missing_labels += int(labels.isna().sum())
        return labels.fillna(default).astype(str)

    out = pd.DataFrame({
        "date": df["order date"].dt.normalize(),
        "order_id": df["order id"].astype(str),
        "customer_id": col("customer id"),
        "region": col("region"),
        "city": col("city"),
        "state": col("state"),
        "category": col("category"),
        "sub_category": col("sub category"),
        "product": col("product name"),
        "channel": col("ship mode"),  # no sales channel in Superstore: ship mode is the closest field
        "customer_segment": col("segment"),
        "units": df["quantity"].astype(int),
        "discount": df["discount"].astype(float),
        "revenue": df["sales"].astype(float),
        "profit": df["profit"].astype(float),
    })
    out["cost"] = out["revenue"] - out["profit"]
    out["is_loss"] = out["profit"] < 0
    if "ship date" in df.columns:
        out["ship_days"] = (df["ship date"] - df["order date"]).dt.days
    out = out.sort_values("date").reset_index(drop=True)
    steps.append(("Missing text labels filled with Unknown", f"{missing_labels:,}"))
    steps.append(("Final dataset", f"{len(out):,} lines · {out['order_id'].nunique():,} orders · "
                                   f"{out['date'].min():%d %b %Y} → {out['date'].max():%d %b %Y}"))
    return out, pd.DataFrame(steps, columns=["Step", "Result"])
