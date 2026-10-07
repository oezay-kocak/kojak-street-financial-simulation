"""Batch lookup preserves duplicate symbols, currency and live-book identity."""
from types import SimpleNamespace

from kojakstreet.core.market_data_service import MarketDataService


def test_batch_preserves_precedence_duplicates_and_string_keys():
    stock = {"kurs": 3.0, "land": "Ameron", "branche": "Energy"}
    commodity = {"price": 4.0, "land": "ignored", "kategorie": "Metal"}
    crypto = {"kurs": 5.0, "typ": "Chain"}
    fund = {"kurs": 6.0, "ziel": "Novara", "aum": 7.0}
    derivative = {"kurs": 8.0, "land": ""}
    state = SimpleNamespace(
        stocks={"DUP": stock, 1: {"kurs": 999.0}},
        commodities={"DUP": commodity, "METAL": commodity},
        cryptos={"CHAIN": crypto}, funds={"FUND": fund},
        indices={"DUP": {"kurs": 999.0}}, derivatives={"1": derivative},
    )
    service = MarketDataService(state)
    rows = service.quotes()
    assert [(r.ticker, r.asset_type, r.price, r.region) for r in rows] == [
        ("DUP", "Stock", 3.0, "Ameron"), ("1", "Derivative", 8.0, "GD"),
        ("DUP", "Stock", 3.0, "Ameron"), ("METAL", "Commodity", 4.0, "GD"),
        ("CHAIN", "Crypto", 5.0, "GD"), ("FUND", "Fund", 6.0, "Novara"),
        ("DUP", "Index", 999.0, "GD"), ("1", "Derivative", 8.0, "GD"),
    ]
    assert rows[0].data is rows[2].data is stock
    assert rows[5].market_cap == 7.0
    assert rows == [service.quote(str(t), asset_type="Index" if kind == "Index" else None)
                    for kind, book in service.asset_books() for t in book]
    assert service.quote("DUP").data is stock
    assert service.quote("DUP", asset_type="Index").price == 999.0
    # Replacing a world book must not retain a snapshot from the previous read.
    state.stocks = {"NEW": {"kurs": 10.0}}
    assert service.quotes()[0].ticker == "NEW"
    assert service.quote("DUP").asset_type == "Commodity"
