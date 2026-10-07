"""Bounded, deterministic roots for a Day-1 world; never used by day steps."""
from __future__ import annotations

import hashlib
import math
import random
from collections import Counter
from contextvars import ContextVar
from dataclasses import dataclass

INITIALIZATION_VERSION = 1
POPULATION_BUDGET = 400_000_000
GDP_BUDGET = 100_000.0
MARKET_CAP_BUDGET = 1_280_000_000_000
# Counts, then inclusive bands. The original requested bands need no widening.
POPULATION_CLASSES = (
    ("Very large", 2, 35_000_000, 50_000_000),
    ("Large", 4, 24_000_000, 35_000_000),
    ("Medium", 7, 15_000_000, 25_000_000),
    ("Small", 5, 8_000_000, 17_000_000),
    ("Very small", 2, 5_000_000, 10_000_000),
)
COMPANY_CLASSES = (
    ("Mega Cap", 19, 8_000_000_000, 18_000_000_000),
    ("Large Cap", 128, 3_000_000_000, 8_000_000_000),
    ("Upper Mid", 256, 1_300_000_000, 3_000_000_000),
    ("Mid Cap", 384, 600_000_000, 1_500_000_000),
    ("Small Cap", 365, 200_000_000, 800_000_000),
    ("Micro Cap", 128, 80_000_000, 300_000_000),
)


@dataclass(frozen=True)
class InitializationRoots:
    population: dict[str, int]
    population_class: dict[str, str]
    productivity: dict[str, float]
    gdp: dict[str, float]
    company_caps: dict[tuple[str, str], tuple[int, ...]]
    company_classes: dict[tuple[str, str], tuple[str, ...]]
    requested_country_caps: dict[str, int]
    country_caps: dict[str, int]


# Set only around daten's initial module execution, reset even on failure.
initialization_roots: ContextVar[InitializationRoots | None] = ContextVar("initialization_roots", default=None)


def _stream(seed: int, purpose: str) -> random.Random:
    identity = f"heterogeneous:{INITIALIZATION_VERSION}:{int(seed)}:{purpose}".encode()
    return random.Random(int.from_bytes(hashlib.sha256(identity).digest(), "big"))


def _correlation(left: list[float], right: list[float]) -> float:
    lmean, rmean = sum(left) / len(left), sum(right) / len(right)
    a, b = [v - lmean for v in left], [v - rmean for v in right]
    return sum(x * y for x, y in zip(a, b)) / math.sqrt(sum(x * x for x in a) * sum(y * y for y in b))


def bounded_budget(weights: list[float], lower: list[int], upper: list[int], total: int) -> list[int]:
    """Project positive weights into fixed bands, with exact integer accounting."""
    if not (len(weights) == len(lower) == len(upper)) or any(w <= 0 or not math.isfinite(w) for w in weights):
        raise ValueError("Invalid initialization weights")
    if any(lo > hi for lo, hi in zip(lower, upper)) or not sum(lower) <= total <= sum(upper):
        raise ValueError("Initialization budget is outside the feasible bands")
    low, high = 0.0, max(hi / w for hi, w in zip(upper, weights))
    for _ in range(80):
        scale = (low + high) / 2
        amounts = [max(lo, min(hi, w * scale)) for w, lo, hi in zip(weights, lower, upper)]
        if sum(amounts) < total:
            low = scale
        else:
            high = scale
    amounts = [max(lo, min(hi, w * high)) for w, lo, hi in zip(weights, lower, upper)]
    result = [int(value) for value in amounts]
    remaining = total - sum(result)
    order = sorted(range(len(result)), key=lambda i: amounts[i] - result[i], reverse=remaining >= 0)
    for i in order:
        change = min(1, remaining, upper[i] - result[i]) if remaining >= 0 else max(-1, remaining, lower[i] - result[i])
        result[i] += change
        remaining -= change
        if not remaining:
            break
    if remaining or sum(result) != total:
        raise ValueError("Unable to conserve the initialization budget")
    return result


def _company_sizes(rng: random.Random) -> list[tuple[str, int, int, int]]:
    classes = [(name, lo, hi) for name, count, lo, hi in COMPANY_CLASSES for _ in range(count)]
    minimum = sum(lo for _, lo, _ in classes)
    # Only the headroom is distributed, rather than scaling values below bands.
    headroom = bounded_budget(
        [(hi - lo) * rng.uniform(.10, 1.0) for _, lo, hi in classes],
        [0] * len(classes), [hi - lo for _, lo, hi in classes], MARKET_CAP_BUDGET - minimum,
    )
    return sorted([(name, lo + extra, lo, hi) for (name, lo, hi), extra in zip(classes, headroom)],
                  key=lambda row: row[1], reverse=True)


def generate_roots(seed: int, countries: list[str], sectors: list[str]) -> InitializationRoots:
    """Create fixed coverage and size classes without consuming simulation RNG."""
    if len(countries) != 20 or len(sectors) != 16 or len(set(countries)) != 20 or len(set(sectors)) != 16:
        raise ValueError("Heterogeneous initialization requires the audited 20 × 16 universe")
    from kojakstreet.core.fundamentals import SECTOR_PROFILES
    from kojakstreet.core.production_chains import _initial_country_sector_focus

    pop_rng = _stream(seed, "population")
    tiers = [(name, lo, hi) for name, count, lo, hi in POPULATION_CLASSES for _ in range(count)]
    populations = bounded_budget([pop_rng.uniform(lo, hi) for _, lo, hi in tiers],
                                 [lo for _, lo, _ in tiers], [hi for _, _, hi in tiers], POPULATION_BUDGET)
    # Sorting preserves every rank's ordered lower/upper band and tier counts.
    populations.sort(reverse=True)
    placement = countries.copy()
    pop_rng.shuffle(placement)
    population = dict(zip(placement, populations))
    population_class = {country: tier[0] for country, tier in zip(placement, tiers)}

    productivity_rng = _stream(seed, "productivity")
    for _ in range(256):
        productivity = {country: productivity_rng.uniform(.70, 1.40) for country in countries}
        weights = [population[c] * productivity[c] for c in countries]
        # The existing GDP floor must not reset a small economy at its first report.
        correlation = _correlation([population[c] for c in countries], weights)
        if (min(weights) / sum(weights) >= .010 and .10 <= max(weights) / sum(weights) <= .20
                and .60 <= correlation <= .90):
            break
    else:
        raise ValueError("Unable to satisfy GDP concentration guard")
    units = bounded_budget(weights, [1_000_000_000] * 20, [20_000_000_000] * 20, 100_000_000_000)
    gdp = {c: value / 1_000_000 for c, value in zip(countries, units)}
    # The legacy aggregate uses ordinary sum; conserve that exact representation.
    gdp[countries[-1]] = GDP_BUDGET - sum(gdp[c] for c in countries[:-1])

    market_rng = _stream(seed, "capital_markets")
    structure = {}
    for c in countries:
        focus = _initial_country_sector_focus(c, set())
        structure[c] = sum(SECTOR_PROFILES[s]["fcf_margin"] / SECTOR_PROFILES[s]["ps"] for s in focus)
    variation = {c: market_rng.uniform(.60, 1.50) for c in countries}
    weights = [.65 * gdp[c] / GDP_BUDGET + .20 * structure[c] / sum(structure.values())
               + .15 * variation[c] / sum(variation.values()) for c in countries]
    requested = bounded_budget(weights, [0] * 20, [MARKET_CAP_BUDGET // 5] * 20, MARKET_CAP_BUDGET)
    targets = dict(zip(countries, requested))
    buckets: dict[str, list[tuple[str, int, int, int]]] = {c: [] for c in countries}
    totals = Counter()
    mega_counts = Counter()
    for item in _company_sizes(_stream(seed, "company_sizes")):
        name, value, _, _ = item
        eligible = [c for c in countries if len(buckets[c]) < 64 and (name != "Mega Cap" or mega_counts[c] < 2)]
        c = max(eligible, key=lambda c: targets[c] - totals[c])
        buckets[c].append(item)
        totals[c] += value
        mega_counts[c] += name == "Mega Cap"

    lower = [sum(item[2] for item in buckets[c]) for c in countries]
    upper = [min(MARKET_CAP_BUDGET // 5, sum(item[3] for item in buckets[c])) for c in countries]
    # Fixed class counts may constrain an individual 64-company country's target.
    # Preserve bands and world budget rather than silently moving a class boundary.
    country_amounts = bounded_budget(requested, lower, upper, MARKET_CAP_BUDGET)
    company_caps = {}
    company_classes = {}
    placement_rng = _stream(seed, "sector_placement")
    for c, amount in zip(countries, country_amounts):
        items = buckets[c]
        amounts = bounded_budget([item[1] for item in items], [item[2] for item in items], [item[3] for item in items], amount)
        slots = [(s, i) for s in sectors for i in range(4)]
        placement_rng.shuffle(slots)
        # Static preferred sector membership influences placement, never rotating intensity.
        preferred = set(_initial_country_sector_focus(c, set()))
        slots.sort(key=lambda slot: slot[0] not in preferred)
        by_slot = dict(zip(slots, zip(amounts, (item[0] for item in items))))
        for s in sectors:
            company_caps[c, s] = tuple(by_slot[s, i][0] for i in range(4))
            company_classes[c, s] = tuple(by_slot[s, i][1] for i in range(4))
    return InitializationRoots(population, population_class, productivity, gdp, company_caps, company_classes,
                               targets, dict(zip(countries, country_amounts)))


def finalize_initialization(state) -> None:
    """Derive Day-1 marks from the finished books, without a simulation tick."""
    from kojakstreet.core.financial_products import _price_product
    from kojakstreet.core.global_macro import _country_aggregates, _observed_government_yields
    from kojakstreet.core.market_regime import update_market_regime

    aggregates = _country_aggregates(state)
    observed = _observed_government_yields(state, aggregates["avg_rate"])
    macro = state.global_macro
    macro.update({
        "central_bank_balance_sheets": aggregates["balance_sheets"],
        "global_gdp_growth": aggregates["avg_growth"],
        "global_cpi": aggregates["avg_inflation"],
        "global_unemployment": aggregates["avg_unemployment"],
        "avg_3y_yield": observed["3y"], "avg_5y_yield": observed["5y"], "avg_10y_yield": observed["10y"],
        "yield_curve_3y10y": max(-.035, min(.055, observed["10y"] - observed["3y"])),
        "net_liquidity": macro["global_m2"] + aggregates["balance_sheets"] - macro["rrp"] - macro["tga"],
    })
    update_market_regime(state)
    date = state.datum.strftime("%d.%m.%Y")
    for key, value in macro.items():
        state.GLOBAL_MACRO_HISTORIE[key] = [(value, date, "")]
    for ticker, product in state.derivatives.items():
        product["kurs"] = max(.01, _price_product(state, ticker, product))
        product["aenderung"] = 0.0


def validate_saved_initialization(metadata: dict, simulation_seed: int | None) -> None:
    """Validate new-mode identity before a checkpoint can mutate the live world."""
    from kojakstreet.core.established_world import GENERATOR_VERSION
    from kojakstreet.core.history import (
        ECONOMIC_MODEL_VERSION,
        HISTORY_SCHEMA_VERSION,
        LEGACY_ECONOMIC_MODEL_VERSION,
    )

    if (metadata.get("heterogeneous_initialization_version") != INITIALIZATION_VERSION
            or (metadata.get("generator_version"), metadata.get("economic_model_version"),
                metadata.get("history_schema_version")) not in {
                    (GENERATOR_VERSION, ECONOMIC_MODEL_VERSION, HISTORY_SCHEMA_VERSION),
                    (3, ECONOMIC_MODEL_VERSION, 2),
                    (2, LEGACY_ECONOMIC_MODEL_VERSION, 1),
                }
            or metadata.get("prehistory_years") != 0
            or type(metadata.get("seed")) is not int
            or metadata["seed"] != simulation_seed):
        raise ValueError("Invalid or unsupported Heterogeneous initialization identity")
