from __future__ import annotations

import daten
from kojakstreet.adapters.legacy_state import snapshot_from_legacy
from kojakstreet.core.news import build_news_items


def test_news_items_classify_priority_category_and_impact() -> None:
    state = snapshot_from_legacy(daten)
    state.news = [
        (
            "01.02.1990",
            " ALERT - BREAKING NEWS: GENERAL STRIKE\nAffected regions suffer.",
            "ROT",
        ),
        (
            "01.03.1990",
            " CENTRAL BANK DECISION: Policy rate CUT to 1.00%",
            "ZENTRALBANK",
        ),
    ]

    items = build_news_items(state)

    assert items[0].priority == "High"
    assert items[0].topic == "Country"
    assert items[0].category == "Negative"
    assert items[0].impact == "Bearish"
    assert items[1].topic == "Policy"
    assert items[1].category == "Central Bank"
    assert items[1].impact == "Easing"


def test_news_items_mark_solvency_events_as_critical() -> None:
    state = snapshot_from_legacy(daten)
    state.news = [
        (
            "01.04.1990",
            "MARGIN CALL: Your net worth is depleted.",
            "ROT",
        ),
    ]

    items = build_news_items(state)

    assert items[0].priority == "Critical"
    assert items[0].topic == "Solvency"


def test_news_items_translate_legacy_german_news_to_english() -> None:
    state = snapshot_from_legacy(daten)
    state.news = [
        (
            "01.02.1990",
            " ACHTUNG - EILMELDUNG: GENERALSTREIK\nBetroffene Regionen leiden.",
            "ROT",
        ),
        (
            "01.03.1990",
            " ZENTRALBANK-ENTSCHEID: Leitzins GESENKT auf 1.00%",
            "ZENTRALBANK",
        ),
    ]

    items = build_news_items(state)

    assert items[0].headline.startswith("ALERT - BREAKING NEWS")
    assert "GENERAL STRIKE" in items[0].body
    assert items[1].headline == "CENTRAL BANK DECISION: Policy rate CUT to 1.00%"
    assert items[1].impact == "Easing"
