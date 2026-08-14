from __future__ import annotations

from pathlib import Path

import daten
import speicher
from kojakstreet.core.countries import COUNTRIES
from kojakstreet.core.production_chains import ensure_country_economies


def test_save_load_preserves_country_economy_fields(tmp_path: Path, monkeypatch) -> None:
    save_file = tmp_path / "spielstand.dat"
    monkeypatch.setattr(speicher, "SPEICHER_DATEI", str(save_file))
    ensure_country_economies(daten)
    country = COUNTRIES[0].name
    partner_a = COUNTRIES[1].name
    partner_b = COUNTRIES[2].name
    daten.makro[country]["regional_supply"] = {"ELC": 123.0}
    daten.makro[country]["trade_partner_details"] = {"ELC": {partner_a: 50.0, partner_b: 25.0}}
    daten.makro[country]["regional_history"] = {"ELC": {"produced": [(123.0, "01.01.1990", "")]}}

    speicher.spiel_speichern()
    daten.makro[country].pop("regional_supply", None)
    daten.makro[country].pop("trade_partner_details", None)
    daten.makro[country].pop("regional_history", None)

    speicher.spiel_laden()

    assert daten.makro[country]["regional_supply"]["ELC"] == 123.0
    assert len(daten.makro[country]["trade_partner_details"]["ELC"]) == 2
    assert daten.makro[country]["regional_history"]["ELC"]["produced"]


def test_save_payload_strips_runtime_cache_keys() -> None:
    payload = {
        "AAA": {
            "kurs": 12.0,
            "_ema_cache": {"20": 11.5},
            "history": [(1.0, "01.01.1990", {"_private": True, "public": True})],
        },
        "_asset_row_source_cache": {"heavy": True},
    }

    cleaned = speicher._without_runtime_cache(payload)

    assert "_asset_row_source_cache" not in cleaned
    assert "_ema_cache" not in cleaned["AAA"]
    assert cleaned["AAA"]["history"][0][2] == {"public": True}
