"""Deterministic decision briefs with auditable arithmetic and explicit limits.

These findings describe observations. They do not estimate causal effects,
invent a cause for a movement, or promise recoverable savings.
"""
from __future__ import annotations

import pandas as pd


def _amount(value: float, currency: str) -> str:
    return f"{currency}{value:,.0f}"


def _margin(frame: pd.DataFrame) -> float | None:
    revenue = float(frame["revenue"].sum())
    return float(frame["profit"].sum()) / revenue * 100 if revenue > 0 else None


def decision_brief(cur: pd.DataFrame, prev: pd.DataFrame, currency: str = "₹") -> dict:
    """Return up to three evidence/action/limitation findings for one selection.

    ``cur`` and ``prev`` must contain the same dimension selections and adjacent,
    equally sized date windows. An empty comparison is reported as unavailable;
    it is never treated as a zero-sales period. The caller owns coverage checks
    because order rows alone cannot distinguish no sales from missing data.
    """
    result = {
        "findings": [], "region_drivers": [], "loss_exposure": {},
        "discount_comparison": {}, "comparison_available": not prev.empty,
    }
    if cur.empty:
        return result

    revenue = float(cur["revenue"].sum())
    findings = result["findings"]

    # Contributions are absolute currency deltas, avoiding unstable percentage
    # growth when a region had little or no revenue in the prior window.
    if not prev.empty:
        current = cur.groupby("region")["revenue"].sum()
        previous = prev.groupby("region")["revenue"].sum()
        drivers = pd.concat([current.rename("current_revenue"), previous.rename("previous_revenue")], axis=1).fillna(0)
        drivers["change"] = drivers["current_revenue"] - drivers["previous_revenue"]
        drivers = drivers.loc[drivers["change"].abs().sort_values(ascending=False, kind="stable").index]
        result["region_drivers"] = [
            {"region": str(region), **{key: float(value) for key, value in row.items()}}
            for region, row in drivers.iterrows()
        ]
        lead = result["region_drivers"][0]
        total_change = revenue - float(prev["revenue"].sum())
        direction = "increase" if lead["change"] > 0 else "decrease" if lead["change"] < 0 else "change"
        findings.append({
            "id": "revenue_driver",
            "title": f"Review {lead['region']}: largest regional revenue movement",
            "evidence": (
                f"{lead['region']} moved from {_amount(lead['previous_revenue'], currency)} to "
                f"{_amount(lead['current_revenue'], currency)} ({_amount(lead['change'], currency)} {direction}). "
                f"Total revenue changed by {_amount(total_change, currency)}."
            ),
            "action": "Compare order volume, product mix, and promotions in this region before changing budget or stock allocation.",
            "caveat": "This locates the movement; it does not explain its cause. The comparison assumes complete data in equally sized windows and does not adjust for seasonality.",
            "metrics": {**lead, "total_revenue_change": total_change},
        })

    losses = cur[cur["profit"] < 0]
    loss_amount = -float(losses["profit"].sum())
    loss_revenue = float(losses["revenue"].sum())
    result["loss_exposure"] = {
        "loss_amount": loss_amount, "loss_line_revenue": loss_revenue,
        "loss_line_count": int(len(losses)),
        "revenue_share_pct": loss_revenue / revenue * 100 if revenue > 0 else None,
    }
    if not losses.empty:
        product_losses = losses.groupby("product")["profit"].sum().sort_values(kind="stable")
        product = str(product_losses.index[0])
        product_loss = -float(product_losses.iloc[0])
        result["loss_exposure"].update(product=product, product_loss=product_loss)
        findings.append({
            "id": "loss_exposure",
            "title": f"Check loss-making lines for {product}",
            "evidence": (
                f"{len(losses):,} loss-making lines generated {_amount(loss_revenue, currency)} in revenue "
                f"and {_amount(loss_amount, currency)} in gross losses. {product} accounts for "
                f"{_amount(product_loss, currency)} of those losses."
            ),
            "action": "Inspect pricing, discounts, and recorded costs for these lines; review exceptions before approving another promotion.",
            "caveat": "Loss exposure sums negative-profit lines, not net product profit. Some promotions may be intentional. These losses are not a savings estimate.",
            "metrics": result["loss_exposure"].copy(),
        })
    else:
        findings.append({
            "id": "loss_exposure", "title": "No negative-profit lines in this selection",
            "evidence": f"All {len(cur):,} selected lines have nonnegative recorded profit.",
            "action": "Monitor low-margin products and validate that recorded costs include the expenses relevant to your decision.",
            "caveat": "Recorded profit may exclude shipping, marketing, returns, and overhead. Nonnegative line profit does not establish business profitability.",
            "metrics": result["loss_exposure"].copy(),
        })

    full = cur[cur["discount"] == 0]
    discounted = cur[cur["discount"] > 0]
    full_margin, discounted_margin = _margin(full), _margin(discounted)
    if full_margin is not None and discounted_margin is not None:
        gap = discounted_margin - full_margin
        comparison = {
            "full_price_margin_pct": full_margin, "discounted_margin_pct": discounted_margin,
            "gap_pts": gap, "full_price_lines": int(len(full)), "discounted_lines": int(len(discounted)),
        }
        result["discount_comparison"] = comparison
        findings.append({
            "id": "discount_association", "title": "Validate the promotion margin tradeoff",
            "evidence": (
                f"Revenue-weighted margin is {full_margin:.1f}% on {len(full):,} full-price lines "
                f"and {discounted_margin:.1f}% on {len(discounted):,} discounted lines "
                f"(discounted minus full-price: {gap:+.1f} percentage points)."
            ),
            "action": "Compare like-for-like products and customer groups, then test a promotion with a control group before changing discount policy.",
            "caveat": "This is an association, not a causal discount effect. Different products, customers, and seasons can explain the gap; volume uplift is not estimated.",
            "metrics": comparison.copy(),
        })
    return result
