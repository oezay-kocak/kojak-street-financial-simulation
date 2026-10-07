"""A pricing batch must retain tie order and rebuild after bond-book changes."""
from copy import deepcopy
from types import SimpleNamespace

from kojakstreet.core.financial_products import _yield_future_price, update_financial_products


def test_yield_batch_matches_full_scan_with_ties_and_replaced_bonds():
    bonds = [
        {"issuer_type": issuer, "region": region, "maturity_years": tenor, "yield_to_maturity": rate}
        for issuer, region, tenor, rate in (
            ("Government", "A", 5, 0.01),
            ("Corporate", "A", 5, 0.99),
            ("Government", "B", 5, 0.08),
            ("Government", "A", 5, 0.02),
            ("Government", "A", 5, 0.03),
            ("Government", "A", 5, 0.04),
            ("Government", "A", 10, 0.00),
        )
    ]
    world = SimpleNamespace(
        derivative_universe_complete=True, bond_market=bonds, makro={},
        derivatives={
            f"{country}{tenor}": {
                "instrument_type": "Yield Future", "underlying": country,
                "tenor_years": tenor, "kurs": 100.0, "historie": [],
            }
            for country in ("A", "B", "missing") for tenor in (2, 5, 10, 30)
        },
    )
    for day in ("01.01.1990", "02.01.1990"):
        expected = {}
        for ticker, product in world.derivatives.items():
            reference = deepcopy(product)
            price = _yield_future_price(world, reference)
            expected[ticker] = (price, reference)
        update_financial_products(world, day)
        for ticker, product in world.derivatives.items():
            price, reference = expected[ticker]
            assert product["kurs"] == price
            for field in ("yield_rate", "bond_market_yield", "yield_curve_component"):
                assert product[field] == reference[field]
        world.bond_market = deepcopy(list(reversed(world.bond_market)))
        world.bond_market[0]["yield_to_maturity"] = 0.13
        world.bond_market[1]["region"] = "B"
