"""Assemble a source-grounded Genesis inventory and the index audit report."""
from __future__ import annotations

import ast
import hashlib
import json
import statistics
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / ".cache/genesis-audit"
DOCS = ROOT / "docs"
HEADER = ["Category", "Entity", "Field", "Classification", "Current Genesis value/formula",
          "Range/distribution", "Scope", "Global budget?", "Dependencies", "Downstream consumers",
          "RNG source", "Code location", "Heterogeneous candidate?", "Notes/invariants"]
MODULES = {
    "makro": ["daten.py", "fiscal.py", "expectations.py", "production_chains.py"],
    "aktien": ["companies.py", "fundamentals.py", "production_chains.py", "psychology.py", "company_lifecycle.py", "bonds.py"],
    "rohstoffe": ["daten.py", "production_chains.py", "commodities.py", "psychology.py"],
    "processed_products": ["production_chains.py"], "kryptos": ["cryptos.py", "production_chains.py", "psychology.py"],
    "fonds": ["funds.py"], "indizes": ["indices.py", "companies.py"],
    "derivatives": ["financial_products.py"], "bond_market": ["bonds.py"],
    "global_macro": ["daten.py", "global_macro.py", "market_regime.py"], "market_psychology": ["psychology.py"],
    "world": ["daten.py", "legacy_runtime.py", "bonds.py", "shocks.py"],
}
UNITS = {
    "bip_abs": "model GDP units", "balance_sheet": "model balance-sheet units",
    "government_debt": "model GDP units", "fiscal_deficit": "annual model GDP units",
    "private_credit": "model GDP units", "bevoelkerung": "persons",
    "zins": "annual fraction", "inflation": "annual fraction", "bip_prozent": "annual fraction",
    "arbeitslosigkeit": "fraction", "population_growth": "monthly fraction",
    "kurs": "local-currency quote / index points", "market_cap": "local-currency value / synthetic proxy",
    "aktien_anzahl": "shares", "aum": "fund-currency value", "debt": "local currency",
    "cash_reserves": "local currency", "revenue": "annual local currency", "free_cash_flow": "annual local currency",
    "eps": "local currency/share", "coupon": "annual fraction", "yield_to_maturity": "annual fraction",
    "price": "per 100 nominal", "nominal": "nominal currency units", "duration": "years",
    "maturity_years": "years", "term_years": "years", "tenor_years": "years", "tenor_months": "months",
    "production_capacity": "model output units", "supply": "model quantity", "production": "model quantity",
    "demand": "model quantity", "inventories": "model quantity", "price_index": "index points",
    "aenderung": "percent", "expense_ratio": "annual fraction",
}
RANDOM_RANGES = {
    ("aktien", "kurs"): "round(U[18,145],2)",
    ("aktien", "eps"): "max(0.1, price/U[14,28]); independent seeded P/E, not FCF/shares",
    ("aktien", "cash_reserves"): "1e9*U[0.04,0.22], then funding issue may add 0.92*issue_size",
    ("aktien", "debt"): "1e9*U[0.05,0.45], then funding issue may add issue_size",
    ("aktien", "rating"): "uniform choice {A-,BBB+,BBB,BBB-,BB+}",
    ("kryptos", "kurs"): "round(U[12,180],2)",
    ("kryptos", "circulating_supply"): "STORE U[5e6,50e6]; others U[18e6,220e6]",
    ("kryptos", "network_capacity"): "U[360,920]",
    ("kryptos", "transactions"): "U[35000,260000]",
    ("kryptos", "chain_fees"): "U[8000,95000]",
    ("kryptos", "active_wallets"): "U[18000,160000]",
    ("bond_market", "liquidity"): "Government U[0.75,1]; Corporate U[0.35,0.85]",
    ("fonds", "aum"): "max(27e6, target_aum*U[0.35,0.95])",
    ("fonds", "market_cap"): "same start_aum as AUM; no additional draw",
}
ROOT_CANDIDATES = {("makro", k) for k in ("bevoelkerung", "bip_abs", "bip_prozent", "zins", "inflation", "arbeitslosigkeit", "balance_sheet")}
ROOT_CANDIDATES |= {("aktien", "market_cap")}


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def cell(value):
    return str(value).replace("|", "&#124;").replace("\n", " ")


def table(headers, rows):
    return "\n".join(["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |",
                      *["| " + " | ".join(cell(c) for c in row) + " |" for row in rows]])


def observed(values):
    items = [v for _, v in values]
    if items and all(isinstance(v, (float, int)) and not isinstance(v, bool) for v in items):
        return f"observed min={min(items)!r}; median={statistics.median(items)!r}; max={max(items)!r}"
    if items and all(not isinstance(v, (dict, list)) for v in items):
        unique = sorted({str(v) for v in items})
        return "exact set: " + ", ".join(unique) if len(unique) <= 12 else f"{len(unique)} distinct identifiers; full values in JSON"
    lengths = [len(v) for v in items if isinstance(v, (dict, list))]
    return f"nested mapping/series; observed sizes {min(lengths)}..{max(lengths)}; all values in JSON" if lengths else "see exact JSON"


def classify(book, field, values):
    if book == "world":
        if field == "simulation_seed":
            return "ROOT"
        if "HISTORIE" in field or field == "realisierte_guv_historie":
            return "BOOTSTRAP_RESULT"
        return "FIXED"
    if book == "makro" and field in {"rating", "credit_growth"}:
        return "FIXED"
    if book in {"aktien", "kryptos"} and field == "name":
        return "EXISTING_RANDOMIZED"
    if book == "fonds" and field == "issuer":
        return "EXISTING_RANDOMIZED"
    if (book, field) in RANDOM_RANGES:
        return "EXISTING_RANDOMIZED"
    if (book, field) in ROOT_CANDIDATES:
        return "ROOT"
    if field.startswith("_"):
        return "DERIVED"
    if field in {"historie", "economic_profile", "regional_history", "company_output_history", "company_input_history"} or field.endswith("_history"):
        return "BOOTSTRAP_RESULT"
    if field in {"name", "land", "branche", "kategorie", "typ", "symbol", "issuer", "issuer_type", "category", "region", "status", "founded", "fund_type", "strategy", "mandate_key", "issuer_bank", "ziel", "tracked_index", "inception_date", "instrument_type", "underlying", "underlying_type", "option_type", "inputs", "users", "sector", "index_type", "methodology", "base_level", "production_role", "specialization_name", "sector_code", "group_code", "task_type", "service_code", "code", "pricing_note", "ticker", "issue_reason", "issue_date", "maturity_date", "expires_at", "base_currency", "quote_currency", "long_leg", "short_leg", "output_code"}:
        return "FIXED" if field not in {"name", "issuer", "issuer_bank", "specialization_name", "production_role"} else "DERIVED"
    if book in {"rohstoffe", "processed_products"} and field not in {"kurs", "market_cap", "long_interest", "short_interest", "open_interest", "prognose_target", "extraction_cost", "previous_extraction_cost"}:
        return "BOOTSTRAP_RESULT"
    if book == "aktien" and field in {"output_mix", "specialization"}:
        return "EXISTING_RANDOMIZED"
    if book == "aktien" and field in {"production_capacity", "capacity_utilization", "capacity_growth", "production_score", "input_availability", "supply_chain_shortage", "refinancing_momentum", "hedge_profile", "hedge_summary"}:
        return "BOOTSTRAP_RESULT"
    if book == "makro" and field in {"regional_supply", "regional_demand", "regional_shortage", "regional_pressure", "exports", "imports", "trade_partners", "trade_partner_details", "trade_balance", "import_dependency", "export_strength", "main_sector", "main_bottleneck"}:
        return "BOOTSTRAP_RESULT"
    if book == "bond_market" and field in {"price", "fair_price", "yield_to_maturity", "duration", "default_risk", "maturity_years"}:
        return "BOOTSTRAP_RESULT"
    if book == "global_macro" and not field.startswith("regime_"):
        return "FIXED"
    if field == "previous_eps":
        return "DERIVED"
    items = [v for _, v in values]
    if items and all(v == items[0] for v in items) and items[0] in (0., 0, False, True, None, 100., 1000., 1., 0.7, 1e9, 1e8):
        return "FIXED"
    return "DERIVED"


def generated_provenance(book, field):
    if field.endswith("_history") and book in {"makro", "rohstoffe", "processed_products"}:
        return [{"location": "src/kojakstreet/core/production_chains.py:1242 / :957 / :1629",
                 "formula": "append (value,date,'') to dynamic history key; two initialization passes at 01.01.1990"}]
    if book == "kryptos" and (field.startswith("previous_") or field.endswith("_change")):
        return [{"location": "src/kojakstreet/core/cryptos.py:415 (_ensure_task_metrics)",
                 "formula": "for key in TASK_METRIC_KEYS[task]: previous_key=current[key]; key_change=0"}]
    if book == "world":
        return [{"location": "daten.py:36 / legacy_runtime.py:52 / bonds.py:41", "formula": "top-level initializer / runtime bootstrap; actual value below"}]
    return []


def inventory():
    values = read(OUT / "before-2307/inventory-values.json")
    world = read(OUT / "before-2307/checkpoint.json")["checkpoint"]
    values["world"] = {k: [("world", v)] for k, v in world.items() if k not in values}
    source = read(OUT / "source-fields.json")
    records = []
    for book, fields in values.items():
        for field, vals in fields.items():
            writes = [w for w in source["writes"].get(field, [])
                      if any(m in w["location"] for m in [*MODULES[book], "label_codes.py"])]
            if book != "world":
                writes = [w for w in writes if "kwargs" not in w["formula"]]
            if not writes:
                writes = generated_provenance(book, field)
            assert writes, (book, field)
            consumers = source["consumers"].get(field, [])
            classification = classify(book, field, vals)
            note = f"Unit: {UNITS.get(field, 'model scalar/identifier; dimensional meaning follows source')}"
            if field.startswith("_"):
                note += "; computational/reference cache, reconstructible; not a new economic root"
            if field == "eps" and book == "aktien":
                note += "; directly randomized today; first monthly report derives FCF/shares"
            if book == "global_macro" and field not in {"global_m2", "rrp", "tga", "vix"}:
                note += "; direct seed is semantically derived; rates/liquidity may disagree with ready aggregates; see report section 11"
            formulas = list(dict.fromkeys(w["formula"] for w in writes))
            locations = list(dict.fromkeys(w["location"] for w in writes))
            rng = "Python random, seeded by IntegratedRuntime" if (book, field) in RANDOM_RANGES else "none / upstream seeded values"
            if (book in {"aktien", "kryptos"} and field == "name") or (book == "fonds" and field == "issuer"):
                rng = "Python random.choice; current template/pool, no independent amount budget"
            if book == "aktien" and field in {"output_mix", "specialization"}:
                rng = "stable text hash (base 131 mod 10000), seeded company name upstream; bootstrap rebalance"
            if book == "bond_market" and field == "price":
                rng = "Python U[-0.018,0.018] liquidity noise after fair-value calculation"
            budget = "see budget matrix; derived amounts are not independent pools"
            if field in {"bevoelkerung", "bip_abs", "market_cap", "production_capacity", "aum", "government_debt", "private_credit", "debt", "cash_reserves", "inventories", "supply", "demand"}:
                budget = "explicitly audited in budget matrix; no generic runtime conservation"
            deps = sorted({n.id for formula in formulas for n in ast.walk(ast.parse(formula, mode="eval")) if isinstance(n, ast.Name)}) if all(";" not in f and not f.startswith(("append ", "for ", "top-level")) and " / " not in f for f in formulas) else ["see bootstrap dependency graph"]
            record = dict(zip(HEADER, [book, f"all {book} entities having this field", field, classification,
                "; ".join(formulas) + "; " + observed(vals),
                RANDOM_RANGES.get((book, field), "No independent draw; formula/default above; " + observed(vals)),
                "per country" if book == "makro" else "global" if book in {"world", "global_macro", "market_psychology"} else "per entity",
                budget, ", ".join(deps), "; ".join(consumers) or "whole-book snapshot/checkpoint/store consumers",
                rng, "; ".join(locations), "candidate, requires controlled budgets" if (book, field) in ROOT_CANDIDATES else "preserve/derive; not independent", note]))
            record["all_observed_values"] = vals
            records.append(record)
    # Nested state carries meaningful economics even though it is stored in a parent mapping.
    nested = [
        ("economic_profile.sector_focus", "FIXED", "4 preferred sectors/country; 1.18 + uniqueness(0 or .08) + (position%3)*.04", "production_chains.py:1430", "regional output bonus; fixed country templates, not seeded random geology"),
        ("economic_profile.product_focus", "DERIVED", "first 3 outputs/selected sector, each 1.10", "production_chains.py:1465", "country demand weights; overlaps collapsed by dictionary"),
        ("economic_profile.last_rebalanced_year", "FIXED", "1990", "production_chains.py:493", "five-year gate"),
        ("regional_history.*.produced/demanded/gap/shortage/pressure/exports/imports/net", "BOOTSTRAP_RESULT", "two same-date entries; physical flow values and percentages as in :1049", "production_chains.py:1035", "not prehistory"),
        ("trade_partner_details.*.*.exports/imports", "BOOTSTRAP_RESULT", "bilateral matched quantities", "production_chains.py:928", "per commodity/product and partner, export/import matching"),
        ("underlyings[].ticker/asset_type/weight", "DERIVED", "ETF index weight 1; equity up to35; bonds up to80; value-weighted normalized holdings", "funds.py:385", "fund return and exposures; cash overlays separate"),
        ("output_mix.*", "EXISTING_RANDOMIZED", "normalize primary .58+.24h, secondary .12+.15h, tertiary .05+.08h; optional fourth .03+.06h if h>.36", "production_chains.py:573", "all shares normalize to1; names/countries deterministically hash"),
        ("company_output_history.* / company_input_history.*", "BOOTSTRAP_RESULT", "capacity*output share*utilization; recipe-weighted input quantities", "production_chains.py:1352", "two bootstrap points at Day1"),
        ("constituents.*", "DERIVED", "member market_cap / country-or-sector total", "indices.py:189", "all eligible same-country stocks; no minimum"),
        ("hedge_profile.*", "DERIVED", "input recipe exposure by energy/metals/agriculture/FX/rates/credit", "company_lifecycle.py:101", "report/warm cache; no separate economic generator"),
    ]
    for field, cls, formula, loc, note in nested:
        records.append(dict(zip(HEADER, ["nested", "owning entities", field, cls, formula, "formula above", "per parent", "inherits parent budgets", "parent/root and recipe state", "production/funds/UI/persistence", "stable hash if stated; otherwise upstream", loc, "preserve/derive", note])))
    # Include all literal model-definition parameters (recipes, baskets, sector financial profiles,
    # universe limits, temporal controls, ratings). No execution of module initializers is needed.
    wanted = {"production_chains.py": {"PROCESSED_PRODUCTS", "INPUT_RECIPES", "SECTOR_INPUT_WEIGHTS", "CONSUMER_BASKET", "BALANCE_PROFILES", "SECTOR_OUTPUTS", "COUNTRY_PROFILE_REBALANCE_DAYS", "OUTPUT_MIX_VERSION", "TRADE_PARTNER_WEIGHTS"},
              "fundamentals.py": {"SECTOR_PROFILES", "DEFAULT_PROFILE"},
              "ratings.py": {"DEFAULT_PROBABILITIES", "RECOVERY_RATE"},
              "companies.py": {"START_COMPANIES_PER_COUNTRY_SECTOR", "INITIAL_MARKET_CAP", "STYLE_NAME_PARTS", "SECTOR_TERMS"},
              "cryptos.py": {"TARGET_CRYPTO_COUNT", "START_CHAINS_PER_TASK", "MIN_CHAINS_PER_TASK", "SHUTDOWN_PRICE", "SHUTDOWN_SHARE", "NAME_PARTS", "TASK_METRIC_KEYS", "CRYPTO_SERVICE_CODES"},
              "bonds.py": {"BASE_GOVERNMENT_TERMS", "BASE_CORPORATE_TERMS", "MAX_MONTHLY_CORPORATE_NEED_ISSUES"},
              "financial_products.py": {"FUTURE_TENORS", "OPTION_TENORS", "OPTION_MONEYNESS", "YIELD_TENORS", "CDS_NOTIONAL", "CDS_RECOVERY_RATE", "CDS_CONTRACT_SCALE", "DERIVATIVE_MARKET_CAP"},
              "funds.py": {"MINIMUM_AUM", "START_FUND_PRICE", "TARGET_COUNTRY_SECTOR_FUNDS_PER_COUNTRY", "TARGET_COUNTRY_SECTOR_ETFS_PER_COUNTRY", "WORLD_FUND_STYLES", "BOND_FUND_STYLES"}}
    for filename, names in wanted.items():
        path = ROOT / "src/kojakstreet/core" / filename
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id in names for t in node.targets):
                key = node.targets[0].id
                try:
                    val = ast.literal_eval(node.value)
                except ValueError:
                    val = ast.unparse(node.value)
                entries = val.items() if isinstance(val, dict) else [(key, val)]
                for entry, value in entries:
                    records.append(dict(zip(HEADER, ["model definition", key, entry, "FIXED", json.dumps(value, ensure_ascii=False), "literal current model parameter", "global rule / per code", "recipe/basket/universe constraints", "existing code definitions", "production/pricing/bootstrap", "none", f"src/kojakstreet/core/{filename}:{node.lineno}", "leave intact", "Reuse existing machinery; no new ranges proposed"])))
    registry = ROOT / "src/kojakstreet/core/countries.py"
    for node in ast.walk(ast.parse(registry.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "CountryDefinition":
            country = ast.literal_eval(node.args[0])
            for field, value in zip(("name", "currency_name", "symbol", "code", "style"), node.args):
                literal = ast.literal_eval(value)
                records.append(dict(zip(HEADER, ["country registry", country, field, "FIXED", literal, "exact constant", "per country", "20 countries, 21 currencies including GD", "registry", "company styles, macro, FX, derivatives, UI", "none", f"src/kojakstreet/core/countries.py:{node.lineno}", "leave intact", "world identity, not an amount budget"])))
    (OUT / "field-inventory.json").write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    sections = ["# Genesis: vollständiges Feldinventar\n\nStand 2026-10-07; gemessener Seed 2307 vor der Reparatur. `ROOT` bezeichnet steuerbare direkte Startgrößen; `FIXED` feste Konventionen; `EXISTING_RANDOMIZED` vorhandene Zufalls-/Hash-Erzeugung; `DERIVED` abhängige Größen; `BOOTSTRAP_RESULT` Ergebnis der vorhandenen Initialisierungsrechnungen. Formelbereiche und beobachtete Bereiche werden getrennt: ein Seed liefert keine theoretischen Grenzen.\n\nDie Tabelle enthält alle entdeckten Entity-Felder einschließlich privater Frühzustände, alle gespeicherten Weltfelder und die Modellparameter für Rezepte, Produkte, Profile und Universen. Vollständige Quellschreibstellen, Verbraucher und gemessene Einzelwerte stehen in `.cache/genesis-audit/field-inventory.json`. Mehrere aufgeführte Schreibformeln sind Initialisierungs-/Fallback-Zweige; sie sind keine zusätzlichen unabhängigen Zufallsziehungen. Ein identischer Datentyp/Nullwert allein begründet keine neue Wirtschaftsgröße.\n"]
    for category in dict.fromkeys(r["Category"] for r in records):
        group = [r for r in records if r["Category"] == category]
        # Keep the Markdown readable; complete provenance/consumer lists remain in exact JSON.
        display = []
        for record in group:
            row = [record[key] for key in HEADER]
            row[4] = row[4][:1400] + (" … vollständige Formeln im JSON" if len(row[4]) > 1400 else "")
            row[9] = row[9][:400] + (" … siehe JSON" if len(row[9]) > 400 else "")
            row[11] = row[11][:550] + (" … siehe JSON" if len(row[11]) > 550 else "")
            display.append(row)
        sections.append(f"\n## {category} ({len(group)} Felder/Definitionen)\n\n" + table(HEADER, display))
    (DOCS / "genesis-initialization-field-inventory-2026-10-07.md").write_text("\n".join(sections) + "\n", encoding="utf-8")
    return records


def suite_result():
    path = OUT / "full-suite.xml"
    if not path.exists():
        return "Die vollständige Suite läuft noch; dieser Abschnitt wird nach dem Abschluss aus dem unveränderten Testergebnis ergänzt."
    root = ET.parse(path).getroot()
    suites = list(root.iter("testsuite"))
    tests, failed, errors, skipped = [sum(int(s.get(k, 0)) for s in suites) for k in ("tests", "failures", "errors", "skipped")]
    seconds = sum(float(s.get("time", 0)) for s in suites)
    return f"Vollständiger Lauf: **{tests} Tests, {failed} fehlgeschlagen, {errors} Fehler, {skipped} übersprungen**, {seconds:.2f} s. Original: `.cache/genesis-audit/full-suite.xml` und `full-suite.log`."


def report(records):
    before = read(OUT / "before-2307/countries.json")
    world = read(OUT / "before-2307/checkpoint.json")["checkpoint"]
    final = read(OUT / "final-2307/countries.json")
    equivalence = read(OUT / "equivalence.json")
    old_hashes = read(OUT / "before-source-hashes.json")
    changed = [p for p, h in old_hashes.items() if hashlib.sha256((ROOT / p).read_bytes()).hexdigest() != h]
    (OUT / "changed-production-files.json").write_text(json.dumps(changed, indent=2), encoding="utf-8")
    for seed in (7, 42, 2307):
        assert equivalence[str(seed)]["day1_changed_fields"] == ["indizes"]
        assert equivalence[str(seed)]["day1_rng_exact"] and equivalence[str(seed)]["day2_exact"]
        assert equivalence[str(seed)]["all_340_displayed"]
    macro_identical = [k for k in before[0]["macro"] if all(c["macro"][k] == before[0]["macro"][k] for c in before)]
    totals = {
        "population": sum(c["macro"]["bevoelkerung"] for c in before),
        "GDP": sum(c["macro"]["bip_abs"] for c in before),
        "company_cap": sum(c["market_cap"] for c in before),
        "capacity": sum(c["production_capacity"] for c in before),
        "AUM": sum(a["aum"] for a in world["fonds"].values()),
        "crypto_cap": sum(a["market_cap"] for a in world["kryptos"].values()),
    }
    matrix = []
    for seed in (7, 42, 2307):
        b = read(OUT / f"before-{seed}/countries.json")
        a = read(OUT / f"final-{seed}/countries.json")
        for old, new in zip(b, a):
            broad = [t for t, row in old["indices"].items() if row["index_type"] == "Country"]
            matrix.append([seed, old["country"], "Country/ALL + 16 Sector", "Country/ALL + 16 Sector",
                           "ALL 64; Sector jeweils 4", ", ".join(broad), len(old["displayed_indices"]), len(new["displayed_indices"]),
                           "UI verdeckt " + ", ".join(old["collisions"]) if old["collisions"] else "keine fehlenden/unexpected"])
    text = f"""# Genesis-Audit und Reparatur der Länderindizes

Stand: 2026-10-07. Untersucht wurde der aktuelle, bereits optimierte Produktionsstand; die vorhandenen lokalen Änderungen wurden vor diesem Auftrag separat eingefroren. **Kein heterogener Startmodus und keine neuen Wertebereiche wurden implementiert.**

Alle 20 breiten Länderindizes existieren in der Welt. Der bestätigte Anzeigefehler entsteht durch Kürzelkollisionen: die Marktdatenliste ersetzt Indexzeilen durch gleichnamige Aktien. Zusätzlich bleiben einzelne Constituent-Kürzel nach der zweiten Aktieninitialisierung veraltet. Beide Fehler wurden an ihren Ursachen behoben, ohne Indexformeln oder Aktienerzeugung zu ändern.

## 1. Erzeugungspfad bis zum spielbaren Tag 1

`NewSimulationDialog.config()` (`ui_qt/new_simulation.py:94`) erzeugt GENESIS/Seed/0 Jahre. `IntegratedRuntime.__init__` (`adapters/legacy_runtime.py:52`) setzt Python- und NumPy-Seed, leert alte dynamische Attribute von `daten` und lädt das Modul neu. Die Engine-Imports können `daten` vorher laden; die explizite Neuladung nach dem Seed ist der maßgebliche Erzeugungslauf. Kalter Lauf, Wiederholung und vorher geladener Modulzustand lieferten bei Seed 2307 identische Startcheckpoints.

`daten.py`: Länder/Währungen und Spieler → 1.280 Unternehmen → 34 Rohstoffe → 90 verarbeitete Produkte/Dienstleistungen → 32 Kryptoketten → 340 Indizes → Ländermakro/Bevölkerung/Fiskal/Erwartungen → 420 gerichtete FX-Historien → Makro-/Portfolio-/GLI-Startpunkte → globale Startwerte → Fonds (mit Anleihenbootstrap) → Derivate → Labelcodes/Regime → Leeren aller Asset-Preishistorien → Produktionsbootstrap ohne Bevölkerungswachstum.

Danach Runtime-Fassade/Engines → Fiskal/Erwartungen erneut (setdefault) → Unternehmensuniversum erneut, Produkte/Population/Regionalprofile/Spezialisierungen → Fundamental-/Psychologieprüfungen → Produktionsbootstrap erneut → Hedge-Caches/Regime/Markt-Indizes vorwärmen → globale Historiensicherung → dynamischer Anleihenmarkt → DuckDB/Repository/Trading/Context → vollständige Tag-1-Aufzeichnung. `record_day` führt keine Simulationsperiode aus. Der Live-Worker aktiviert anschließend den bestehenden einzelnen Persistenz-Writer.

Die aufgezeichnete erste Aufrufreihenfolge einschließlich Dateinamen und Zeilen steht in `.cache/genesis-audit/before-2307/creation-calls.json`. Sie ersetzt keine Abhängigkeitsanalyse: wiederholte Aufrufe sind absichtlich dedupliziert.

## 2. Abhängigkeitsgraph

```mermaid
flowchart TD
 S[Mode, Seed, Datum] --> C[Länder, Währungen, Spieler]
 C --> U[Unternehmen: Sektor, Preis, 1 Mrd. Cap]
 U --> F[Shares, Umsatz, FCF, Margin, Cash, Debt, EPS]
 F --> P[Kapazität, Hash-Output-Mix]
 C --> M[Population, GDP, Rate, Inflation, Arbeitslosigkeit]
 M --> T[Fiskal, Credit, Erwartungen, regionale Profile]
 U --> I[Länder- und Branchenindizes]
 T --> B[Staats- und Unternehmensanleihen]
 F --> B
 I --> V[Fonds, ETF, Holdings, AUM]
 B --> V
 R[Rohstoffe, Produkte, Rezepte] --> PB[Produktionsbootstrap zweimal]
 K[Kryptoketten und Dienste] --> PB
 P --> PB
 T --> PB
 PB --> TR[Regionale Supply/Demand, Handel, Utilization]
 U --> D[Derivate und technische Vertragssaat]
 K --> D
 T --> D
 R --> D
 V --> D
 TR --> DB[Tag-1 Current/History, Checkpoint, UI-Scope]
 D --> DB
 B --> DB
 I --> DB
```

## 3. Vollständiges Feldinventar

Das [separate Inventar](genesis-initialization-field-inventory-2026-10-07.md) enthält **{len(records)}** Entity-/Weltfelder, verschachtelte Wirtschaftszustände und Modelldefinitionen in der vorgeschriebenen 14-spaltigen Tabelle. Keine Beschränkung auf die Beispielsammlung des Auftrags. Private Output-/Psychologie-/Hedge-Frühzustände sind enthalten. Die exakten Einzelwerte und vollständigen Schreib-/Lesestellen stehen außerdem in `.cache/genesis-audit/field-inventory.json`.

## 4. Einordnung der Startgrößen

Direkt steuerbare wirtschaftliche Größen werden als ROOT ausgewiesen, auch wenn heute alle Länder denselben Wert erhalten. Bestehende Namens-/Preis-/Cash-/Debt-/Crypto-/AUM-Zufälle bleiben EXISTING_RANDOMIZED. Deklarierte Universen und Vertragskonventionen sind FIXED. Shares, Gewichte, Verschuldungsquoten, Umsatz/FCF/Dividenden, Anleihendurationen und Partnerflüsse sind DERIVED. Die zweimal berechnete Produktion, regionale Wirtschaft, Preisindizes und Kapazitätsentwicklung sind BOOTSTRAP_RESULT.

Semantisch problematische Direktzuweisungen: EPS wird aus Preis/zufälligem P/E gesät; Global-Balance-Sheets, Liquidität und lange Renditen werden nicht aus dem fertigen Ländermakro/Anleihenbuch initialisiert; viele Derivatpreise bleiben zunächst 100. Diese Punkte sind Auditbefunde und wurden nicht wirtschaftlich umgebaut.

## 5. Tatsächliche Werte und bestehende Bereiche

Jedes Land: Bevölkerung 20.000.000, GDP 5.000, annual growth 0,010, policy rate 0,035, CPI 0,010, unemployment 0,060, balance sheet 1.000, rating BBB. Debt=GDP×0,62=3.100; annual deficit=GDP×0,025=125; private credit=GDP×0,92=4.600; credit growth 0,018. Erwartungswerte kopieren Wachstum/CPI/Rate/Arbeitslosigkeit; Überraschungen beginnen bei 0. Regierungsschulden und GDP verwenden dieselbe abstrakte Modellskala; eine Umrechnung in Aktienwährungsbeträge ist nicht definiert.

Aktien: je 4 Firmen × 16 Branchen × 20 Länder. Initial cap=1.000.000.000 je Unternehmen. Preis=round(U[18,145],2); shares=cap/price; cap=price×shares; EPS=max(0,1, price/U[14,28]); Cash=cap×U[0,04,0,22]; Debt=cap×U[0,05,0,45]. Funding-Bonds können diese beiden letzten Werte noch im Bootstrap verändern. Rating aus {{A-,BBB+,BBB,BBB-,BB+}}. Long/short/open interest=2,0%/1,6%/3,6% der Cap. Kein Small/Mid/Large-Cap-Saatmodell; heute nur unterschiedliche Preise/Shares bei gleichem Firmenwert.

Crypto: 8 Ketten je STORE/PAY/DATA/GRID. Preis round(U[12,180],2), Kapazität U[360,920], Supply STORE U[5 Mio.,50 Mio.], andere U[18 Mio.,220 Mio.], Transaktionen U[35.000,260.000], Gebühren U[8.000,95.000], Wallets U[18.000,160.000]. Task-Demand 620/760/540/500 jeweils ÷8, Share 1/8, technische Auslastung zunächst 0,7. Cap verwendet den ungerundeten Preis×Supply, während Kurs gerundet ist: bestehende kleine Inkonsistenz, kein unabhängiger Heterogenitätsregler.

Fonds: Preis 100, AUM=max(27 Mio., target×U[0,35,0,95]); min continued AUM 18 Mio.; tatsächliche Gebührenquote **0**. Anleihenliquidität GOV U[0,75,1], CORP U[0,35,0,85]. Bestehende Produktionsbereiche sind unten vollständig angegeben. Gemessene Min/Median/Max pro Entity-Feld stehen im Inventar; sie werden nicht als theoretische Bereiche ausgegeben.

## 6. Budgets und Erhaltung

"""
    budgets = [
        ["Population", totals["population"], "20×20 Mio.; fester Saatgesamtwert, kein expliziter Generator-Budgetverteiler", "400 Mio. kontrolliert verteilen; Länderminimum beachten; globaler Haushaltsbedarf folgt Summe"],
        ["GDP", totals["GDP"], "20×5.000; nicht aus Population abgeleitet", "gemeinsame Einheit/Invariante vor Änderung festlegen; Gewichte, Fiskal und FX hängen daran"],
        ["Unternehmen", 1280, "64/Land, 4 je Land/Sektor; Fill-Ziel 1280", "zunächst unverändert; sonst Produktdeckung und Lifecycle-Fill berücksichtigen"],
        ["Firmen-Cap", totals["company_cap"], "1.280×1 Mrd., bis auf Float-Arithmetik", "natürliches Startbudget; Preis/Shares/Fundamentals gemeinsam ableiten"],
        ["Shares", sum(a["aktien_anzahl"] for a in world["aktien"].values()), "kein unabhängiges/global fixiertes Aktienzahlbudget", "Shares=Cap/Preis; keine dritte unabhängige Ziehung"],
        ["Company capacity", totals["capacity"], "sektorabhängig aus Umsatz/Margin, dann Bootstrapwachstum", "kein fester physischer Gesamtpool; nicht zusätzlich neben Größe randomisieren"],
        ["Rohstoffe/Produkte/Dienste", "34+90", "feste Codes/Rezepte, Mengen aus Markthash und Bootstrap", "regionale Mengen werden auf globale Supply/Demand normiert; kein endlicher geologischer Deposit-Pool"],
        ["Fonds-AUM", totals["AUM"], "abhängig von underlying Caps/Mandaten und Zufallsfaktor; kein fixer Weltpool", "Investmentwerte überlappen Aktien/Bonds; nicht zum gleichen Welt-Cap-Budget addieren"],
        ["Crypto-Cap", totals["crypto_cap"], "unabhängige Preis-/Supply-Ziehungen; kein fixes globales Budget", "Task-Anzahl beibehalten; keine Gleichsetzung mit Aktienweltbudget"],
        ["Anleihen", len(world["bond_market"]), "1350 base +8 funding in Seed2307; nominal 100 ist Quote, kein aggregierter Schuldenbetrag", "64 Corporate-Basisbonds/Land plus bedarfsabhängig; Debt nicht aus Bond-Anzahl berechnen"],
        ["Liquidity", "M2=100000, RRP=7500, TGA=4500, GLI=15420", "teilweise direkte Saat und teilweise abgeleitete Größen; keine strikte Währungs-Geldmengenerhaltung", "Netliquidität konsistent berechnen, historische Referenzen passend setzen"],
        ["Trade", sum(c["macro"]["trade_balance"] for c in before), "Exports/Imports paarweise; balance anschließend um Weltmittel bereinigt", "Summe≈0 mit Floatrest; regionale Mengen und Ländergewichte normalisieren"],
        ["Player", 25000, "GD Cash, sonst FX=0, Loans=0, leere Positionen", "vollständig erhalten; keine Finanzierung der Welt durch Kleinanleger"],
    ]
    text += table(["Größe", "Gemessener Gesamtwert", "Aktuelle Semantik", "Bei Umverteilung"], budgets)
    text += "\n\n## 7. Gemessene Länder-Symmetrie\n\nSeed 2307, vollständiger spielbarer Start. GDP/rates/population sind exakt gleich; Preise, Shares, Cash, Debt, Namen, regionale Supply/Demand/Handel und ausgewählte Fonds unterscheiden sich. Die branchenbezogenen Umsätze und Kapazitäten folgen zunächst denselben Profilen. Float-Min/Max der Cap im Roh-JSON sind vollständig erhalten.\n\n"
    text += table(["Land", "Population", "GDP", "Firmen/Sektoren", "Cap gesamt", "Cap min/median/max", "Capacity", "GOV/CORP Bonds", "Fonds", "Index-Welt/UI vorher/UI nachher"],
                  [[c["country"], c["macro"]["bevoelkerung"], c["macro"]["bip_abs"], f"{c['company_count']}/16",
                    c["market_cap"], f"{c['cap_min']!r}/{c['cap_median']!r}/{c['cap_max']!r}", f"{c['production_capacity']:.9f}",
                    f"{c['bonds'].get('Government',0)}/{c['bonds'].get('Corporate',0)}", sum(c["funds"].values()),
                    f"17/{len(c['displayed_indices'])}/{len(f['displayed_indices'])}"] for c, f in zip(before, final)])
    text += "\n\nExakt gleiche Makrofelder: " + ", ".join(f"`{k}`" for k in macro_identical) + ".\n"
    text += """
## 8. Unternehmens-/Aktienkette

Der tatsächliche Pfad ist **Land/Sektor/Name → zufälliger Kurs + feste Cap → Shares=Cap/Kurs → Sektorprofil-Umsatz/FCF/Dividenden + unabhängiges EPS → Kapazität/Outputmix → Produktionsbootstrap**. Weder Bevölkerung noch GDP bestimmen die Unternehmensgröße. `SECTOR_PROFILES` hat P/S 0,8..6,0, FCF margin 0,045..0,28, dividend yield 0,006..0,045. Umsatz=Cap/P/S; FCF=Umsatz×Margin. Die vollständige Zuordnung je Branche steht im Inventar. Erst monatlich wird EPS=max(0,1, FCF/Shares) verwendet.

Basis-Capacity=max(12,sqrt(Umsatz)/95×(1+clamp(Margin,-0,35,0,45))); vorhandene Capacity wird 75:25 mit Basis gemischt, dann je Bootstrap wachsen/geschrumpft. Gleiche Sektorverteilung erklärt gleiche aggregierte Länderkapazität {capacity_note}. Ein zukünftiger Größenregler muss vor Fundamentals/Kapazität greifen. Kein täglicher Formelwechsel erforderlich, aber `setdefault`-Initialisierer aktualisieren vorhandene abgeleitete Felder nicht automatisch. Unternehmensnamen und Kürzel werden zweimal kompaktiert/ausgerichtet; die Reparatur pflegt Index-Referenzen dabei mit.

## 9. Ressourcen, Produkte, Dienste und Lebensfähigkeit

Kein separat randomisiertes geologisches Länder-Deposit-Modell gefunden. Die Vielfalt stammt aus festen Länder-/Sektorpräferenzen, erzeugten Firmennamen und einem stabilen Texthash h=((h×131+ord(char)) mod10000)/10000. Output-Auswahl hängt von Land/Sektor-Offset und Firmenindex ab. Outputmix ist normalisiert, mit primärer Rohgewichtung 0,58+0,24h, zweiter 0,12+0,15h, dritter 0,05+0,08h; vierter 0,03+0,06h nur bei h>0,36. Doppelte Codes werden durch Dictionary-/Normalisierungssemantik behandelt.

Markt-Scale=Basis×(0,68+0,84h); Basis essential260/strategic145/discretionary74/cyclical178/other132. Initial demand=max(10,scale×(1+(h−0,5)×0,18)), Texture 0,92+0,18h. Initial supply=max(12,demand×clamped balance); Rohbalance essential 0,985+0,085h, strategic0,88+0,24h, discretionary0,78+0,38h, sonst0,86+0,28h. Inventory-Cover service0,18+0,30h, essential0,72+0,65h, strategic0,88+0,85h, sonst0,48+0,78h; inventories=max(1,demand×cover).

Supply/Demand-Korridore essential 0,96..1,10; industrial0,90..1,18; cyclical0,84..1,24; strategic0,82..1,22; discretionary0,78..1,32. Produktcapacity verwendet max(initial supply×0,72, Unternehmenscapacity, direct demand×0,88); Rohstoffsupply hat ebenfalls Fallbacks. Das schützt die technische Lebensfähigkeit, bildet aber keine strikte Ressourcen-/Input-Erhaltung ab. Seed2307 hat **NEWC, UX und TEXT ohne ausgewiesene Produzenten**, trotzdem positiven Markt-Supply. Die Behauptung „global lebensfähig“ darf deshalb nicht mit vollständiger physischer Deckung jeder Kette verwechselt werden.

Regionale Nachfrage wird mit Population/Wachstum/Arbeitslosigkeit/Rate/Produktbonus gewichtet und auf global demand normiert. Regionale Supply wird nach Firmencapacity/Outputmix/Profilbonus verteilt und auf global supply normiert. Händler matchen Überschüsse/Defizite mit Ratingvertrauen und Kapazitäten; Welt-Trade-Balance wird um den Durchschnitt bereinigt. Rezepte, Code-Universen, vorhandene Spezialisation und Lebensfähigkeitskorridore zunächst unverändert lassen.

## 10. Länder-/Branchenboni und Anpassung

Jedes Land besitzt vier feste bevorzugte Branchen. Fokus=1,18+0,08 falls Branche bisher unbenutzt+(Position mod3)×0,04; damit 1,18..1,34 für die tatsächlichen bevorzugten Startfoki. Produktfoki sind je1,10 für die ersten3 Outputs. Regionaler Sektorbonus=Fokus×clamp(1,05−rating_default_probability×0,75,0,72,1,08), kein eigener RNG. `last_rebalanced_year=1990`.

Alle fünf Kalenderjahre (konkretes Gate `current_year-last_year>=5`, nicht ein täglich erzwungener 1825-Tage-Zähler) stärkt `_maybe_rebalance_country_profiles` den kapazitätsstärksten Sektor um0,08 bis1,38 und schwächt den kleinsten anderen um0,05 bis mindestens1,02. Die Branchenmenge wird dabei nicht als neuer Zufallssatz rotiert. Produktfoki werden abgeleitet neu gesetzt. Outputmix reagiert separat auf Chancen: maximal0,08 neuer Anteil bzw.0,045 Verschiebung mit Donor-Untergrenzen0,12/0,10. Kein weiterer unabhängiger zyklischer Länderbonus wurde in den Produktions-/Lifecycle-/Event-/Kalenderpfaden gefunden. Diese vorhandene Anpassung soll vom zukünftigen Startmodus unabhängig bleiben.

## 11. Makro-Invarianten und erster Tageswechsel

GDP ist heute direkt5.000, nicht Bevölkerung×Produktivität; ein GDP/Kopf-Feld existiert nicht. Bevölkerung beeinflusst Haushaltsbedarf und regionale Nachfrage. GDP gewichtet globale Länder-/Erwartungsaggregate und bestimmt Fiskal/Credit-Saat. Arbeitslosigkeit beeinflusst regionale Nachfrage, Bevölkerungstrend, erwartete Produktion/Makro; es gibt kein konsistentes „beschäftigte Personen×Produktivität = GDP“-System. Keine explizite Steuerrate/-einnahmensaat gefunden; Fiskalregeln sind vereinfachte jährliche Defizit-/Schuldenimpulse.

Korrektur nach der Implementierungsprüfung: Der erste Tageswechsel am 01.01.1990 führt keinen Monatsbericht aus. Die aktive DailySimulation plant den ersten Wirtschaftsbericht am 15.01.1990; `LETZTER_REPORT_MONAT=-1` allein löst ihn nicht früher aus. GDP=max(1000,old GDP×(1+growth/12)); Fiskal-, Credit-, Population-, Unternehmens-, Crypto- und Produktionswerte entwickeln sich dabei. Population hat später Untergrenze2 Mio.; monatliches Wachstum clamp((GDPgrowth−0,005)×0,025−max(0,unemployment−0,08)×0,010,−0,0025,0,0035). Deshalb müssen Startroots vor Bootstrap liegen und vorige Referenzwerte konsistent gesetzt werden.

Bestehende Direkt-Saatinkonsistenzen: globale CB-Bilanz5.000 statt Summe20×1.000=20.000; Netliquidität93.000 statt M2+CB−RRP−TGA=108.000. Der erste globale Update ersetzt CB durch Ländersumme und rechnet Netliquidität neu. 10Y-Saat0,047 ergibt Kurve0,009 bei3Y0,038, während `ensure_global_macro` Fallbacks rate+0,010 bzw.Kurve0,007 setzen würde. Tatsächliche Bondrenditen enthalten Credit-/Balance-Spreads und werden täglich beobachtet. Diese Diskontinuitäten dürfen in einem neuen Modus nicht durch unabhängige weitere Ziehungen vergrößert werden; fachliche Entscheidung zur gemeinsamen Initialisierung noch offen.

## 12. Anleihen, Rates und Credit

{bond_initialization_note}

Coupon=max(0,001, local policy rate+rating spread+Corporate0,012+min(0,020,term×0,0012)). Spread=default_probability×0,6+sqrt(default_probability)×0,018+0,0006. GOVdefault=0,75×PD×max(0,45,years/10), CORPohne0,75, oberes Limit0,95. Fair price ist halbjährliche abgezinste Coupon-/Nominalsumme, nominal100, duration=min(years,years/(1+yield)). Quote-Yield ergänzt Balance-Spread; Sekundärpreis glättet Fairvalue und enthält U[−0,018,0,018]×(1−liquidity)×max(1,duration/6). Preisgrenzen20..160.

Funding-Emissionen sind bedarfsabhängig. Staatsneed aus deficit ratio>0,035/debt ratio>0,85/interest burden>0,045; Firmenneed aus Cash/Umsatz<0,10/Debt/Cap>0,55/Margin<0,025. Begrenzt auf die höchsten Kandidaten, neue Firmenbonds erhöhen Debt und92% der Emissionsgröße als Cash. Base-Emissionen schreiben keine Proceeds. Coupon, Yield, Fairprice, Duration und Default-Risiko nie separat randomisieren; optional spätere Roots wären zusammenhängende Policy-/Credit-/Debt-Parameter.

## 13. Fonds und Index-Erzeugungsreihenfolge

Fonds nach Indizes, Makro und Rohstoffen/Crypto. Zunächst Anleihenmarkt sicherstellen. Pro Land1 Country Fund,1 Composite ETF,4 sektorspezifische aktive Fonds und3 Sector ETF. Globale16 Sector Funds,5 World-Stile (Equity/Growth/Dividend/Value/Small Cap),6 Bond-Stile,6 Commoditygruppen,4 Cryptotasks. Short/2x/−2x-ETF-Varianten ergänzen maximal floor(Basismandate/4), zyklisch von den ersten ETF-Mandaten; deshalb ist die Variantenanzahl pro Land **nicht symmetrisch** und kein fehlender Index.

Country target AUM=max(36 Mio.,country Cap×share), share0,018/0,012/0,006/0,004 jeMandat. Global-Sector0,004×Welt-Cap; World0,011×Welt-Cap; Bond max(200 Mio.,Welt-Cap×0,006); Commodity/crypto siehe vollständige Mandatformeln/Inventar. Varianten×0,22. Finanzunternehmen eines passenden Landes/Sektors werden als zufälliger Issuer ausgewählt. ETF-Holding ist genau der Index mit Gewicht1. Equity-Auswahl bis35 (kleine Universen vollständig), Bond-Auswahl bis80; Cashreserve aktiver Fonds/Rebalance beeinflusst effective weights. Gebührenquote0; Bootstrapdistribution folgt Underlyings. Leverage sind1/−1/2/−2, keine zusätzlichen Indexfamilien.

## 14. Historien und technische Saat

Spielbarer Genesis-Tag1 ist01.01.1990. Alle sechs Asset-Preisbücher haben **leere** `historie` nach dem expliziten Reset in `daten.py`; technische Erzeuger können vorher IPO-/100-/1000-Punkte anlegen. Anleihen besitzen Tag-1-Preisreferenzen. Makro-/Global-/Portfoliohistorien und GLI haben technische Startpunkte; FX hat420 leere gerichtete Serien, Stärke aller21 Währungen=1.

Produkt-/Rohstoffmetriken, Firmen-Input/Output und regionale Flüsse werden zweimal am selben Startdatum gebootstrapt: z.B. Supply-History-Länge2 bei90 Produkten. Das ist keine simulierte Vorgeschichte, aber auch keine reine seiteneffektfreie Initialisierung: Inventare, Druck, Preisindex, Capacity und Outputmix können zwischen den beiden Pässen fortgeschrieben werden. EMA startet ohne Historie neutral/0 und baut aus echten späteren Punkten auf; vorige Fundamentals/Taskmetriken werden mit aktuellen Startwerten gesetzt. Ein zukünftiger Modus darf diese technischen Same-Date-Punkte nicht als vorherige Wirtschaftstage ausgeben.

Derivate:1/3/6M Futures,1/3M Optionen mit moneyness0,95/1/1,05 undCALL/PUT,2/5/10/30Y Yield Futures,5Y Sovereign/Corporate CDS, FX Forward, Inflation Swap, Commodity Spread/Input-Cost Spread/Freight. Insgesamt566 inSeed2307. `_base_product` setzt Kurs100, Cap/OI100 Mio.; Optionen setzen Strike/Expiry aus Underlying, aber viele Preise werden erst beim ersten täglichen `_price_product` berechnet. Keine behauptete vollständige Day1-Fairvalue-Pricing-Kette; diese bestehende Saat ist ausdrücklich ein offener Architekturpunkt.

## 15. Erforderliche spätere Mode-/Save-/DB-/UI-Arbeit und Performance

Ein dritter Mode benötigt Enum/Config.normalized/trajectory_identity, GENESIS-artigen Pfad mit0 Prehistory, stabile Generation-Version/Root-Konfiguration in `world_generation`, den UI-Selector `new_simulation.py` und Start-Routing. Checkpoint-v7 speichert vorhandene numerische Felder und `world_generation`; neue Mode-Metadaten müssen validiert/migriert werden, ohne alte Saves umzudeuten. DuckDB kann dieselben strukturierten Current-/Daily-/Aggregate-Tabellen nutzen, solange keine neuen Wirtschaftsfelder entstehen. Root-Verteilung vor referenziellen Builders, Fundamentals, Fonds/Derivaten, Historiensaat und `record_day`; kein nachträgliches UI-Mirror.

Empfohlene Tests später: deterministische Mode/Seed-Identität, Budgets, Fundamentals/Preis/Shares-Konsistenz, Produktionsdeckung und Corridor-Grenzen, früheste Monats-/Policy-Schritte, Save/Load/exakte Recovery, kein Prehistory-Datum vorStart, alte GENESIS-Welt unverändert. Erwartete wiederkehrende Zusatzkosten des Modus **0**, wenn ausschließlich bestehende numerische Roots vor Erzeugung gesetzt werden. Das ist eine Architekturprognose, keine Messung einer nicht implementierten Funktion. Unterschiedliche Firmengrößen können bestehende Lifecycle-/Emissions-/Flush-Mengen mittelbar beeinflussen und müssen später gemessen werden.

## 16. Kleinste vorgeschlagene ROOT-Menge – noch ohne Bereiche

Zwei zusammenhängende Initialisierungsverteilungen genügen für sichtbar unterschiedliche Länder und Firmengrößen: **Ländergrößenanteile** für das vorhandene Weltbevölkerungsbudget400 Mio.; **Company-Cap-Anteile** für das vorhandene Aktienstartbudget1,28 Billionen, mit weiter4 Firmen proLand/Sektor. Preisgenerator beibehalten, Shares/Fundamentals/Capacity aus Cap ableiten. Eine proportionale GDP-Verteilung aus denselben Ländergrößenanteilen könnte das bestehende Gesamt-GDP100.000 bewahren; sie ist eine neue explizite Startinvariante, kein heute vorhandenes GDP/Kopf-Modell und braucht eine Produktentscheidung.

Ohne diese Entscheidung ist GDP ein dritter zusammenhängender ROOT-Vektor. Zusätzliche Rate-/Inflations-/Unemployment-/Rating-Ziehungen sind für die erste sichtbare Heterogenität nicht nötig und vergrößern Inkonsistenzrisiken. Kontrollierte Länder-/Firmenanteile, Ober-/Untergrenzen und Sektorcoverage werden gebraucht; **keine finalen Min/Max wurden ausgewählt**.

## 17. Systeme unverändert lassen

Bestehende Namen/Preisziehungen, Rohstoff-/Produktcodes und Rezepte, Outputmix-/Länderprofile samt Fünfjahresanpassung, Crypto-Tasks und Kapazitäten, Fondsmandate/Holdings, Indexformeln, Bondcoupons/Yields, Tagesformeln, Spieleraccounting und der dauerhafte Writer. Niemals EPS/Revenue/FCF/Shares/Cap/Capacity/Weights/Duration/Netliquidity unabhängig voneinander randomisieren.

## 18. Offene Architektur-/Designentscheidungen

GDP-Einheit und GDP/Kopf-Invariante; gemeinsame statt widersprüchliche Global-/Länder-Liquiditätssaat; unabhängiges EPS vs.FCF-EPS; zweimaliger zustandsverändernder Produktionsbootstrap; technische100-Derivatpreise vs.volle Startbewertung; Crypto-Cap aus ungerundetem Preis; Nullproduzenten trotz Supply-Fallbacks; Fondsvarianz und begrenzte Holdings als gewollte Markttiefe; gewünschte Weltgrößenbudgets und sektorweise Größenverteilung; spätere rückwärtskompatible Konfigurations-/Versionsidentität. Diese Befunde sind dokumentiert, nicht im Indexauftrag umgebaut.

## 19. Vollständige Indexfamilien

""".replace("{capacity_note}", "im gemessenen Seed")
    text += table(["Familie", "Scope", "Eligibility/Minimum", "Creation/IDs", "Wert/Update/kleines Universum"], [
        ["Country Composite / ALL", "ein Land, alle Branchen", "alle Aktien mit land==Land; kein Status-/Liquiditäts-/Min-Cap-Filter; Minimum0", "20 feste COMPOSITE_TICKERS, Name '<Land> Composite', index_type Country, branche All Sectors", "1000 Start; Marktkapitalgewichtung; alle passenden Mitglieder, auch1; leer bleibt1000"],
        ["Country Sector", "ein Land+eine der16 Branchen", "gleicher Land- und exakter Branche-String; Minimum0", "20×16, SECTOR_PREFIXES + suffix AUTO/CHEM/OIL/UTIL/IND/TEL/RET/CONS/FIN/PMET/HEAL/TECH/REAL/LOG/DEF/AGR", "gleiche Cap-Formel; leere Sektoren bleiben vorhanden"],
        ["Globale Indexfamilien", "keine im aktuellen Indexbuch", "Global Sector/World sind Fonds, keine zusätzlichen Indizes", "keine verpflichtenden Fantasiefamilien ergänzt", "unverändert"],
    ])
    text += "\n\nCountry-Kürzel AmeronAMX/AlbioniaABX/ArdoniaADX/ValoriaVLX/RomaraRMX/SoleriaSLX/NordmarkNMX/SarmatiaSMX/DanubriaDBX/CarpathiaCPX/AnatriaATX/AzariaAZX/IndaraIDX/HanxiaHNX/PacificaPFX/KoryoKRX/AmazoniaANX/CanadiaCNX/AuroriaAUX/SavannaSVX. Albionia-SectorprefixALX undArdoniaARX weichen absichtlich vomComposite ab. Definitionsreihenfolge Länderregistry, jeComposite dannBRANCHEN; keine RNG-Ziehung.\n\nDaily cached update rechnet previous_cap aus price/(1+change/100)×shares, current_cap ausprice×shares, level=max(1,old_level×sum_current/sum_previous), neu normalisierte Mitgliedergewichte. Nur aktuelle Unternehmensmitgliedschaft wird verwendet; kein erfundener Ausschlussfilter. IPO/Removal invalidiert den vorhandenen Schlüssel-Cache. Das Rebalancing ist Universe-membership und Cap-Gewichte, keine Top-N-Auswahl.\n\n## 20. Länder-Matrix für drei frische Seeds\n\nWeltseitig vollständig schon vor dem Fix. ALL ist die Benutzerbezeichnung für den vorhandenen breiten Composite mit `All Sectors`, kein fehlendes separates `*-ALL`-Instrument.\n\n"
    text += table(["Seed", "Land", "Erwartete Typen", "Tatsächliche Typen", "Constituents", "ALL-ID", "UI vorher", "UI nachher", "Fehlend/unexpected"], matrix)
    text += """

## 21. Bestätigte Ursachen

1. Stock-/Crypto-/Indexbücher dürfen bestehende gleiche Symbole besitzen. `MarketDataService.quotes()` verwendete jeweils das zuerst gefundene Buch; die Indexzeile bekam Stock-Typ/Stock-Name/Stock-Land/Stock-Preis. Daher fehlen inSeed2307 RMX/SLX/NMX/HNX/KRX als sichtbare Indizes, obwohl die20Composite und320Sector in `daten.indizes` undDuckDB vorhanden sind. Seed7 und42 haben andere betroffene Länder, jeweils5; die Matrix zeigt die tatsächlichen statt angenommener Länder.
2. `_align_existing_company_tickers` läuft zweimal und kann nach erneutem Compacting/Fallback andere Kürzel vergeben. `_rewrite_ticker_references` pflegte Depot/Perpetuals/Playerbonds, aber keine Indexmitglieder. Deshalb enthalten Startindizes teilweise alte Namen; der erste tägliche Indexupdate reparierte diese implizit. Die neue Referenzpflege macht bereitsTag1 vollständig.

## 22. Geänderte Produktionsdateien dieses Auftrags

"""
    text += "\n".join(f"- `{path}`" for path in changed)
    text += """

Zusätzlich `tests/test_genesis_country_indices.py`, angepasster `tests/test_market_quote_batch.py` und die zwei Auditwerkzeuge/Berichte. Vergleich gegen den eingefrorenen lokalen Stand, nicht gegen einen Git-Stand, der vorherige Performancearbeiten enthalten würde.

## 23. Reparatur und begrenzte Wirkung

Indexzeilen behalten beim Quote-Batch ihre eigene Anlageklasse und Datenreferenz; untypisierte `get/quote/price/region` und Handel behalten ihren bestehenden Vorrang. Explizite `quote(...,asset_type='Index')` und typed row keys erlauben korrekte Aktualisierung. Marktübersicht, Live-Shape, aktuelle Auswahl und Detail-Rückkehr verwenden Index-/Stock-Identität statt nurSymbol. Andere bestehende symbolische Auflösung wird nicht geändert.

Bei wirklichen Aktienkürzeländerungen werden vorhandene Index-Constituent-Schlüssel umgeschrieben, **mit denselben Gewichten**. Keine neue Indexdefinition, keine neue Aktie, keine Preis-/Cap-/RNG-Änderung. Die Referenzpflege läuft an der vorhandenen Umbenennung; bei identischen old/new-Kürzeln kein zusätzlicher Scan der340Indices. Tagesindexberechnung und sichtbare Scope-Übertragung bleiben bestehende Pfade.

## 24. Regressionen

8 neue Fälle:3Seeds×alle20Länder/17Indices/volleConstituents plus tatsächliche Qt-Länderfilter; Daily-Cap-Formel und alleFamilien/SaveLoad/DuckDB; kleinesUniversum mit1Stock undleerenSektoren; realerLive-Worker mit340Index-Quotes undRückkehr nachHiddenDays; Index-/Stock-Auswahl bei gleichemAMX durchRefresh,Live,Detail. Die Floatapprox-Formelassertion berücksichtigt unterschiedliche arithmetische Summenreihenfolgen; der unabhängige Vorher/Nachher-Checkpointvergleich ist dagegen **exakt ohne Floattoleranz**.

Gezielte Suite:43 bestanden (vor dem zusätzlichen Livefall); finale neue Regressionen8/8 bestanden. Das vorhandene Batch-Precedence-Testfixture wurde gezielt für das korrigierte Indexexception angepasst; untypisierte Stock-/Commodity-Priorität bleibt getestet.

## 25. Vollständige Testsuite

""" + suite_result()
    text += """

## 26. Save/Load und Persistenz

Regression speichert nach echtem Tageswechsel, entwickelt weiter, lädt zurück und vergleicht alle340Indices inklusiveHistory/Constituents/Preis exakt. Structured`asset_current` enthält alle340Index-Ticker undAnlageklasse, auchbeiStock-Kollision. KeineSchema-/Checkpointversion-/Durabilityänderung. Day1Indexzeilen/History waren schonvorhanden; nurdie Anzeige undMitgliedernamen warenfehlerhaft. Zurückladen alterSaves profitiert von vorhandener Initialisierung/Referenzpflege; keineAltsave-History erfunden.

## 27. Exakte RNG- und Wirtschaftsäquivalenz

Seeds7/42/2307 jeweilsfrischeisolierteWelten vor/nach. Alle Startcheckpointfelder außer `indizes` sind exakt gleich; Python-/NumPy-RNG exakt gleich. Innerhalb `indizes` sind nur die Mitgliederschlüssel korrigiert, nicht Level/Cap/Gewichte/History/Definitionen. Nach erstem Tageswechsel sind **gesamte Checkpoints einschließlich allerwirtschaftlichenFelder undRNG exakt gleich**. Kalter/repeat/warmSeed2307 ebenfallsidentisch. Rohbelege `equivalence.json`, `before-*/checkpoint.json`, `final-*/checkpoint.json`, `day2-checkpoint.json`; keineDatums-/Float-/Cashnormalisierung.

## 28. Wiederkehrende Kosten

Die cached Tagesindexberechnung in `market_calculations.py` und ihre Mitgliedschaftscaches sind gegen den eingefrorenen Stand byte-identisch. Es entsteht kein zusätzlicher täglicher Welt-/Aktien-/Indexscan; nurbestehenderQuote-Batch erhält einen konstanten Branch fürIndexzeilen. Der sichtbareUI-Shape-Check ergänzt bereitsvorhandene340Indexidentitäten; keineHidden-UI-Synchronisation oderVollweltübertragung. Die Umbenennung pflegt340Mitgliedermappings nurbei tatsächlichgeändertenStock-Symbolen. Der vollständigeTestlauf enthält den bestehendenInteractive-Performancebudgettest; dessenErgebnissteht inAbschnitt25. Keineerneute native300ms-Messungwirdbehauptet, solange sie nicht durchgeführt ist. EinweitererMarktpreis-/Daily-Index-Algorithmuswurde nicht implementiert.
"""
    # Correct explicit bond term/count statements from the source, not guessed nominal budgets.
    bond_source = (ROOT / "src/kojakstreet/core/bonds.py").read_text(encoding="utf-8")
    constants = {}
    for node in ast.walk(ast.parse(bond_source)):
        if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name) and node.targets[0].id in {"BASE_GOVERNMENT_TERMS", "BASE_CORPORATE_TERMS"}:
            constants[node.targets[0].id] = ast.literal_eval(node.value)
    text = text.replace("{bond_initialization_note}",
                        f"Government-Basislaufzeiten {constants['BASE_GOVERNMENT_TERMS']} Jahre, Corporate-Basislaufzeiten {constants['BASE_CORPORATE_TERMS']} Jahre. Seed 2307: 1.350 Basisquotes (60 GOV + 1.280 CORP und 10 weitere Basisaufstockungen aus vorhandener Kürzelausrichtung) + 8 Funding-Quotes = 1.358 Quotes. Konkrete Issue-/Ticker-Daten stehen im Inventar; Nominal 100 ist keine Welt-Schuldenverteilung. Die zehn alten Corporate-Quotes verweisen im gemessenen Start auf nicht mehr vorhandene Aktienkürzel. Dieser zusätzliche Genesis-Referenzbefund ist relevant für das spätere Initialisierungsdesign; er wird im begrenzten Indexauftrag nicht durch Änderungen am Anleihenmarkt behoben.")
    text = text.replace("die zwei Auditwerkzeuge/Berichte", "die drei Auditwerkzeuge/Berichte")
    text = text.replace("Commodity/crypto siehe vollständige Mandatformeln/Inventar", "Commodity-Gruppen 0,018×Gruppen-Cap; Crypto-Tasks 0,030×Task-Cap")
    text = text.replace("Zurückladen alterSaves profitiert von vorhandener Initialisierung/Referenzpflege; keineAltsave-History erfunden.",
                        "Vorhandene gespeicherte Indexbücher werden durch die korrigierte Anzeige ebenfalls vollständig sichtbar. JSON-Saves stellen ihre gespeicherten Mitgliedschaften unverändert wieder her; alte veraltete Constituent-Kürzel werden nicht geraten. Der vorhandene nächste Tagesindexupdate aktualisiert sie aus dem Aktienbuch. Keine Altsave-Historie wird erfunden.")
    text = text.replace("Die aufgezeichnete erste Aufrufreihenfolge", "Der UI-Einstieg `ui_qt/app.py:793` routet GENESIS direkt zu IntegratedRuntime und anschließend zum Live-Worker; ein gespeichertes `world_generation`-Config wird im aktuellen GENESIS-Pfad nicht angelegt. ESTABLISHED nutzt `world_generator.generate`, im Standardpfad hybrid `fast_history_v2` plus täglichen Burn-in; `production_equivalent=True` nutzt vollständige Tageszyklen. Keine dieser Vorhistorien soll für den dritten Sofortstart übernommen werden.\n\nDie aufgezeichnete erste Aufrufreihenfolge")
    text = text.replace("Fondsvarianz und begrenzte Holdings", "zusätzliche Corporate-Basisquotes mit alten Kürzelreferenzen; Fondsvarianz und begrenzte Holdings")
    text = text.replace("Gebührenquote0; Bootstrapdistribution", "Gebührenquote 0; Bootstrapdistribution")
    text = text.replace("Leverage sind1/−1/2/−2", "Leverage sind 1/−1/2/−2")
    text = text.replace("Global-Sector0,004", "Global-Sector 0,004").replace("World0,011", "World 0,011")
    text = text.replace("Seed2307", "Seed 2307").replace("Seed7", "Seed 7").replace("Seed42", "Seed 42")
    # Editorial spacing for prose, leaving identifiers and source expressions intact.
    replacements = {
        "Annual": "Annual", "min continued AUM": "Mindest-AUM für den Fortbestand",
        "dann je Bootstrap wachsen/geschrumpft": "dann je Bootstrap vergrößert oder verkleinert",
        "Basis essential260/strategic145/discretionary74/cyclical178/other132": "Basis essential 260 / strategic 145 / discretionary 74 / cyclical 178 / other 132",
        "strategic0,88": "strategic 0,88", "discretionary0,78": "discretionary 0,78", "sonst0,86": "sonst 0,86",
        "service0,18": "service 0,18", "essential0,72": "essential 0,72",
        "sonst0,48": "sonst 0,48", "industrial0,90": "industrial 0,90", "cyclical0,84": "cyclical 0,84",
        "strategic0,82": "strategic 0,82", "Pro Land1": "Pro Land 1", "Fund,1": "Fund, 1",
        "ETF,4": "ETF, 4", "und3 Sector": "und 3 Sector", "Globale16": "Globale 16",
        "Funds,5": "Funds, 5", "),6 Bond": "), 6 Bond", "Stile,6": "Stile, 6", "gruppen,4": "gruppen, 4",
        "share0,018": "share 0,018", "Gewicht1": "Gewicht 1", "bis35": "bis 35", "bis80": "bis 80",
        "Tag1 ist01.01.1990": "Tag 1 ist 01.01.1990", "FX hat420": "FX hat 420", "aller21": "aller 21",
        "Supply-History-Länge2 bei90": "Supply-History-Länge 2 bei 90",
        "Derivate:1/3/6M": "Derivate: 1/3/6M", "undCALL/PUT": "und CALL/PUT", "Insgesamt566 inSeed": "Insgesamt 566 in Seed",
        "setzt Kurs100, Cap/OI100": "setzt Kurs 100, Cap/OI 100", "mit0 Prehistory": "mit 0 Prehistory",
        "vorStart": "vor Start", "Weltbevölkerungsbudget400": "Weltbevölkerungsbudget 400",
        "Aktienstartbudget1,28": "Aktienstartbudget 1,28", "mit weiter4 Firmen proLand/Sektor": "mit weiterhin 4 Firmen pro Land/Sektor",
        "Gesamt-GDP100.000": "Gesamt-GDP 100.000", "vs.FCF-EPS": "vs. FCF-EPS",
        "technische100-Derivatpreise vs.volle": "technische 100-Derivatpreise vs. volle",
        "eine der16 Branchen": "eine der 16 Branchen", "Minimum0": "Minimum 0", "auch1": "auch 1", "leer bleibt1000": "leer bleibt 1000",
        "Definitionsreihenfolge Länderregistry, jeComposite dannBRANCHEN": "Definitionsreihenfolge Länderregistry, je Composite dann BRANCHEN",
        "ausprice×shares": "aus price×shares", "Albionia-SectorprefixALX undArdoniaARX": "Albionia-Sectorprefix ALX und Ardonia ARX",
        "vomComposite": "vom Composite", "AmeronAMX/AlbioniaABX/ArdoniaADX": "Ameron AMX / Albionia ABX / Ardonia ADX",
        "vorhandenen340Indices": "vorhandenen 340 Indices", "der340Indices": "der 340 Indices",
        "bestehendenInteractive-Performancebudgettest": "bestehenden Interactive-Performancebudgettest",
        "bereitsvorhandene340Indexidentitäten": "bereits vorhandene 340 Indexidentitäten",
        "einzelne Constituent-Kürzel": "einzelne Constituent-Kürzel",
        "je1,10 für die ersten3": "je 1,10 für die ersten 3", "um0,08 bis1,38": "um 0,08 bis 1,38",
        "um0,05 bis mindestens1,02": "um 0,05 bis mindestens 1,02", "maximal0,08": "maximal 0,08",
        "bzw.0,045": "bzw. 0,045", "Donor-Untergrenzen0,12/0,10": "Donor-Untergrenzen 0,12/0,10",
        "heute direkt5.000": "heute direkt 5.000", "Untergrenze2 Mio.": "Untergrenze 2 Mio.",
        "CB-Bilanz5.000": "CB-Bilanz 5.000", "Netliquidität93.000": "Netliquidität 93.000",
        "10Y-Saat0,047": "10Y-Saat 0,047", "Kurve0,009 bei3Y0,038": "Kurve 0,009 bei 3Y 0,038",
        "bzw.Kurve0,007": "bzw. Kurve 0,007", "Corporate0,012": "Corporate 0,012",
        "GOVdefault": "GOV default", "CORPohne0,75": "CORP ohne Faktor 0,75", "Limit0,95": "Limit 0,95",
        "nominal100": "nominal 100", "Preisgrenzen20..160": "Preisgrenzen 20..160", "Debt und92%": "Debt und 92%",
        "inSeed ": "in Seed ", "8 neue Fälle:3": "8 neue Fälle: 3", "realeLive": "reale Live",
        "realerLive-Worker mit340": "realer Live-Worker mit 340 ", "Gezielte Suite:43": "Gezielte Suite: 43",
        "Regressionen8/8": "Regressionen 8/8", "Seeds7/42/2307": "Seeds 7/42/2307",
        "Felder undRNG": "Felder und RNG", "Kalter/repeat/warmSeed": "Kalter/repeat/warm Seed",
        "sichtbareUI-Shape-Check": "sichtbare UI-Shape-Check", "vollständigeTestlauf": "vollständige Testlauf",
        "EinweitererMarktpreis": "Ein weiterer Marktpreis",
        "jeMandat": "je Mandat", "Varianten×": "Varianten ×", "jeSTORE": "je STORE",
        "Gate ": "Gate ", "Marktpreis-/Daily-Index-Algorithmuswurde": "Marktpreis-/Daily-Index-Algorithmus wurde",
        "Script": "Script", "vorhandene340": "vorhandene 340", "allerwirtschaftlichenFelder": "aller wirtschaftlichen Felder",
        "Seed 2307 ebenfallsidentisch": "Seed 2307 ebenfalls identisch", "jeweilsfrischeisolierteWelten": "jeweils frische isolierte Welten",
        "keineDatums-/Float-/Cashnormalisierung": "keine Datums-/Float-/Cashnormalisierung",
        "beiStock-Kollision": "bei Stock-Kollision", "Structured`asset_current`": "Structured `asset_current`",
        "KeineSchema-/Checkpointversion-/Durabilityänderung": "Keine Schema-/Checkpointversion-/Durabilityänderung",
        "Day1Indexzeilen/History waren schonvorhanden": "Day-1-Indexzeilen/History waren schon vorhanden",
        "nurdie Anzeige undMitgliedernamen warenfehlerhaft": "nur die Anzeige und Mitgliedernamen waren fehlerhaft",
        "einschließlich allerwirtschaftlichenFelder": "einschließlich aller wirtschaftlichen Felder",
        "Index-Quotes undRückkehr nachHiddenDays": "Index-Quotes und Rückkehr nach Hidden Days",
        "bleibt getestet": "bleibt getestet", "keindaily": "kein daily",
        "bei tatsächlichgeändertenStock-Symbolen": "bei tatsächlich geänderten Stock-Symbolen",
        "Die Umbenennung pflegt340Mitgliedermappings nurbei": "Die Umbenennung pflegt 340 Mitgliedermappings nur bei",
        "Konkrete Issue-/Ticker-Daten": "Konkrete Issue-/Ticker-Daten",
        "nach erstem Tageswechsel": "nach erstem Tageswechsel",
        "zusätzlicher täglicher Welt-/Aktien-/Indexscan; nurbestehenderQuote-Batch": "zusätzlicher täglicher Welt-/Aktien-/Indexscan; nur der bestehende Quote-Batch",
        "Branch fürIndexzeilen": "Branch für Indexzeilen", "keineHidden-UI-Synchronisation oderVollweltübertragung": "keine Hidden-UI-Synchronisation oder Vollweltübertragung",
        "vorhandenenInteractive-Performancebudgettest": "vorhandenen Interactive-Performancebudgettest",
        "dessenErgebnissteht inAbschnitt25": "dessen Ergebnis steht in Abschnitt 25",
        "Keineerneute native300ms-Messungwirdbehauptet": "Keine erneute native 300-ms-Messung wird behauptet",
        "nicht durchgeführt ist": "nicht durchgeführt ist",
        "kleinesUniversum mit1Stock undleerenSektoren": "kleines Universum mit 1 Stock und leeren Sektoren",
        "alleFamilien/SaveLoad/DuckDB": "alle Familien/SaveLoad/DuckDB",
        "3Seeds×alle20Länder/17Indices/volleConstituents": "3 Seeds × alle 20 Länder / 17 Indices / volle Constituents",
        "Index-/Stock-Auswahl bei gleichemAMX durchRefresh,Live,Detail": "Index-/Stock-Auswahl bei gleichem AMX durch Refresh, Live, Detail",
        "43 bestanden": "43 bestanden", "8/8 bestanden": "8/8 bestanden",
        "Vorher/Nachher-Checkpointvergleich": "Vorher/Nachher-Checkpointvergleich",
        "alle340Indices inklusiveHistory/Constituents/Preis": "alle 340 Indices inklusive History/Constituents/Preis",
        "alle340Index-Ticker undAnlageklasse, auchbei": "alle 340 Index-Ticker und Anlageklasse, auch bei",
        "beim Quote-Batch": "beim Quote-Batch", "statt nurSymbol": "statt nur Symbol",
        "bleiben bestehende Pfade": "bleiben bestehende Pfade", "bei identischen old/new-Kürzeln kein": "bei identischen old/new-Kürzeln kein",
        "bekam Stock-Typ": "bekam Stock-Typ", "haben andere betroffene Länder, jeweils5": "haben andere betroffene Länder, jeweils 5",
        "als sichtbare Indizes, obwohl die20Composite und320Sector": "als sichtbare Indizes, obwohl die 20 Composite und 320 Sector",
        "undDuckDB vorhanden": "und DuckDB vorhanden", "Seed 7 und42": "Seed 7 und 42",
        "bereitsTag1 vollständig": "bereits Tag 1 vollständig", "vor/nach": "vor/nach",
        "Erster Step auf01.01.1990": "Erster Step auf 01.01.1990", "vorige Referenzwerte": "vorige Referenzwerte",
        "Erzeugungsreihenfolge": "Erzeugungsreihenfolge", "1 je Firma": "1 je Firma",
        "Startfoki": "Startfoki", "Variantenanzahl pro Land": "Variantenanzahl pro Land",
        "Keineerneute": "Keine erneute", "gezielt für das korrigierte Indexexception": "gezielt für die korrigierte Index-Ausnahme",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    costs_path = OUT / "index-costs.json"
    if costs_path.exists():
        costs = read(costs_path)
        text += "\n\nIsolierte Messung nach Abschluss der Tests, jeweils 100 abwechselnde Vorher-/Nachher-Proben und 5 Warm-ups; unveränderte Genesis-Größe, Aufbau/Kopieren außerhalb der Messung. Kein vollständiger Tages- oder UI-Cadence-Benchmark.\n\n"
        operations = {"quotes": "Vollständiger Quote-Batch", "rename_identity": "Referenzpflege ohne Umbenennung",
                      "rename_actual": "Referenzpflege mit 10 Umbenennungen"}
        text += table(["Operation", "Vorher median/p95/max ms", "Nachher median/p95/max ms"],
                      [[operations[mode], "/".join(f"{row['before'][k]:.4f}" for k in ("median_ms", "p95_ms", "max_ms")),
                        "/".join(f"{row['after'][k]:.4f}" for k in ("median_ms", "p95_ms", "max_ms"))]
                       for mode, row in costs.items() if isinstance(row, dict)])
        text += f"\n\nDer Quote-Batch bleibt im Median bei rund {costs['quotes']['after']['median_ms']:.2f} ms."
        text += (f" Die Prüfung identischer Kürzel benötigt {costs['rename_identity']['after']['median_ms']:.2f} ms, "
                 f"die vollständige Referenzpflege bei zehn tatsächlichen Umbenennungen {costs['rename_actual']['after']['median_ms']:.2f} ms. "
                 "Diese Pflege hängt am vorhandenen Unternehmens-Initialisierungspfad, nicht am Tagesindexalgorithmus. "
                 "Die beobachteten Maximalwerte des Quote-Batches streuen in beiden Versionen; aus dieser isolierten Messung wird keine native Tageslatenz abgeleitet.")
        assert costs["daily_index_source_unchanged"]
    (DOCS / "genesis-initialization-and-country-index-audit-2026-10-07.md").write_text(text + "\n", encoding="utf-8")
    print(json.dumps({"inventory_rows": len(records), "changed_production_files": changed, "suite": suite_result()}, ensure_ascii=False))


if __name__ == "__main__":
    report(inventory())
