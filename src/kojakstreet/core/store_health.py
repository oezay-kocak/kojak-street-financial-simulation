"""Health summaries for the structured simulation store."""

from __future__ import annotations

from typing import Any


def structured_store_health(current_rows: dict[str, list[tuple[Any, ...]]]) -> dict[str, int | bool]:
    """Return lightweight coverage counts for current-state tables."""

    counts = {
        "assets": len(current_rows.get("asset_current", [])),
        "products": len(current_rows.get("product_current", [])),
        "companies": len(current_rows.get("company_current", [])),
        "company_flows": len(current_rows.get("company_output_current", [])),
        "country_trade_rows": len(current_rows.get("country_trade_current", [])),
        "fund_allocations": len(current_rows.get("fund_allocation_current", [])),
        "countries": len(current_rows.get("country_current", [])),
        "forex_pairs": len(current_rows.get("forex_current", [])),
        "bonds": len(current_rows.get("bond_current", [])),
        "portfolio": len(current_rows.get("portfolio_current", [])),
        "events": len(current_rows.get("event_current", [])),
        "phase_metrics": len(current_rows.get("phase_metric_current", [])),
    }
    counts["structured_ready"] = bool(
        counts["assets"]
        and counts["products"]
        and counts["companies"]
        and counts["company_flows"]
        and counts["country_trade_rows"]
        and counts["countries"]
    )
    counts["duckdb_truth_ready"] = bool(counts["structured_ready"] and counts["phase_metrics"] >= 0)
    return counts
