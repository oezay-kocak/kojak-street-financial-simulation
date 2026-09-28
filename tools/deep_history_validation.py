"""Generate compact deterministic evidence for Deep History scalability."""

from __future__ import annotations

import json
import tempfile
from datetime import date
from pathlib import Path
from time import perf_counter

from kojakstreet.core.data_store import EconomicDataStore


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    output_dir = root / "docs" / "audit-data" / "deep-history-v1"
    output_dir.mkdir(parents=True, exist_ok=True)
    results = []
    for years in (20, 100, 500, 1000):
        with tempfile.TemporaryDirectory(prefix="kojak-history-") as directory:
            path = Path(directory) / "scale.duckdb"
            store = EconomicDataStore(path, auto_flush=False)
            if not store.enabled:
                raise RuntimeError("DuckDB is required for history validation")
            started = perf_counter()
            store._connection.execute(
                """
                INSERT INTO history_aggregate
                SELECT 'asset_daily', 'Stock:S' || lpad(entity::VARCHAR, 2, '0'), 'price', 'price', 'yearly',
                       make_date(1000 + year_offset, 1, 1), make_date(1000 + year_offset, 12, 31),
                       value, value * 1.08, value * 0.94, value * 1.02, value, 0.0, 365
                FROM (
                    SELECT year_offset, entity, 100.0 + year_offset * 0.2 + entity AS value
                    FROM range(?) years(year_offset) CROSS JOIN range(10) entities(entity)
                )
                """,
                [years],
            )
            insert_ms = (perf_counter() - started) * 1000.0
            started = perf_counter()
            points = store.history_series("asset_daily", "ticker", "Stock:S00", "price", pixel_budget=1200, semantic_type="price")
            query_ms = (perf_counter() - started) * 1000.0
            first = points[0]["start"] if points else None
            last = points[-1]["date"] if points else None
            store.close()
            size = path.stat().st_size
            results.append({
                "horizon_years": years,
                "synthetic": True,
                "series": 10,
                "yearly_rows": years * 10,
                "payload_points": len(points),
                "first_date": first,
                "last_date": last,
                "insert_ms": round(insert_ms, 3),
                "query_ms": round(query_ms, 3),
                "store_bytes": size,
            })
    payload = {
        "schema_version": 1,
        "method": "Synthetic yearly semantic aggregates; ten representative price series. Full-economy storage is projected separately.",
        "results": results,
    }
    (output_dir / "synthetic-scale-results.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
