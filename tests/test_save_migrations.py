from __future__ import annotations

from kojakstreet.core.financial_products import CDS_CONTRACT_SCALE
from kojakstreet.core.save_migrations import CURRENT_SAVE_VERSION, migrate_save_payload


def test_save_migration_adds_missing_books_and_cds_contract_metadata() -> None:
    payload = {
        "save_version": 1,
        "bargeld": 100.0,
        "aktien": {"AAA": {"kurs": 10.0}},
        "rohstoffe": {},
        "kryptos": {},
        "makro": {},
        "derivatives": {
            "CDS1": {
                "kurs": 2.0,
                "instrument_type": "Credit Default Swap",
                "notional": 10_000_000.0,
            }
        },
    }

    migrated = migrate_save_payload(payload)

    assert migrated["save_version"] == CURRENT_SAVE_VERSION
    assert migrated["perpetuals"] == {}
    assert migrated["realisierte_guv_historie"] == []
    assert migrated["aktien"]["AAA"]["ticker"] == "AAA"
    assert migrated["derivatives"]["CDS1"]["contract_scale"] == CDS_CONTRACT_SCALE
    assert migrated["derivatives"]["CDS1"]["contract_size"] == 1_000.0
