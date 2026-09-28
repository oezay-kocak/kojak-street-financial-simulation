from __future__ import annotations

from types import SimpleNamespace

import pytest

from kojakstreet.core.companies import bankrupt_tickers, remove_bankrupt_companies
from kojakstreet.core.company_lifecycle import monthly_energy_shock, sector_energy_factor, update_company_rating
from kojakstreet.core.financial_products import _cds_price
from kojakstreet.core.fiscal import ensure_country_financials, update_country_financials
from kojakstreet.core.fundamentals import (
    SECTOR_PROFILES,
    consume_fundamental_repricing,
    fundamental_price_signal,
    stage_fundamental_repricing,
)
from kojakstreet.core.market_calculations import stock_energy_price_signal
from kojakstreet.core.macro_calculations import sovereign_rating_target, update_sovereign_ratings
from kojakstreet.core.ratings import rating_index


def _macro(*, debt_ratio: float = 0.62, growth: float = 0.015, unemployment: float = 0.052) -> dict:
    gdp = 5_000.0
    return {
        "bip_abs": gdp,
        "bip_prozent": growth,
        "inflation": 0.02,
        "arbeitslosigkeit": unemployment,
        "zins": 0.035,
        "rating": "BBB",
        "government_debt": gdp * debt_ratio,
        "private_credit": gdp * 0.92,
        "credit_growth": 0.018,
    }


def test_fiscal_accounting_is_monthly_and_high_debt_creates_consolidation() -> None:
    ordinary = SimpleNamespace(makro={"A": _macro()})
    stressed = SimpleNamespace(makro={"A": _macro(debt_ratio=2.0)})
    ensure_country_financials(ordinary)
    ensure_country_financials(stressed)
    initial_debt = ordinary.makro["A"]["government_debt"]

    update_country_financials(ordinary, "A")
    annualized_deficit = ordinary.makro["A"]["fiscal_deficit"]
    assert ordinary.makro["A"]["government_debt"] == pytest.approx(initial_debt + annualized_deficit / 12.0)

    for _ in range(60):
        update_country_financials(stressed, "A")
    assert stressed.makro["A"]["fiscal_adjustment"] > 0.04
    assert stressed.makro["A"]["fiscal_deficit"] < 0.0
    assert stressed.makro["A"]["debt_to_gdp"] < 2.0
    assert stressed.makro["A"]["sovereign_funding_rate"] > stressed.makro["A"]["zins"]


def test_severe_recession_can_still_worsen_the_fiscal_balance() -> None:
    normal = SimpleNamespace(makro={"A": _macro(debt_ratio=0.9)})
    recession = SimpleNamespace(makro={"A": _macro(debt_ratio=0.9, growth=-0.06, unemployment=0.16)})
    update_country_financials(normal, "A")
    update_country_financials(recession, "A")
    assert recession.makro["A"]["fiscal_deficit"] > normal.makro["A"]["fiscal_deficit"]


def test_sovereign_ratings_follow_persistent_fundamentals_without_drift_to_default() -> None:
    healthy = _macro()
    target, score = sovereign_rating_target(healthy)
    assert rating_index(target) < rating_index("BBB")
    assert score > 0.0
    healthy_world = SimpleNamespace(makro={"A": healthy})
    for _ in range(36):
        update_sovereign_ratings(healthy_world)
    assert rating_index(healthy["rating"]) < rating_index("BBB")

    stressed = _macro(debt_ratio=1.8, growth=-0.04, unemployment=0.15)
    stressed.update(inflation=0.12, debt_to_gdp=1.8, interest_burden=0.15)
    stressed_world = SimpleNamespace(makro={"A": stressed})
    update_sovereign_ratings(stressed_world)
    assert stressed["rating"] == "BBB"
    for _ in range(60):
        update_sovereign_ratings(stressed_world)
    assert rating_index(stressed["rating"]) > rating_index("BB")
    assert stressed["rating"] != "D"
    assert stressed["sovereign_rating_target"] == "CC"


def _company(**updates) -> dict:
    asset = {
        "rating": "BBB",
        "market_cap": 1_000_000_000.0,
        "revenue": 500_000_000.0,
        "revenue_growth": 0.02,
        "free_cash_flow": 60_000_000.0,
        "fcf_margin": 0.12,
        "cash_reserves": 80_000_000.0,
        "debt": 250_000_000.0,
        "debt_to_market_cap": 0.25,
        "interest_coverage": 5.0,
    }
    asset.update(updates)
    return asset


def test_company_rating_migration_has_inertia_in_both_directions() -> None:
    strong = _company(free_cash_flow=120_000_000.0, fcf_margin=0.24, interest_coverage=8.0)
    update_company_rating(strong)
    assert strong["rating"] == "BBB"
    for _ in range(18):
        update_company_rating(strong)
    assert rating_index("BBB") - rating_index(strong["rating"]) in range(1, 5)
    assert strong["rating"] != "AAA"

    weak = _company(
        free_cash_flow=-30_000_000.0,
        fcf_margin=-0.06,
        cash_reserves=2_000_000.0,
        debt_to_market_cap=1.0,
        interest_coverage=-1.0,
        revenue_growth=-0.06,
    )
    update_company_rating(weak)
    assert weak["rating"] == "BBB"
    for _ in range(6):
        update_company_rating(weak)
    assert rating_index(weak["rating"]) > rating_index("BBB")
    assert weak["distress_months"] >= 6


def test_company_distress_can_recover_or_end_in_failure() -> None:
    recovered = _company(distress_months=6)
    for _ in range(3):
        update_company_rating(recovered)
    assert recovered["distress_months"] == 0

    failed = _company(
        rating="B-",
        free_cash_flow=-30_000_000.0,
        cash_reserves=0.0,
        debt_to_market_cap=1.2,
        interest_coverage=-1.0,
        distress_months=9,
    )
    assert bankrupt_tickers(SimpleNamespace(aktien={"FAIL": failed})) == ["FAIL"]


def test_company_failure_preserves_reference_integrity() -> None:
    failed = _company(rating="B-", free_cash_flow=-30_000_000.0, cash_reserves=0.0, debt_to_market_cap=1.2, distress_months=9)
    data = SimpleNamespace(
        aktien={"FAIL": failed, "LIVE": _company()},
        depot={"FAIL": {"stueck": 1.0}},
        perpetuals={},
        anleihen=[{"ticker": "FAIL", "typ": "CORP"}],
        bond_market=[{"ticker": "FAIL", "issuer_type": "Corporate", "price": 100.0}],
        derivatives={"CDS": {"instrument_type": "Corporate Credit Default Swap", "underlying": "FAIL"}},
        fonds={"F": {"underlyings": [
            {"asset_type": "Stock", "ticker": "FAIL", "weight": 0.4},
            {"asset_type": "Stock", "ticker": "LIVE", "weight": 0.6},
        ]}},
        retired_company_tickers=set(),
    )
    remove_bankrupt_companies(data, ["FAIL"])
    assert data.anleihen[0]["defaulted"] is True
    assert data.bond_market[0]["rating"] == "D"
    assert data.derivatives["CDS"]["credit_event"] is True
    assert data.fonds["F"]["underlyings"] == [{"asset_type": "Stock", "ticker": "LIVE", "weight": 1.0}]


def test_sector_norms_remove_initial_absolute_value_bonus() -> None:
    for sector in ("Öl und Gas", "Finanzen", "Technologie"):
        profile = SECTOR_PROFILES[sector]
        market_cap = 1_000_000_000.0
        revenue = market_cap / profile["ps"]
        asset = {
            "branche": sector,
            "market_cap": market_cap,
            "revenue": revenue,
            "revenue_growth": 0.0,
            "previous_revenue_growth": 0.0,
            "free_cash_flow": revenue * profile["fcf_margin"],
            "fcf_margin": profile["fcf_margin"],
            "previous_fcf_margin": profile["fcf_margin"],
            "dividend_yield": profile["dividend_yield"],
            "previous_dividend_yield": profile["dividend_yield"],
        }
        assert fundamental_price_signal(asset) == pytest.approx(0.0)


def test_fundamental_repricing_is_finite_and_does_not_double_count_eps() -> None:
    asset = _company(
        branche="Technologie",
        previous_revenue_growth=0.0,
        previous_fcf_margin=0.10,
        dividend_yield=0.01,
        previous_dividend_yield=0.01,
        eps=1.0,
    )
    first = fundamental_price_signal(asset)
    asset["eps"] = 100.0
    assert fundamental_price_signal(asset) == first
    staged = stage_fundamental_repricing(asset, trading_days=5)
    assert sum(consume_fundamental_repricing(asset) for _ in range(5)) == pytest.approx(staged)
    assert consume_fundamental_repricing(asset) == 0.0


def test_sovereign_cds_price_responds_to_credit_stress() -> None:
    healthy = SimpleNamespace(makro={"A": {"default_probability": 0.01, "debt_to_gdp": 0.6, "fiscal_deficit": 50.0, "bip_abs": 5_000.0}})
    stressed = SimpleNamespace(makro={"A": {"default_probability": 0.40, "debt_to_gdp": 1.8, "fiscal_deficit": 600.0, "bip_abs": 5_000.0}})
    product = {"underlying": "A", "notional": 10_000_000.0}
    assert _cds_price(stressed, dict(product)) > _cds_price(healthy, dict(product))


def test_daily_energy_signal_is_not_duplicated_for_utilities() -> None:
    assert stock_energy_price_signal("Öl und Gas", 0.02) > 0.0
    assert stock_energy_price_signal("Transport und Logistik", 0.02) < 0.0
    assert stock_energy_price_signal("Stromerzeuger", 0.02) == 0.0
    assert stock_energy_price_signal("Öl und Gas", -0.02) < 0.0
    assert sector_energy_factor("Öl und Gas", 1.5, 1.0) > 1.0
    assert sector_energy_factor("Transport und Logistik", 1.5, 1.0) < 1.0
    assert sector_energy_factor("Stromerzeuger", 1.5, 1.0) == 1.0


def test_monthly_energy_shock_is_a_change_not_a_repeated_price_level() -> None:
    data = SimpleNamespace(rohstoffe={"CL": {"kurs": 150.0}, "TTF": {"kurs": 150.0}})
    assert monthly_energy_shock(data) == pytest.approx(1.0)
    assert monthly_energy_shock(data) == pytest.approx(1.0)
    data.rohstoffe["CL"]["kurs"] = 165.0
    data.rohstoffe["TTF"]["kurs"] = 165.0
    assert monthly_energy_shock(data) == pytest.approx(1.1)
