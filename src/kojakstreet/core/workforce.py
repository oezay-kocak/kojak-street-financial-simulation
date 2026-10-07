"""Monthly abstract workforce and simple annual demographic roots.

Pools measure available workforce equivalents, never employees. One capacity
unit demands DEMAND_SCALE equivalents, adjusted by a fixed sector intensity.
Shares are static; only report/bucket aggregation changes the frozen penalty.
Annual birth/death rates are fractions of population (0.012 means 1.2%/year).
"""
from __future__ import annotations

import hashlib
import math
import random
from datetime import date, datetime, timedelta

from kojakstreet.core.label_codes import stable_label_code

MODEL_VERSION = 1
CALIBRATION_VERSION = 1
PARTICIPATION = 0.65
POOLS = ("basic", "skilled", "highly_qualified")
DEFAULT_SHARES = dict(zip(POOLS, (0.4, 0.4, 0.2)))
DEFAULT_BIRTH_RATE = 0.012
DEFAULT_DEATH_RATE = 0.0085
RESULT_CAP = 0.01
DEMAND_SCALE = 575.0
SECTOR_MIXES = {
    "AUTOMOTIVE": (.35, .45, .20),
    "CHEMICALS": (.30, .45, .25),
    "OIL_GAS": (.45, .40, .15),
    "POWER_UTILITIES": (.30, .50, .20),
    "INDUSTRIAL_MACHINERY": (.35, .45, .20),
    "TELECOM": (.15, .50, .35),
    "RETAIL": (.65, .30, .05),
    "CONSUMER_GOODS": (.55, .35, .10),
    "FINANCIALS": (.10, .45, .45),
    "PRECIOUS_METALS_MINING": (.50, .40, .10),
    "HEALTHCARE": (.20, .45, .35),
    "TECHNOLOGY": (.10, .40, .50),
    "REAL_ESTATE": (.45, .40, .15),
    "TRANSPORT_LOGISTICS": (.50, .40, .10),
    "DEFENSE": (.25, .45, .30),
    "AGRICULTURE": (.60, .30, .10),
}
# Minimum-norm adjustment of equal intensities to the Genesis 40/40/20 mix.
# Rounded fixed constants, not a live fit or country-specific renormalization.
SECTOR_INTENSITIES = dict(zip(SECTOR_MIXES, (
    .764462, .871339, .990304, .590021, .814282, .792199, 1.419139, 1.133073,
    1.126121, .928568, 1.005827, 1.260106, .995419, .911441, .952423, 1.476473,
)))


def _day(value) -> date:
    return value.date() if isinstance(value, datetime) else value


def _rng(seed: int, country: str, stream: str) -> random.Random:
    key = f"workforce:{MODEL_VERSION}:{seed}:{country}:{stream}".encode()
    return random.Random(int.from_bytes(hashlib.sha256(key).digest(), "big"))


def country_roots(seed: int, country: str, *, heterogeneous: bool = False) -> tuple:
    """Separate feature streams never consume market or initialization RNG."""
    if not heterogeneous:
        return dict(DEFAULT_SHARES), DEFAULT_BIRTH_RATE, DEFAULT_DEATH_RATE
    rng = _rng(seed, country, "shares")
    while True:
        basic = round(rng.triangular(.30, .50, .40), 6)
        skilled = round(rng.triangular(.32, .48, .40), 6)
        qualified = 1.0 - (basic + skilled)
        if .12 <= qualified <= .30:
            break
    births = _rng(seed, country, "births").triangular(.008, .016, .012)
    deaths = _rng(seed, country, "deaths").triangular(.006, .011, .0085)
    return dict(zip(POOLS, (basic, skilled, qualified))), round(births, 7), round(deaths, 7)


def initialize(state, *, seed: int = 0, heterogeneous: bool = False,
               force: bool = False, legacy: bool = False) -> bool:
    """Initialize roots without changing population, economy, clock or RNG.

    Existing feature saves retain their active contribution exactly. Legacy
    activation uses common roots; it never reconstructs fictitious prehistory.
    """
    activated = False
    when = _day(state.datum).isoformat()
    for country, macro in state.makro.items():
        if "workforce" in macro and not force:
            validate_country(macro)
            continue
        shares, births, deaths = country_roots(seed, country, heterogeneous=heterogeneous and not legacy)
        macro["birth_rate"] = births
        macro["death_rate"] = deaths
        macro["workforce"] = {
            "model_version": MODEL_VERSION, "calibration_version": CALIBRATION_VERSION,
            "shares": shares, "activated_on": when,
            "provenance": "legacy_activation" if legacy else "world_initialization",
            "last_aggregation_date": None, "contributions": {},
            "population_interval_years": 0.0, "population_interval_end": None,
            "natural_growth": 0.0, "economic_population_adjustment": 0.0,
            "population_growth_annualized": 0.0,
        }
        activated = True
    if activated:
        aggregate(state, when=_day(state.datum), force=True)
    return activated


def validate_country(macro: dict) -> None:
    """Fail before restoring a partial, nonfinite or unsupported feature save."""
    wf = macro.get("workforce")
    if not isinstance(wf, dict) or type(wf.get("model_version")) is not int or wf.get("model_version") != MODEL_VERSION:
        raise ValueError("Invalid or unsupported workforce model")
    if wf.get("calibration_version") != CALIBRATION_VERSION:
        raise ValueError("Unsupported workforce calibration")
    shares = wf.get("shares", {})
    if set(shares) != set(POOLS) or any(type(v) not in (int, float) or not math.isfinite(v) or v < 0 or v > 1 for v in shares.values()):
        raise ValueError("Invalid workforce shares")
    if not math.isclose(sum(shares.values()), 1.0, rel_tol=0.0, abs_tol=1e-14):
        raise ValueError("Workforce shares must sum to one")
    for key in ("birth_rate", "death_rate"):
        value = macro.get(key)
        if type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value < 1:
            raise ValueError("Invalid annual birth/death rate")
    if wf.get("last_aggregation_date") is None:
        raise ValueError("Missing workforce aggregation date")
    date.fromisoformat(wf["last_aggregation_date"])
    date.fromisoformat(wf["activated_on"])
    if wf.get("provenance") not in ("world_initialization", "legacy_activation"):
        raise ValueError("Invalid workforce provenance")
    interval = wf.get("population_interval_years")
    if type(interval) not in (int, float) or not math.isfinite(interval) or interval < 0:
        raise ValueError("Invalid demographic interval")
    if interval > 0:
        date.fromisoformat(wf["population_interval_end"])
    elif wf.get("population_interval_end") is not None:
        raise ValueError("Unobserved demographic interval must have no end")
    for key in ("natural_growth", "economic_population_adjustment", "population_growth_annualized", "labor_force"):
        value = wf.get(key)
        if type(value) not in (int, float) or not math.isfinite(value):
            raise ValueError(f"Invalid workforce {key}")
    for field in ("supply", "demand", "coverage", "shortage"):
        values = wf.get(field, {})
        if set(values) != set(POOLS) or any(type(v) not in (int, float) or not math.isfinite(v) or v < 0 for v in values.values()):
            raise ValueError(f"Invalid workforce {field}")
        if field == "shortage" and any(v > 1 for v in values.values()):
            raise ValueError("Workforce shortage exceeds one")
    contributions = wf.get("contributions", {})
    if set(contributions) != set(SECTOR_MIXES) or any(type(v) not in (int, float) or not math.isfinite(v) or not -RESULT_CAP <= v <= 0 for v in contributions.values()):
        raise ValueError("Invalid frozen workforce contribution")


def sector_code(asset: dict) -> str:
    code = asset.get("sector_code") or stable_label_code(asset.get("branche", ""), category="sector")
    if code not in SECTOR_MIXES:
        raise ValueError(f"Unknown workforce sector: {code}")
    return code


def shortage_contribution(shortage: tuple, mix: tuple) -> float:
    weighted = max(0.0, min(1.0, sum(s * w for s, w in zip(shortage, mix))))
    return -RESULT_CAP * weighted * weighted if weighted else 0.0


def aggregate(state, *, when: date | None = None, force: bool = False) -> bool:
    """One 1,280×3 scan per report, never called by the ordinary day path."""
    when_text = _day(when or state.datum).isoformat()
    macros = {c: m for c, m in state.makro.items() if "workforce" in m}
    if not macros or (not force and all(m["workforce"]["last_aggregation_date"] == when_text for m in macros.values())):
        return False
    demands = {c: [0.0, 0.0, 0.0] for c in macros}
    for asset in state.aktien.values():
        total = demands.get(asset.get("land"))
        if total is None:
            continue
        code = sector_code(asset)
        capacity = max(0.0, float(asset.get("production_capacity", 0.0)))
        size = capacity * DEMAND_SCALE * SECTOR_INTENSITIES[code]
        for index, weight in enumerate(SECTOR_MIXES[code]):
            total[index] += size * weight
    for country, macro in macros.items():
        wf = macro["workforce"]
        labor = float(macro["bevoelkerung"]) * PARTICIPATION
        supply = tuple(labor * wf["shares"][p] for p in POOLS)
        demand = demands[country]
        shortage = tuple(max(0.0, d - s) / max(1e-12, d) for s, d in zip(supply, demand))
        wf.update({
            "last_aggregation_date": when_text, "labor_force": labor,
            "supply": dict(zip(POOLS, supply)), "demand": dict(zip(POOLS, demand)),
            "coverage": dict(zip(POOLS, (s / d if d > 0 else 1.0 for s, d in zip(supply, demand)))),
            "shortage": dict(zip(POOLS, shortage)),
            "contributions": {code: shortage_contribution(shortage, mix) for code, mix in SECTOR_MIXES.items()},
        })
    return True


def company_contribution(state, asset: dict) -> float:
    wf = state.makro.get(asset.get("land"), {}).get("workforce")
    return wf["contributions"][sector_code(asset)] if wf else 0.0


def advance_population(macro: dict, years: float, *, floor: float, when: date) -> None:
    """Compound annual natural+reduced economic rates for the actual interval."""
    before = float(macro["bevoelkerung"])
    if before <= 0 or years <= 0:
        raise ValueError("Population and demographic interval must be positive")
    old_monthly = max(-.0025, min(.0035, (float(macro.get("bip_prozent", 0.0)) - .005) * .025
                      - max(0.0, float(macro.get("arbeitslosigkeit", .06)) - .08) * .010))
    natural = float(macro["birth_rate"]) - float(macro["death_rate"])
    economic = max(-.006, min(.003, old_monthly * 12 * .25))
    annual = max(-.01, min(.015, natural + economic))
    after = max(floor, before * math.exp(math.log1p(annual) * years))
    realized = after / before - 1.0
    macro["bevoelkerung"] = after
    macro["population_growth"] = realized
    wf = macro["workforce"]
    wf.update({"population_interval_years": years, "population_interval_end": when.isoformat(),
               "natural_growth": math.expm1(math.log1p(natural) * years),
               "economic_population_adjustment": economic,
               "population_growth_annualized": math.expm1(math.log1p(realized) / years)})


def integrate_coarse(state, before_population: dict, before_companies: dict,
                     *, when: date, years: float) -> None:
    """Integrate only the feature at monthly spacing inside a coarse bucket.

    Interpolate the existing coarse baseline paths; apply the same monthly
    result/health/growth equations to their incremental workforce component.
    Each step uses the preceding step's frozen penalty, then aggregates demand.
    No macro/market replay, extra RNG or once-per-year result shortcut occurs.
    """
    if not any("workforce" in m for m in state.makro.values()):
        return
    end_population = {c: m["bevoelkerung"] for c, m in state.makro.items()}
    months = years * 12
    company_paths = []
    for ticker, asset in state.aktien.items():
        old_revenue, old_capacity, old_cash = before_companies[ticker]
        base_revenue = asset["revenue"]
        base_capacity = asset["production_capacity"]
        company_paths.append((asset, old_capacity, base_capacity,
                              math.log(base_revenue / old_revenue) / months,
                              base_revenue, asset["fcf_margin"], old_revenue, old_cash))
        asset["_workforce_coarse_factor"] = 1.0
    elapsed = 0.0
    while elapsed < months:
        step = min(1.0, months - elapsed)
        elapsed = min(months, elapsed + step)
        for asset, old_capacity, base_capacity, log_base, base_revenue, base_margin, old_revenue, old_cash in company_paths:
            delta = company_contribution(state, asset)
            old_health = float(asset.get("_workforce_coarse_health", 0.0))
            decay = .78 ** step
            health = delta + (old_health - delta) * decay
            # Geometric monthly recurrence, with a fractional last-month integral.
            avg_health = delta + (old_health - delta) * .78 * (1 - decay) / (.22 * step)
            growth = .18 * (.35 * delta + .65 * avg_health)
            relative_growth = growth / math.exp(log_base)
            factor = asset["_workforce_coarse_factor"] * math.exp(math.log1p(relative_growth) * step)
            asset["_workforce_coarse_factor"] = factor
            asset["_workforce_coarse_health"] = health
            asset["production_capacity"] = old_capacity * math.exp(math.log(base_capacity / old_capacity) * elapsed / months) * factor
            if elapsed == months:
                asset["revenue"] = max(1.0, base_revenue * factor)
                asset["_workforce_coarse_base_margin"] = base_margin
                asset["fcf_margin"] = max(-.08, min(.30, base_margin + .06 * delta + .16 * health))
                asset["free_cash_flow_margin"] = asset["fcf_margin"]
                asset["free_cash_flow"] = asset["revenue"] * asset["fcf_margin"]
                # Propagate adjusted fundamentals through the existing coarse
                # cash equation, rather than accumulating unadjusted FCF.
                asset["cash_reserves"] = max(0.0, min(asset["revenue"] * 2.5,
                    old_cash * asset["revenue"] / old_revenue
                    + max(0.0, asset["free_cash_flow"]) * years * .25))
        for country, macro in state.makro.items():
            start, end = before_population[country], end_population[country]
            macro["bevoelkerung"] = end if elapsed == months else start * math.exp(math.log(end / start) * elapsed / months)
        remaining_days = round((months - elapsed) / 12 * 365.2425)
        aggregate(state, when=when - timedelta(days=remaining_days), force=True)
    for asset, *_ in company_paths:
        del asset["_workforce_coarse_factor"]


def projection(macro: dict) -> dict:
    """Small selected-country future UI data; never copies companies/history."""
    wf = macro.get("workforce")
    if not wf:
        return {}
    return {
        "model_version": MODEL_VERSION, "units": "workforce_equivalents",
        "population": macro["bevoelkerung"], "birth_rate": macro["birth_rate"],
        "death_rate": macro["death_rate"], "population_growth": macro.get("population_growth", 0.0) if wf["population_interval_years"] else None,
        "population_interval_years": wf["population_interval_years"],
        "population_interval_end": wf["population_interval_end"],
        "population_growth_annualized": wf["population_growth_annualized"] if wf["population_interval_years"] else None,
        "unemployment": macro["arbeitslosigkeit"], "last_aggregation_date": wf["last_aggregation_date"],
        "pools": {p: {key: wf[key][p] for key in ("supply", "demand", "coverage", "shortage")}
                  for p in POOLS},
    }
