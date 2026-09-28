"""Build the compact Established World V1 acceptance summary from raw evidence."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _economic_summary(payload: dict[str, Any]) -> dict[str, Any]:
    distributions = payload["distributions"]
    lifecycle = payload["universe"]["lifecycle_yearly"][-1]
    ratings = payload["universe"]["ratings_final"]
    companies = ratings["companies"]
    return {
        "run": payload["run"],
        "debt_to_gdp": distributions["macro"]["debt_to_gdp"],
        "interest_burden": distributions["macro"]["interest_burden"],
        "credit_stress": distributions["global"]["regime_credit_stress"],
        "company_cash": distributions["company"]["cash_reserves"],
        "company_market_cap": distributions["company"]["market_cap"],
        "company_ratings": companies,
        "sovereign_ratings": ratings["sovereigns"],
        "aaa_share": companies.get("AAA", 0) / max(1, lifecycle["active_companies"]),
        "lifecycle_final": lifecycle,
        "regimes": payload["regimes"],
        "anomalies": payload["anomalies"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    root = args.project_root.resolve()
    evidence = root / "docs" / "audit-data" / "established-world-v1"
    baseline = root / "docs" / "audit-data" / "economic-integrity-v1"
    performance = _load(evidence / "performance-1y-flush90.json")["generation"]
    selected_years_per_minute = float(performance["simulated_years_per_minute"])
    payload: dict[str, Any] = {
        "schema_version": 1,
        "selected_generation_batch_days": 90,
        "performance": {
            "selected_1y": performance,
            "memory_probe_90d": _load(evidence / "performance-90d-flush90.json")["generation"],
            "rejected_365d_batch": _load(evidence / "performance-1y-flush365.json")["generation"],
            "estimated_minutes": {
                str(years): years / selected_years_per_minute for years in (50, 75, 100)
            },
        },
        "economic": {},
    }
    pairs = (
        ("5y", baseline / "economic-seed-202-5y-core.json", evidence / "economic-seed-202-5y-post.json"),
        ("20y", baseline / "economic-seed-101-20y-core.json", evidence / "economic-seed-101-20y-post.json"),
    )
    for label, before_path, after_path in pairs:
        if after_path.is_file():
            payload["economic"][label] = {
                "baseline": _economic_summary(_load(before_path)),
                "post_integration": _economic_summary(_load(after_path)),
            }
    output = evidence / "established-world-v1-summary.json"
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
