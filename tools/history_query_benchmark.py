"""Scale-test chart-history queries from a measured one-year DuckDB corpus.

The benchmark repeats the complete one-year fact population with shifted dates
to create physical 10- and 20-year tables.  Values repeat, so this measures
storage/query scaling only; it is not an economic simulation result.
"""

from __future__ import annotations

import argparse
import json
import statistics
import time
from pathlib import Path

import duckdb


def _timed(connection, sql: str, params: list, repeats: int) -> dict:
    durations, rows = [], 0
    for _ in range(repeats):
        started = time.perf_counter()
        result = connection.execute(sql, params).fetchall()
        durations.append(time.perf_counter() - started)
        rows = len(result)
    return {
        "rows": rows,
        "min_ms": min(durations) * 1000,
        "median_ms": statistics.median(durations) * 1000,
        "max_ms": max(durations) * 1000,
    }


def run(source: Path, scratch: Path, output: Path, repeats: int) -> dict:
    scratch.parent.mkdir(parents=True, exist_ok=True)
    scratch.unlink(missing_ok=True)
    connection = duckdb.connect(str(scratch))
    escaped = str(source.resolve()).replace("'", "''")
    connection.execute(f"ATTACH '{escaped}' AS source (READ_ONLY)")
    build_started = time.perf_counter()
    connection.execute(
        """
        CREATE TABLE asset_daily_20y AS
        SELECT date + CAST(year_offset * 365 AS INTEGER) AS date,
               ticker, asset_type, name, region, sector, price, change_pct,
               market_cap, revenue, free_cash_flow, rating
        FROM source.asset_daily CROSS JOIN range(20) years(year_offset)
        """
    )
    connection.execute(
        """
        CREATE TABLE product_daily_20y AS
        SELECT date + CAST(year_offset * 365 AS INTEGER) AS date,
               code, item_type, name, category, produced, demanded, inventories,
               shortage, pressure, price
        FROM source.product_daily CROSS JOIN range(20) years(year_offset)
        """
    )
    build_seconds = time.perf_counter() - build_started
    stock = connection.execute("SELECT ticker FROM source.asset_daily WHERE asset_type='Stock' LIMIT 1").fetchone()[0]
    product = connection.execute("SELECT code FROM source.product_daily LIMIT 1").fetchone()[0]
    minimum_date = connection.execute("SELECT MIN(date) FROM asset_daily_20y").fetchone()[0]
    results = {}
    for years in (1, 10, 20):
        cutoff = connection.execute("SELECT ?::DATE + CAST(? * 365 AS INTEGER)", [minimum_date, years]).fetchone()[0]
        cases = {
            "asset_all": ("SELECT date, price FROM asset_daily_20y WHERE ticker=? AND asset_type='Stock' AND date < ? ORDER BY date", [stock, cutoff]),
            "asset_limit_520": ("SELECT date, price FROM asset_daily_20y WHERE ticker=? AND asset_type='Stock' AND date < ? ORDER BY date DESC LIMIT 520", [stock, cutoff]),
            "asset_yearly_ohlc": (
                "SELECT date_trunc('year', date), first(price ORDER BY date), max(price), min(price), last(price ORDER BY date) FROM asset_daily_20y WHERE ticker=? AND asset_type='Stock' AND date < ? GROUP BY 1 ORDER BY 1",
                [stock, cutoff],
            ),
            "product_all": ("SELECT date, produced, demanded, inventories FROM product_daily_20y WHERE code=? AND date < ? ORDER BY date", [product, cutoff]),
            "product_monthly_semantic": (
                "SELECT date_trunc('month', date), avg(produced), avg(demanded), last(inventories ORDER BY date), avg(shortage), max(shortage) FROM product_daily_20y WHERE code=? AND date < ? GROUP BY 1 ORDER BY 1",
                [product, cutoff],
            ),
        }
        results[str(years)] = {name: _timed(connection, sql, params, repeats) for name, (sql, params) in cases.items()}
    counts = {
        "asset_daily_20y": connection.execute("SELECT COUNT(*) FROM asset_daily_20y").fetchone()[0],
        "product_daily_20y": connection.execute("SELECT COUNT(*) FROM product_daily_20y").fetchone()[0],
    }
    connection.execute("CHECKPOINT")
    connection.close()
    payload = {
        "method": "Physical 20-year scale corpus made by date-shifting all rows from a measured one-year production run.",
        "economic_values": "repeated; query/storage benchmark only",
        "source": str(source),
        "build_seconds": build_seconds,
        "scratch_file_bytes": scratch.stat().st_size,
        "physical_rows": counts,
        "repeats": repeats,
        "results": results,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--scratch", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--repeats", type=int, default=3)
    args = parser.parse_args()
    result = run(args.source, args.scratch, args.output, args.repeats)
    print(json.dumps({"build_seconds": result["build_seconds"], "rows": result["physical_rows"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
