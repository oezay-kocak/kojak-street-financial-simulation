"""Dynamic crypto-chain universe and fundamentals."""

from __future__ import annotations

import random
import string
from dataclasses import dataclass
from types import ModuleType

TARGET_CRYPTO_COUNT = 32
START_CHAINS_PER_TASK = 8
MIN_CHAINS_PER_TASK = 5
SHUTDOWN_PRICE = 2.0
SHUTDOWN_SHARE = 0.003


@dataclass(frozen=True, slots=True)
class CryptoTaskType:
    code: str
    label: str
    description: str
    fixed_supply: bool
    base_demand: float


CRYPTO_TASK_TYPES: dict[str, CryptoTaskType] = {
    "STORE": CryptoTaskType("STORE", "Digital Store of Value", "Digital gold and reserve collateral", True, 620.0),
    "PAY": CryptoTaskType("PAY", "Payment Rails", "Transaction capacity for retail, banks and companies", False, 760.0),
    "DATA": CryptoTaskType("DATA", "Decentralized Storage", "Storage capacity for technology and enterprise demand", False, 540.0),
    "GRID": CryptoTaskType("GRID", "Energy Trading Grid", "Settlement and capacity for digital power markets", False, 500.0),
}

TASK_METRIC_KEYS = {
    "STORE": ["hashrate"],
    "PAY": ["tps", "confirmation_time", "merchant_adoption"],
    "DATA": ["storage_capacity", "used_storage", "price_per_tb"],
    "GRID": ["energy_volume", "smart_meter_nodes", "grid_capacity", "energy_transactions", "settlement_speed"],
}

CRYPTO_SERVICE_CODES = {
    "STORE": "CRSTORE",
    "PAY": "CRPAY",
    "DATA": "CRDATA",
    "GRID": "CRGRID",
}

NAME_PARTS = {
    "STORE": {
        "prefix": ["Aurum", "Vault", "Hash", "Sovereign", "Anchor", "Bit", "Reserve", "Noble"],
        "core": ["Core", "Mint", "Stone", "Ledger", "Prime", "Ore", "Seal", "Node"],
        "suffix": ["Coin", "Gold", "Token", "Chain", "Reserve"],
    },
    "PAY": {
        "prefix": ["Swift", "Pulse", "Relay", "Merchant", "Flux", "Nova", "Clear", "Rapid"],
        "core": ["Pay", "Route", "Rail", "Settle", "Link", "Flow", "Bridge", "Loop"],
        "suffix": ["Network", "Coin", "Protocol", "Chain", "Pay"],
    },
    "DATA": {
        "prefix": ["File", "Archive", "Cloud", "Shard", "Vault", "Data", "Mirror", "Block"],
        "core": ["Store", "Weave", "Cache", "Grid", "Drive", "Stack", "Layer", "Nest"],
        "suffix": ["Chain", "Net", "Storage", "Protocol", "Node"],
    },
    "GRID": {
        "prefix": ["Grid", "Volt", "Watt", "Spark", "Meter", "Power", "Amp", "Flux"],
        "core": ["Trade", "Mesh", "Current", "Node", "Grid", "Pulse", "Relay", "Charge"],
        "suffix": ["Chain", "Grid", "Protocol", "Net", "Energy"],
    },
}


def ensure_crypto_universe(daten: ModuleType, *, reset: bool = False) -> list[str]:
    if reset or not hasattr(daten, "kryptos"):
        daten.kryptos = {}
    created: list[str] = []
    counts = _task_counts(daten.kryptos)
    for task_code in CRYPTO_TASK_TYPES:
        for index in range(max(0, START_CHAINS_PER_TASK - counts.get(task_code, 0))):
            ticker = _unique_ticker(daten.kryptos)
            daten.kryptos[ticker] = _new_crypto_asset(ticker, task_code, index)
            created.append(ticker)
    while len(daten.kryptos) < TARGET_CRYPTO_COUNT:
        task_code = min(CRYPTO_TASK_TYPES, key=lambda code: _task_counts(daten.kryptos).get(code, 0))
        ticker = _unique_ticker(daten.kryptos)
        daten.kryptos[ticker] = _new_crypto_asset(ticker, task_code, len(daten.kryptos))
        created.append(ticker)
    return created


def update_crypto_economy(daten: ModuleType) -> None:
    ensure_crypto_universe(daten)
    demand_by_task = _crypto_demand_by_task(daten)
    for task_code, task in CRYPTO_TASK_TYPES.items():
        chains = [asset for asset in daten.kryptos.values() if asset.get("task_type") == task_code]
        if not chains:
            continue
        total_capacity = sum(max(1.0, float(asset.get("network_capacity", 1.0))) for asset in chains)
        total_demand = demand_by_task.get(task_code, task.base_demand)
        raw_shares = []
        for asset in chains:
            capacity = max(1.0, float(asset.get("network_capacity", 1.0)))
            raw_shares.append((asset, (capacity / total_capacity) * _chain_quality(asset)))
        raw_total = sum(score for _asset, score in raw_shares) or 1.0
        for asset, raw_share in raw_shares:
            previous_demand = float(asset.get("demand", total_demand / len(chains)))
            previous_share = float(asset.get("market_share", 1.0 / len(chains)))
            previous_utilization = float(asset.get("network_utilization", 0.7))
            target_share = raw_share / raw_total
            asset["target_market_share"] = target_share
            asset["market_share"] = max(0.0001, (previous_share * 0.82) + (target_share * 0.18))
            asset["demand"] = max(1.0, total_demand * asset["market_share"])
            asset["demand_change"] = (asset["demand"] / previous_demand - 1.0) if previous_demand else 0.0
            asset["market_share_change"] = (asset["market_share"] / previous_share - 1.0) if previous_share else 0.0
            asset["network_utilization"] = max(0.0, min(1.8, asset["demand"] / max(1.0, float(asset.get("network_capacity", 1.0)))))
            asset["network_utilization_change"] = (
                asset["network_utilization"] / previous_utilization - 1.0
            ) if previous_utilization else 0.0
            asset["adoption_score"] = max(0.0, min(1.5, asset["market_share"] * len(chains) * _chain_quality(asset)))


def shutdown_and_replace_crypto_chains(daten: ModuleType) -> list[tuple[str, str]]:
    removed: list[tuple[str, str]] = []
    for ticker, asset in list(getattr(daten, "kryptos", {}).items()):
        history_len = len(asset.get("historie", []))
        weak_price = float(asset.get("kurs", 100.0)) <= SHUTDOWN_PRICE
        weak_share = float(asset.get("market_share", 1.0)) <= SHUTDOWN_SHARE
        weak_demand = float(asset.get("demand_change", 0.0)) < -0.08
        if history_len > 90 and (weak_price or (weak_share and weak_demand)):
            removed.append((ticker, str(asset.get("name", ticker))))
            daten.kryptos.pop(ticker, None)
            daten.depot.pop(ticker, None)
            for key, position in list(getattr(daten, "perpetuals", {}).items()):
                if position.get("ticker") == ticker:
                    daten.perpetuals.pop(key, None)
    for task_code in CRYPTO_TASK_TYPES:
        while _task_counts(daten.kryptos).get(task_code, 0) < MIN_CHAINS_PER_TASK:
            ticker = _unique_ticker(daten.kryptos)
            daten.kryptos[ticker] = _new_crypto_asset(ticker, task_code, len(daten.kryptos))
    while len(daten.kryptos) < TARGET_CRYPTO_COUNT:
        task_code = max(CRYPTO_TASK_TYPES, key=lambda code: _crypto_task_opportunity(daten, code))
        ticker = _unique_ticker(daten.kryptos)
        daten.kryptos[ticker] = _new_crypto_asset(ticker, task_code, len(daten.kryptos))
    return removed


def ensure_crypto_fundamentals(asset: dict) -> None:
    task = CRYPTO_TASK_TYPES.get(str(asset.get("task_type", "PAY")), CRYPTO_TASK_TYPES["PAY"])
    price = float(asset.get("kurs", 100.0))
    transactions = float(asset.get("transactions", 100_000.0))
    fees = float(asset.get("chain_fees", asset.get("gebuehren", 50_000.0)))
    supply = float(asset.get("circulating_supply", 21_000_000.0 if task.fixed_supply else 10_000_000.0))
    wallets = float(asset.get("active_wallets", 50_000.0))
    asset.setdefault("task_type", task.code)
    asset.setdefault("branche", task.label)
    asset.setdefault("kategorie", task.label)
    asset.setdefault("typ", "Crypto Chain")
    asset.setdefault("network_capacity", 500.0)
    asset.setdefault("demand", task.base_demand / START_CHAINS_PER_TASK)
    asset.setdefault("demand_change", 0.0)
    asset.setdefault("market_share", 1.0 / START_CHAINS_PER_TASK)
    asset.setdefault("network_utilization", 0.7)
    asset.setdefault("adoption_score", 1.0)
    asset.setdefault("transactions", transactions)
    asset.setdefault("previous_transactions", transactions)
    asset.setdefault("transaction_change", 0.0)
    asset.setdefault("chain_fees", fees)
    asset.setdefault("previous_chain_fees", fees)
    asset.setdefault("fee_change", 0.0)
    asset.setdefault("average_fee", fees / max(1.0, transactions))
    asset.setdefault("previous_average_fee", asset["average_fee"])
    asset.setdefault("average_fee_change", 0.0)
    asset.setdefault("circulating_supply", supply)
    asset.setdefault("previous_circulating_supply", supply)
    asset.setdefault("circulating_supply_change", 0.0)
    asset.setdefault("inflation_rate", 0.0)
    asset.setdefault("active_wallets", wallets)
    asset.setdefault("previous_active_wallets", wallets)
    asset.setdefault("wallet_change", 0.0)
    asset.setdefault("market_cap", price * supply)
    asset.setdefault("long_interest", asset["market_cap"] * 0.035)
    asset.setdefault("short_interest", asset["market_cap"] * 0.030)
    asset.setdefault("open_interest", float(asset["long_interest"]) + float(asset["short_interest"]))
    asset.setdefault("open_interest_history", [])
    asset.setdefault("service_code", CRYPTO_SERVICE_CODES.get(task.code, "CRPAY"))
    _ensure_task_metrics(asset)


def update_crypto_fundamentals(
    asset: dict,
    *,
    macro_growth: float,
    world_rate: float,
    event_result: float,
) -> None:
    ensure_crypto_fundamentals(asset)
    _capture_task_metric_previous(asset)
    previous_transactions = max(1.0, float(asset.get("transactions", 100_000.0)))
    previous_fees = max(1.0, float(asset.get("chain_fees", asset.get("gebuehren", 50_000.0))))
    previous_average_fee = max(0.0001, float(asset.get("average_fee", previous_fees / previous_transactions)))
    previous_supply = max(1.0, float(asset.get("circulating_supply", 10_000_000.0)))
    previous_wallets = max(1.0, float(asset.get("active_wallets", 50_000.0)))
    network_activity = float(asset.get("netzwerk_aktivitaet", 0.0))
    network_fees = float(asset.get("netzwerk_fees", 0.0))
    rate_pressure = 0.035 - world_rate
    demand_change = float(asset.get("demand_change", 0.0))
    utilization = float(asset.get("network_utilization", 0.7))
    adoption = float(asset.get("adoption_score", 1.0))
    task = CRYPTO_TASK_TYPES.get(str(asset.get("task_type", "PAY")), CRYPTO_TASK_TYPES["PAY"])

    transaction_change = _clamp(
        (macro_growth * 1.2)
        + (rate_pressure * 0.25)
        + (event_result * 0.08)
        + (network_activity * 0.010)
        + (demand_change * 0.65)
        + ((utilization - 0.75) * 0.08),
        -0.14,
        0.16,
    )
    wallet_change = _clamp(
        (transaction_change * 0.55) + (macro_growth * 0.45) + (event_result * 0.04) + ((adoption - 1.0) * 0.05),
        -0.10,
        0.12,
    )
    fee_change = _clamp((transaction_change * 0.85) + (network_fees * 0.008) + ((utilization - 0.8) * 0.12), -0.18, 0.22)
    issuance = 0.0 if task.fixed_supply else 0.006
    burn_rate = _clamp(0.002 + max(transaction_change, 0.0) * 0.10 + max(fee_change, 0.0) * 0.04, 0.0, 0.018)
    inflation_rate = _clamp(issuance - burn_rate, -0.012, 0.014)

    asset["previous_transactions"] = previous_transactions
    asset["previous_chain_fees"] = previous_fees
    asset["previous_average_fee"] = previous_average_fee
    asset["previous_circulating_supply"] = previous_supply
    asset["previous_active_wallets"] = previous_wallets
    asset["transactions"] = max(1.0, previous_transactions * (1.0 + transaction_change))
    asset["chain_fees"] = max(1.0, previous_fees * (1.0 + fee_change))
    asset["gebuehren"] = asset["chain_fees"]
    asset["average_fee"] = asset["chain_fees"] / max(1.0, asset["transactions"])
    asset["average_fee_change"] = (asset["average_fee"] / previous_average_fee - 1.0) if previous_average_fee else 0.0
    asset["circulating_supply"] = previous_supply if task.fixed_supply else max(1.0, previous_supply * (1.0 + inflation_rate))
    asset["active_wallets"] = max(1.0, previous_wallets * (1.0 + wallet_change))
    asset["transaction_change"] = transaction_change
    asset["fee_change"] = fee_change
    asset["inflation_rate"] = inflation_rate
    asset["circulating_supply_change"] = 0.0 if task.fixed_supply else ((asset["circulating_supply"] / previous_supply - 1.0) if previous_supply else 0.0)
    asset["wallet_change"] = wallet_change
    _update_task_metrics(asset)
    _update_task_metric_changes(asset)


def crypto_price_signal(asset: dict) -> float:
    ensure_crypto_fundamentals(asset)
    transaction_change = float(asset.get("transaction_change", 0.0))
    fee_change = float(asset.get("fee_change", 0.0))
    inflation_rate = float(asset.get("inflation_rate", 0.0))
    wallet_change = float(asset.get("wallet_change", 0.0))
    demand_change = float(asset.get("demand_change", 0.0))
    share = float(asset.get("market_share", 0.0))
    utilization = float(asset.get("network_utilization", 0.7))
    return (
        (transaction_change * 0.70)
        + (fee_change * 0.45)
        + (wallet_change * 0.55)
        + (demand_change * 0.80)
        + ((utilization - 0.75) * 0.08)
        + (share * 0.25)
        - (inflation_rate * 1.2)
    )


def _new_crypto_asset(ticker: str, task_code: str, index_hint: int) -> dict:
    task = CRYPTO_TASK_TYPES[task_code]
    price = random.uniform(12.0, 180.0)
    supply = random.uniform(5_000_000.0, 50_000_000.0) if task.fixed_supply else random.uniform(18_000_000.0, 220_000_000.0)
    capacity = random.uniform(360.0, 920.0)
    asset = {
        "name": _crypto_name(task_code),
        "kurs": round(price, 2),
        "historie": [(round(price, 2), "01.01.1990", "")],
        "aenderung": 0.0,
        "task_type": task_code,
        "service_code": CRYPTO_SERVICE_CODES[task_code],
        "branche": task.label,
        "kategorie": task.label,
        "typ": "Crypto Chain",
        "circulating_supply": supply,
        "network_capacity": capacity,
        "demand": task.base_demand / START_CHAINS_PER_TASK,
        "market_share": 1.0 / START_CHAINS_PER_TASK,
        "network_utilization": 0.7,
        "adoption_score": 1.0,
        "netzwerk_aktivitaet": 0.0,
        "netzwerk_fees": 0.0,
        "transactions": random.uniform(35_000.0, 260_000.0),
        "chain_fees": random.uniform(8_000.0, 95_000.0),
        "active_wallets": random.uniform(18_000.0, 160_000.0),
        "market_cap": price * supply,
        "long_interest": price * supply * 0.035,
        "short_interest": price * supply * 0.030,
        "open_interest": price * supply * 0.065,
        "open_interest_history": [],
    }
    ensure_crypto_fundamentals(asset)
    return asset


def _crypto_name(task_code: str) -> str:
    parts = NAME_PARTS[task_code]
    return f"{random.choice(parts['prefix'])}{random.choice(parts['core'])} {random.choice(parts['suffix'])}"


def _unique_ticker(existing: dict) -> str:
    for _attempt in range(500):
        ticker = "".join(random.choice(string.ascii_uppercase) for _ in range(random.choice([3, 4, 5])))
        if ticker not in existing:
            return ticker
    return f"C{len(existing) + 1:04d}"


def _task_counts(assets: dict) -> dict[str, int]:
    counts = {code: 0 for code in CRYPTO_TASK_TYPES}
    for asset in assets.values():
        code = str(asset.get("task_type", "PAY"))
        if code in counts:
            counts[code] += 1
    return counts


def _crypto_demand_by_task(daten: ModuleType) -> dict[str, float]:
    macro_values = list(getattr(daten, "makro", {}).values())
    avg_inflation = _avg(macro.get("inflation", 0.01) for macro in macro_values)
    avg_growth = _avg(macro.get("bip_prozent", 0.01) for macro in macro_values)
    liquidity = float(getattr(daten, "gli_index", 15420.0)) / 15420.0
    sector_caps: dict[str, float] = {}
    for asset in getattr(daten, "aktien", {}).values():
        sector = str(asset.get("branche", ""))
        sector_caps[sector] = sector_caps.get(sector, 0.0) + float(asset.get("market_cap", 0.0))
    total_cap = max(1.0, sum(sector_caps.values()))

    def sector_share(*sectors: str) -> float:
        return sum(sector_caps.get(sector, 0.0) for sector in sectors) / total_cap

    return {
        "STORE": CRYPTO_TASK_TYPES["STORE"].base_demand * (1.0 + avg_inflation * 12.0 + max(0.0, liquidity - 1.0) * 0.9),
        "PAY": CRYPTO_TASK_TYPES["PAY"].base_demand * (1.0 + avg_growth * 8.0 + sector_share("Einzelhandel", "Finanzen") * 4.0),
        "DATA": CRYPTO_TASK_TYPES["DATA"].base_demand * (1.0 + sector_share("Technologie", "Telekommunikation") * 5.5),
        "GRID": CRYPTO_TASK_TYPES["GRID"].base_demand * (1.0 + sector_share("Stromerzeuger", "Maschinenbau", "Technologie") * 4.5),
    }


def _crypto_task_opportunity(daten: ModuleType, task_code: str) -> float:
    chains = [asset for asset in getattr(daten, "kryptos", {}).values() if asset.get("task_type") == task_code]
    demand = _crypto_demand_by_task(daten).get(task_code, CRYPTO_TASK_TYPES[task_code].base_demand)
    capacity = sum(float(asset.get("network_capacity", 1.0)) for asset in chains) or 1.0
    return demand / capacity


def _chain_quality(asset: dict) -> float:
    wallets = max(1.0, float(asset.get("active_wallets", 1.0)))
    fees = max(1.0, float(asset.get("chain_fees", 1.0)))
    activity = float(asset.get("netzwerk_aktivitaet", 0.0))
    return _clamp(0.85 + (wallets / 500_000.0) + (fees / 1_500_000.0) + activity * 0.025, 0.35, 1.8)


def _ensure_task_metrics(asset: dict) -> None:
    task_code = str(asset.get("task_type", "PAY"))
    capacity = max(1.0, float(asset.get("network_capacity", 500.0)))
    demand = max(1.0, float(asset.get("demand", 1.0)))
    utilization = max(0.05, float(asset.get("network_utilization", 0.7)))
    if task_code == "STORE":
        asset.setdefault("hashrate", capacity * 0.9)
    elif task_code == "PAY":
        asset.setdefault("tps", capacity * 2.4)
        asset.setdefault("confirmation_time", max(0.2, 4.0 / utilization))
        asset.setdefault("merchant_adoption", 0.15)
    elif task_code == "DATA":
        asset.setdefault("storage_capacity", capacity)
        asset.setdefault("used_storage", demand)
        asset.setdefault("price_per_tb", max(0.1, 5.0 * utilization))
    elif task_code == "GRID":
        asset.setdefault("energy_volume", demand)
        asset.setdefault("smart_meter_nodes", 25_000.0)
        asset.setdefault("grid_capacity", capacity)
        asset.setdefault("energy_transactions", 40_000.0)
        asset.setdefault("settlement_speed", max(0.2, 6.0 / utilization))
    for key in TASK_METRIC_KEYS.get(task_code, []):
        value = float(asset.get(key, 0.0))
        asset.setdefault(f"previous_{key}", value)
        asset.setdefault(f"{key}_change", 0.0)


def _update_task_metrics(asset: dict) -> None:
    task_code = str(asset.get("task_type", "PAY"))
    demand = max(1.0, float(asset.get("demand", 1.0)))
    utilization = max(0.05, float(asset.get("network_utilization", 0.7)))
    if task_code == "STORE":
        asset["hashrate"] = max(1.0, float(asset.get("hashrate", 100.0)) * (1.0 + asset.get("wallet_change", 0.0) * 0.35))
    elif task_code == "PAY":
        asset["tps"] = max(1.0, float(asset.get("network_capacity", 1000.0)) * 2.4)
        asset["confirmation_time"] = max(0.2, 4.0 / utilization)
        asset["merchant_adoption"] = max(0.01, min(1.0, float(asset.get("merchant_adoption", 0.15)) + asset.get("demand_change", 0.0) * 0.08))
    elif task_code == "DATA":
        asset["storage_capacity"] = max(1.0, float(asset.get("network_capacity", 100.0)))
        asset["used_storage"] = max(1.0, demand)
        asset["price_per_tb"] = max(0.1, 5.0 * utilization)
    elif task_code == "GRID":
        asset["energy_volume"] = max(1.0, demand)
        asset["smart_meter_nodes"] = max(1.0, float(asset.get("smart_meter_nodes", 25_000.0)) * (1.0 + asset.get("wallet_change", 0.0)))
        asset["grid_capacity"] = max(1.0, float(asset.get("network_capacity", 100.0)))
        asset["energy_transactions"] = max(1.0, float(asset.get("transactions", 1.0)) * 0.6)
        asset["settlement_speed"] = max(0.2, 6.0 / utilization)


def _capture_task_metric_previous(asset: dict) -> None:
    task_code = str(asset.get("task_type", "PAY"))
    for key in TASK_METRIC_KEYS.get(task_code, []):
        asset[f"previous_{key}"] = float(asset.get(key, 0.0))


def _update_task_metric_changes(asset: dict) -> None:
    task_code = str(asset.get("task_type", "PAY"))
    for key in TASK_METRIC_KEYS.get(task_code, []):
        previous = float(asset.get(f"previous_{key}", 0.0))
        current = float(asset.get(key, 0.0))
        asset[f"{key}_change"] = (current / previous - 1.0) if previous else 0.0


def _avg(values) -> float:
    items = [float(value) for value in values]
    return sum(items) / len(items) if items else 0.0


def _clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))
