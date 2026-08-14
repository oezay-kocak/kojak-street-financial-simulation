from __future__ import annotations

from types import SimpleNamespace

from kojakstreet.core.market_data_service import MarketDataService
from kojakstreet.core.trade_preview import build_trade_preview, validate_trade_request


def _state() -> SimpleNamespace:
    return SimpleNamespace(
        aktien={"AAA": {"name": "Alpha", "kurs": 10.0, "aenderung": 1.5, "market_cap": 1000.0, "land": "USA", "branche": "Tech"}},
        rohstoffe={},
        kryptos={},
        fonds={},
        indizes={"IDX": {"name": "Index", "kurs": 100.0, "land": "USA", "market_cap": 5000.0}},
        derivatives={},
        forex_depot={"USA": 90.0, "GD": 0.0},
        depot={"AAA": {"stueck": 3.0, "kaufkurs": 8.0}},
        waehrungen_staerke={"USA": 1.0, "GD": 1.0},
    )


def test_market_data_service_reads_quotes_across_asset_books() -> None:
    service = MarketDataService(_state())

    quote = service.quote("AAA")

    assert quote is not None
    assert quote.asset_type == "Stock"
    assert quote.price == 10.0
    assert quote.region == "USA"
    assert service.history("AAA") == []


def test_trade_validation_rejects_unfunded_buy_without_fees_or_slippage() -> None:
    state = _state()

    valid = validate_trade_request(state, "AAA", "SPOT", "BUY", 9.0, 1)
    invalid = validate_trade_request(state, "AAA", "SPOT", "BUY", 9.1, 1)

    assert valid.is_valid is True
    assert valid.required_amount == 90.0
    assert invalid.is_valid is False
    assert invalid.max_quantity == 9.0


def test_trade_validation_rejects_oversized_sell_and_preview_exposes_state() -> None:
    state = _state()

    invalid = validate_trade_request(state, "AAA", "SPOT", "SELL", 4.0, 1)
    preview = build_trade_preview(state, "AAA", "BUY", 2.0)

    assert invalid.is_valid is False
    assert invalid.available_amount == 3.0
    assert preview.is_valid is True
    assert preview.notional == 20.0
