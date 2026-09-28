from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

from kojakstreet.core.bonds import (
    BASE_CORPORATE_TERMS,
    BASE_GOVERNMENT_TERMS,
    MAX_ACTIVE_BOND_MARKET_SIZE,
    _smooth_secondary_market_price,
    ensure_dynamic_bond_market,
    update_dynamic_bond_market,
)
from kojakstreet.core.funds import _fund_daily_return


def test_bond_secondary_market_price_moves_toward_fair_value_gradually() -> None:
    price = _smooth_secondary_market_price(
        previous_price=100.0,
        fair_price=120.0,
        previous_yield=0.05,
        market_yield=0.05,
        years=30.0,
        liquidity=1.0,
        issuer_type="Government",
    )

    assert 100.0 < price < 120.0
    assert price < 104.0


def test_initial_market_issues_small_base_curve_and_corporate_benchmark() -> None:
    data = _bond_test_data(datetime(1990, 1, 1, tzinfo=timezone.utc))

    ensure_dynamic_bond_market(data)

    government = [bond for bond in data.bond_market if bond["issuer_type"] == "Government"]
    corporate = [bond for bond in data.bond_market if bond["issuer_type"] == "Corporate"]
    issued = {(bond["ticker"], bond["term_years"]) for bond in corporate}
    gov_issued = {(bond["region"], bond["term_years"]) for bond in government}

    assert issued == {
        ("AAA", term) for term in BASE_CORPORATE_TERMS
    } | {
        ("BBB", term) for term in BASE_CORPORATE_TERMS
    }
    assert gov_issued == {
        ("USA", term) for term in BASE_GOVERNMENT_TERMS
    } | {
        ("EU", term) for term in BASE_GOVERNMENT_TERMS
    }


def test_corporate_bond_issues_new_same_term_at_half_maturity() -> None:
    data = _bond_test_data(datetime(1990, 1, 1, tzinfo=timezone.utc))
    ensure_dynamic_bond_market(data)
    data.datum = datetime(1992, 7, 4, tzinfo=timezone.utc)

    update_dynamic_bond_market(data)

    five_year_bonds = [
        bond
        for bond in data.bond_market
        if bond.get("issuer_type") == "Corporate"
        and bond.get("ticker") == "AAA"
        and bond.get("term_years") == 5
    ]

    assert len(five_year_bonds) == 2
    assert any(bond["issue_date"] == data.datum and bond["issue_reason"] == "refinancing" for bond in five_year_bonds)


def test_need_based_corporate_issuance_adds_cash_and_debt() -> None:
    data = _bond_test_data(datetime(1990, 1, 1, tzinfo=timezone.utc))
    data.aktien["AAA"].update(
        {
            "market_cap": 1_000_000_000.0,
            "revenue": 800_000_000.0,
            "cash_reserves": 5_000_000.0,
            "debt": 650_000_000.0,
            "debt_to_market_cap": 0.65,
            "fcf_margin": -0.02,
        }
    )
    ensure_dynamic_bond_market(data)
    before_cash = data.aktien["AAA"]["cash_reserves"]
    before_debt = data.aktien["AAA"]["debt"]
    data.datum = datetime(1990, 2, 1, tzinfo=timezone.utc)

    update_dynamic_bond_market(data)

    funding_bonds = [
        bond
        for bond in data.bond_market
        if bond.get("ticker") == "AAA" and bond.get("issue_reason") == "funding"
    ]
    assert funding_bonds
    assert data.aktien["AAA"]["cash_reserves"] > before_cash
    assert data.aktien["AAA"]["debt"] > before_debt


def test_need_based_government_issuance_does_not_double_count_fiscal_debt() -> None:
    data = _bond_test_data(datetime(1990, 1, 1, tzinfo=timezone.utc))
    data.makro["USA"].update(
        {
            "bip_abs": 5_000.0,
            "fiscal_deficit": 350.0,
            "government_debt": 5_000.0,
            "debt_to_gdp": 1.0,
            "interest_burden": 0.06,
        }
    )
    ensure_dynamic_bond_market(data)
    before_cash = float(data.makro["USA"].get("sovereign_cash_buffer", 0.0))
    before_debt = data.makro["USA"]["government_debt"]
    data.datum = datetime(1990, 2, 1, tzinfo=timezone.utc)

    update_dynamic_bond_market(data)

    funding_bonds = [
        bond
        for bond in data.bond_market
        if bond.get("region") == "USA" and bond.get("issue_reason") == "funding"
    ]
    assert funding_bonds
    assert data.makro["USA"]["sovereign_cash_buffer"] >= before_cash
    assert data.makro["USA"]["government_debt"] == before_debt


def test_partial_bond_refresh_clears_stale_daily_change() -> None:
    data = _bond_test_data(datetime(1990, 1, 1, tzinfo=timezone.utc))
    ensure_dynamic_bond_market(data)
    first_bond = data.bond_market[0]
    refreshed_bond = data.bond_market[1]
    first_bond["aenderung"] = 12.5
    refreshed_bond["aenderung"] = -3.0
    data.bond_market_refresh_cursor = 1
    data.datum = datetime(1990, 1, 2, tzinfo=timezone.utc)

    update_dynamic_bond_market(data, max_refresh=1)

    assert first_bond["aenderung"] == 0.0
    assert refreshed_bond["last_price_update_ordinal"] == data.datum.toordinal()


def test_bond_market_archives_excess_off_the_run_issues() -> None:
    data = _bond_test_data(datetime(1990, 1, 1, tzinfo=timezone.utc))
    ensure_dynamic_bond_market(data)
    base_symbols = {
        str(bond["symbol"])
        for bond in data.bond_market
        if bond.get("issue_reason") == "base"
    }
    template = dict(data.bond_market[0])
    data.bond_market.extend(
        {
            **template,
            "symbol": f"OLD-{index}",
            "issuer_type": "Corporate",
            "issue_reason": "funding",
            "issue_date": datetime(1989, 1, 1, tzinfo=timezone.utc),
            "maturity_date": datetime(2020, 1, 1, tzinfo=timezone.utc),
            "liquidity": 0.1,
        }
        for index in range(MAX_ACTIVE_BOND_MARKET_SIZE + 25)
    )

    update_dynamic_bond_market(data)

    assert len(data.bond_market) == MAX_ACTIVE_BOND_MARKET_SIZE
    assert len(data.bond_market_archive) > 0
    assert base_symbols <= {str(bond["symbol"]) for bond in data.bond_market}
    assert data.bond_market_archive_count == len(data.bond_market_archive)


def test_bond_fund_ignores_stale_price_change_but_keeps_carry() -> None:
    fund = {
        "underlyings": [{"asset_type": "Bond", "ticker": "BOND", "weight": 1.0}],
        "cash_allocation": 0.0,
        "expense_ratio": 0.0,
    }
    asset_cache = {
        ("Bond", "BOND"): {
            "aenderung": 20.0,
            "yield_to_maturity": 0.066,
            "last_price_update_ordinal": datetime(1990, 1, 1, tzinfo=timezone.utc).toordinal(),
        }
    }
    current_ordinal = datetime(1990, 1, 2, tzinfo=timezone.utc).toordinal()

    daily_return = _fund_daily_return(fund, asset_cache, current_ordinal=current_ordinal)

    assert daily_return == 0.066 / 264.0


def _bond_test_data(date: datetime) -> SimpleNamespace:
    return SimpleNamespace(
        datum=date,
        bond_market=[],
        makro={
            "USA": {"zins": 0.035, "rating": "BBB"},
            "EU": {"zins": 0.035, "rating": "BBB"},
        },
        aktien={
            "AAA": {"name": "Alpha Corp", "land": "USA", "branche": "Tech", "rating": "BBB", "market_cap": 1_000_000_000.0, "revenue": 500_000_000.0, "cash_reserves": 150_000_000.0, "debt": 200_000_000.0, "debt_to_market_cap": 0.20, "fcf_margin": 0.08},
            "BBB": {"name": "Beta Corp", "land": "EU", "branche": "Industry", "rating": "BBB", "market_cap": 800_000_000.0, "revenue": 400_000_000.0, "cash_reserves": 120_000_000.0, "debt": 160_000_000.0, "debt_to_market_cap": 0.20, "fcf_margin": 0.08},
        },
    )
