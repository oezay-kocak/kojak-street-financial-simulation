"""Production-chain and country-economy news signals."""

from __future__ import annotations

from collections.abc import Callable
from types import ModuleType

from kojakstreet.core.companies import TARGET_COMPANY_COUNT, spawn_company
from kojakstreet.core.production_chains import opportunity_sector

NewsCallback = Callable[[str, str], None]


def emit_production_chain_news(daten: ModuleType, add_news_callback: NewsCallback) -> None:
    sector_stats = sector_production_stats(daten)
    strong_sector = strongest_sector(sector_stats)
    expanding_sector = fastest_expanding_sector(sector_stats)

    if expanding_sector is not None:
        sector, stats = expanding_sector
        add_news_callback(
            f" CAPACITY TREND: {sector} companies are expanding capacity by {stats['capacity_growth'] * 100:.1f}% as demand stays firm.",
            "GRUEN",
        )

    if strong_sector is not None:
        sector, stats = strong_sector
        add_news_callback(
            f" SECTOR MOMENTUM: {sector} is running hot with {stats['utilization'] * 100:.0f}% utilization and positive production scores.",
            "GRUEN",
        )

    ipo_sector = ipo_opportunity_sector(daten)
    if ipo_sector is not None:
        ticker = spawn_company(daten, sector=ipo_sector, ipo_date=daten.datum)
        asset = daten.aktien[ticker]
        add_news_callback(
            f" IPO: {ticker} {asset.get('name', ticker)} listed in {ipo_sector} to answer persistent supply-chain demand.",
            "GRUEN",
        )

    emit_country_economy_news(daten, add_news_callback)


def sector_production_stats(daten: ModuleType) -> dict[str, dict[str, float]]:
    stats: dict[str, dict[str, float]] = {}
    for asset in daten.aktien.values():
        sector = str(asset.get("branche", ""))
        if not sector:
            continue
        bucket = stats.setdefault(
            sector,
            {"count": 0.0, "capacity_growth": 0.0, "utilization": 0.0, "production_score": 0.0},
        )
        bucket["count"] += 1.0
        bucket["capacity_growth"] += float(asset.get("capacity_growth", 0.0))
        bucket["utilization"] += float(asset.get("capacity_utilization", 0.0))
        bucket["production_score"] += float(asset.get("production_score", 0.0))
    for bucket in stats.values():
        count = max(1.0, bucket["count"])
        bucket["capacity_growth"] /= count
        bucket["utilization"] /= count
        bucket["production_score"] /= count
    return stats


def fastest_expanding_sector(stats: dict[str, dict[str, float]]) -> tuple[str, dict[str, float]] | None:
    if not stats:
        return None
    sector, bucket = max(stats.items(), key=lambda item: item[1]["capacity_growth"])
    return (sector, bucket) if bucket["capacity_growth"] >= 0.018 else None


def strongest_sector(stats: dict[str, dict[str, float]]) -> tuple[str, dict[str, float]] | None:
    candidates = [
        (sector, bucket)
        for sector, bucket in stats.items()
        if bucket["utilization"] >= 0.94 and bucket["production_score"] >= 0.045
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda item: item[1]["production_score"])


def ipo_opportunity_sector(daten: ModuleType) -> str | None:
    if len(daten.aktien) >= TARGET_COMPANY_COUNT + 20:
        return None
    sector = opportunity_sector(daten)
    if sector is None:
        return None
    sector_shortage = [
        float(asset.get("supply_chain_shortage", 0.0))
        for asset in daten.aktien.values()
        if asset.get("branche") == sector
    ]
    average_shortage = sum(sector_shortage) / len(sector_shortage) if sector_shortage else 0.0
    return sector if average_shortage >= 0.12 else None


def emit_country_economy_news(daten: ModuleType, add_news_callback: NewsCallback) -> None:
    if not hasattr(daten, "makro"):
        return
    import_pressure_rows = []
    country_strength_rows = []
    trade_flow_rows = []
    for country, macro in daten.makro.items():
        profile_change = macro.pop("profile_change_news", None)
        if isinstance(profile_change, dict):
            gaining = profile_change.get("gaining_sector", "")
            losing = profile_change.get("losing_sector", "")
            suffix = f" while {losing} loses relative focus" if losing else ""
            add_news_callback(
                f" STRUCTURAL SHIFT: {country} shifts long-term specialization toward {gaining}{suffix}.",
                "WEISS",
            )
        import_dependency = float(macro.get("import_dependency", 0.0))
        export_strength = float(macro.get("export_strength", 0.0))
        bottleneck = str(macro.get("main_bottleneck", ""))
        main_sector = str(macro.get("main_sector", ""))
        if import_dependency >= 0.34 and bottleneck:
            import_pressure_rows.append((country, bottleneck, import_dependency))
        if export_strength >= 0.30 and main_sector:
            country_strength_rows.append((country, main_sector, export_strength))
        partners = macro.get("trade_partners", {})
        if partners:
            partner, value = next(iter(partners.items()))
            trade_flow_rows.append((country, str(partner), float(value)))
    emit_country_pressure_summary(import_pressure_rows, add_news_callback)
    emit_country_strength_summary(country_strength_rows, add_news_callback)
    emit_trade_flow_summary(trade_flow_rows, add_news_callback)


def emit_country_pressure_summary(rows: list[tuple[str, str, float]], add_news_callback: NewsCallback) -> None:
    if not rows:
        return
    strongest = sorted(rows, key=lambda item: item[2], reverse=True)[:5]
    details = "; ".join(f"{country}: {bottleneck} ({value * 100:.1f}% import dependency)" for country, bottleneck, value in strongest)
    add_news_callback(
        f" COUNTRY PRESSURE SUMMARY: Import pressure is elevated in {len(rows)} countries. {details}.",
        "ROT",
    )


def emit_country_strength_summary(rows: list[tuple[str, str, float]], add_news_callback: NewsCallback) -> None:
    if not rows:
        return
    strongest = sorted(rows, key=lambda item: item[2], reverse=True)[:6]
    details = "; ".join(f"{country}: {sector} ({value * 100:.1f}% export strength)" for country, sector, value in strongest)
    add_news_callback(
        f" COUNTRY STRENGTH SUMMARY: Export strength improved across {len(rows)} countries. {details}.",
        "GRUEN",
    )


def emit_trade_flow_summary(rows: list[tuple[str, str, float]], add_news_callback: NewsCallback) -> None:
    if not rows:
        return
    strongest = sorted(rows, key=lambda item: item[2], reverse=True)[:8]
    details = "; ".join(f"{country}-{partner}" for country, partner, _value in strongest)
    add_news_callback(
        f" TRADE FLOW SUMMARY: Cross-border supply-chain trade expanded across {len(rows)} country routes. Key routes: {details}.",
        "WEISS",
    )
