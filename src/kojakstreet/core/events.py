"""Daily event lifecycle for the integrated simulation runtime."""

from __future__ import annotations

import random
from collections.abc import Callable
from types import ModuleType

from kojakstreet.core.shocks import add_shock


NewsCallback = Callable[[str, str], None]


def run_event_phase(daten: ModuleType, add_news: NewsCallback) -> None:
    clear_invalid_gold_dinar_event(daten)
    age_active_event(daten, add_news)
    maybe_start_crisis_event(daten, add_news)


def clear_invalid_gold_dinar_event(daten: ModuleType) -> None:
    if daten.aktives_event and "GD" in daten.aktives_event.get("laender", []):
        daten.aktives_event = None


def age_active_event(daten: ModuleType, add_news: NewsCallback) -> None:
    if not daten.aktives_event:
        return
    if not hasattr(daten, "event_dauer"):
        daten.event_dauer = 0
    daten.event_dauer -= 1
    if daten.event_dauer <= 0:
        add_news(
            f" NEWS: The special event '{daten.aktives_event['name']}' has ended.",
            "ZENTRALBANK",
        )
        daten.aktives_event = None


def maybe_start_crisis_event(daten: ModuleType, add_news: NewsCallback) -> None:
    if daten.aktives_event or random.random() >= 0.008:
        return
    countries = list(daten.LAENDER.keys())
    crises = [
        {
            "name": "GENERAL STRIKE & CIVIL UNREST",
            "typ": "NATIONAL",
            "laender": [random.choice(countries)],
            "dauer": random.randint(30, 90),
            "bip_makel": -0.035,
            "text": "Massive general strikes paralyze infrastructure and factories in {}.",
        },
        {
            "name": "GEOPOLITICAL CONFLICT",
            "typ": "BILATERAL",
            "laender": random.sample(countries, 2),
            "dauer": random.randint(60, 120),
            "bip_makel": -0.025,
            "text": "Severe geopolitical tensions between {} and {}.",
        },
        {
            "name": "SUPPLY SHORTAGE & EMBARGO",
            "typ": "ENERGIE",
            "laender": [random.choice(countries)],
            "dauer": random.randint(45, 90),
            "bip_makel": -0.020,
            "text": "A supply shortage disrupts {}.",
        },
    ]
    event = random.choice(crises)
    daten.event_dauer = event["dauer"]
    if len(event["laender"]) == 1:
        event_text = event["text"].format(event["laender"][0])
    else:
        event_text = event["text"].format(event["laender"][0], event["laender"][1])
    daten.aktives_event = {
        "name": event["name"],
        "laender": event["laender"],
        "bip_makel": event["bip_makel"],
        "typ": event["typ"],
    }
    if event["typ"] == "ENERGIE":
        date_key = getattr(daten, "datum", "world")
        for code in ("CL", "TTF"):
            add_shock(
                daten,
                shock_id=f"energy-embargo:{date_key}:{code}",
                shock_type="supply",
                target=code,
                magnitude=-0.28,
                duration_days=int(event["dauer"]),
                decay="linear",
                source="SUPPLY SHORTAGE & EMBARGO",
            )
    add_news(
        f" ALERT - BREAKING NEWS: {event['name']}!\n\n{event_text}",
        "ROT",
    )
