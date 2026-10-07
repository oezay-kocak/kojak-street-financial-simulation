import daten
from kojakstreet.core.accounting import convert_amount
from kojakstreet.core.countries import RESERVE_CURRENCY
from kojakstreet.core.history import HOT_REALIZED_EVENTS, trim_history
from kojakstreet.core.ratings import DEFAULT_RATING, RECOVERY_RATE, default_probability
from kojakstreet.core.player_accounting import bond_credit_uniform


def update_laufende_anleihen(add_news_callback, daten_module=None):
    """Calculate coupon payments in each bond's local currency."""
    daten_module = daten if daten_module is None else daten_module
    for anl in daten_module.anleihen[:]:
        if anl.get("typ") != "STAAT" and (
            anl.get("defaulted")
            or str(anl.get("ticker", "")) in getattr(daten_module, "retired_company_tickers", set())
        ):
            land = anl.get("land", RESERVE_CURRENCY)
            recovery = float(anl.get("nominal", 0.0)) * RECOVERY_RATE
            daten_module.forex_depot[land] = daten_module.forex_depot.get(land, 0.0) + recovery
            add_news_callback(
                f" CORPORATE BOND DEFAULT: {anl.get('ticker', '')} paid recovery of {recovery:.2f} {daten_module.LAENDER.get(land, land)}.",
                "ROT",
            )
            daten_module.anleihen.remove(anl)
            continue
        anl["resttage"] -= 1

        if "zinstage_zaehler" not in anl:
            anl["zinstage_zaehler"] = 0
        anl["zinstage_zaehler"] += 1

        land = anl.get("land", RESERVE_CURRENCY)
        sym = daten_module.LAENDER.get(land, land)

        if anl["zinstage_zaehler"] >= 180 and anl["resttage"] > 0:
            anl["zinstage_zaehler"] = 0
            halbjahres_kupon = anl["nominal"] * (anl["zins"] / 2)

            daten_module.forex_depot[land] = daten_module.forex_depot.get(land, 0.0) + halbjahres_kupon

            daten_module.realisierte_guv_historie.append((daten_module.datum, convert_amount(daten_module, halbjahres_kupon, land, RESERVE_CURRENCY)))
            trim_history(daten_module.realisierte_guv_historie, HOT_REALIZED_EVENTS)
            label = (
                f"government bond ({land})"
                if anl["typ"] == "STAAT"
                else f"corporate bond [{anl['ticker']}]"
            )
            add_news_callback(
                f" COUPON PAYMENT: Semiannual interest of {halbjahres_kupon:.2f} {sym} "
                f"received for {label}.",
                "GRUEN",
            )

        if anl["resttage"] <= 0:
            rest_kupon = anl["nominal"] * (anl["zins"] * (anl["zinstage_zaehler"] / 365))

            daten_module.forex_depot[land] = daten_module.forex_depot.get(land, 0.0) + rest_kupon
            daten_module.realisierte_guv_historie.append((daten_module.datum, convert_amount(daten_module, rest_kupon, land, RESERVE_CURRENCY)))
            trim_history(daten_module.realisierte_guv_historie, HOT_REALIZED_EVENTS)

            if anl["typ"] == "STAAT":
                daten_module.forex_depot[land] = daten_module.forex_depot.get(land, 0.0) + anl["nominal"]
                add_news_callback(
                    f" GOVERNMENT BOND: ({land}) with {anl['nominal']:.2f} {sym} principal "
                    "matured and was repaid at 100%.",
                    "ZENTRALBANK",
                )
            else:
                akt_rating = daten_module.aktien.get(anl["ticker"], {}).get("rating", "D")
                ausfall_risiko = _remaining_term_default_probability(akt_rating, anl)

                if bond_credit_uniform(daten_module, anl) < ausfall_risiko:
                    add_news_callback(
                        f" RATING DEFAULT: Corporate bond {anl['ticker']} "
                        f"(Rating: {akt_rating}) has defaulted!\n"
                        f"The principal amount of {anl['nominal']:.2f} {sym} was lost completely.",
                        "ROT",
                    )
                else:
                    daten_module.forex_depot[land] = daten_module.forex_depot.get(land, 0.0) + anl["nominal"]
                    add_news_callback(
                        f" CORPORATE BOND: {anl['ticker']} matured successfully "
                        f"(Rating: {akt_rating}).\n"
                        f"The principal amount of {anl['nominal']:.2f} {sym} was repaid at 100%.",
                        "GRUEN",
                    )

            daten_module.anleihen.remove(anl)


def _remaining_term_default_probability(rating: str, bond: dict) -> float:
    original_days = max(1.0, float(bond.get("laufzeit_tage", bond.get("initial_resttage", bond.get("resttage", 365.0)))))
    elapsed_days = max(1.0, original_days - max(0.0, float(bond.get("resttage", 0.0))))
    annualized_horizon = max(1.0 / 12.0, elapsed_days / 365.0)
    return min(0.95, default_probability(rating) * annualized_horizon)
