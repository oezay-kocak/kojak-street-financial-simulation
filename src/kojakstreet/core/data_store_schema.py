"""Schema management for the DuckDB-backed economic data store."""

from __future__ import annotations

from typing import Any

CREATE_TABLE_STATEMENTS = (
    """
    CREATE TABLE IF NOT EXISTS history_metadata (
        key VARCHAR PRIMARY KEY,
        value VARCHAR
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS history_aggregate (
        source_table VARCHAR,
        entity VARCHAR,
        field VARCHAR,
        semantic_type VARCHAR,
        resolution VARCHAR,
        bucket_start DATE,
        bucket_end DATE,
        open_value DOUBLE,
        high_value DOUBLE,
        low_value DOUBLE,
        close_value DOUBLE,
        mean_value DOUBLE,
        sum_value DOUBLE,
        observation_count BIGINT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS structural_event (
        event_id VARCHAR PRIMARY KEY,
        date DATE,
        event_type VARCHAR,
        scope VARCHAR,
        entity VARCHAR,
        summary VARCHAR,
        severity VARCHAR,
        metadata_json VARCHAR
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS asset_daily (
        date DATE,
        ticker VARCHAR,
        asset_type VARCHAR,
        name VARCHAR,
        region VARCHAR,
        sector VARCHAR,
        price DOUBLE,
        change_pct DOUBLE,
        market_cap DOUBLE,
        revenue DOUBLE,
        free_cash_flow DOUBLE,
        rating VARCHAR
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS product_daily (
        date DATE,
        code VARCHAR,
        item_type VARCHAR,
        name VARCHAR,
        category VARCHAR,
        produced DOUBLE,
        demanded DOUBLE,
        inventories DOUBLE,
        shortage DOUBLE,
        pressure DOUBLE,
        price DOUBLE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS country_daily (
        date DATE,
        region VARCHAR,
        population DOUBLE,
        gdp DOUBLE,
        growth DOUBLE,
        rate DOUBLE,
        inflation DOUBLE,
        unemployment DOUBLE,
        rating VARCHAR,
        trade_balance DOUBLE,
        import_dependency DOUBLE,
        export_strength DOUBLE,
        main_sector VARCHAR,
        main_bottleneck VARCHAR,
        debt_to_gdp DOUBLE,
        credit_growth DOUBLE,
        expected_growth DOUBLE,
        expected_inflation DOUBLE,
        expected_rate DOUBLE,
        macro_surprise DOUBLE,
        balance_sheet DOUBLE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS company_daily (
        date DATE,
        ticker VARCHAR,
        name VARCHAR,
        region VARCHAR,
        sector VARCHAR,
        rating VARCHAR,
        price DOUBLE,
        market_cap DOUBLE,
        revenue DOUBLE,
        free_cash_flow DOUBLE,
        production_capacity DOUBLE,
        capacity_utilization DOUBLE,
        production_score DOUBLE,
        input_availability DOUBLE,
        supply_chain_shortage DOUBLE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS company_output_daily (
        date DATE,
        ticker VARCHAR,
        role VARCHAR,
        code VARCHAR,
        share DOUBLE,
        quantity DOUBLE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS country_trade_daily (
        date DATE,
        region VARCHAR,
        code VARCHAR,
        produced DOUBLE,
        demanded DOUBLE,
        exports DOUBLE,
        imports DOUBLE,
        net DOUBLE,
        shortage DOUBLE,
        pressure DOUBLE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS fund_allocation_daily (
        date DATE,
        fund_ticker VARCHAR,
        ticker VARCHAR,
        asset_type VARCHAR,
        weight DOUBLE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS global_macro_daily (
        date DATE,
        metric VARCHAR,
        value DOUBLE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS forex_daily (
        date DATE,
        pair VARCHAR,
        base VARCHAR,
        quote VARCHAR,
        rate DOUBLE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS bond_daily (
        date DATE,
        symbol VARCHAR,
        issuer VARCHAR,
        region VARCHAR,
        bond_type VARCHAR,
        price DOUBLE,
        yield DOUBLE,
        coupon DOUBLE,
        maturity_years DOUBLE,
        rating VARCHAR,
        issuer_type VARCHAR,
        category VARCHAR,
        default_risk DOUBLE,
        liquidity DOUBLE,
        maturity_date VARCHAR,
        change_pct DOUBLE,
        duration DOUBLE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS portfolio_daily (
        date DATE,
        cash DOUBLE,
        net_worth DOUBLE,
        positions INTEGER,
        futures INTEGER
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS news_events (
        date DATE,
        body VARCHAR,
        category VARCHAR
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS event_log (
        date DATE,
        event_type VARCHAR,
        scope VARCHAR,
        entity VARCHAR,
        summary VARCHAR,
        severity VARCHAR
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS phase_metric_daily (
        date DATE,
        phase VARCHAR,
        duration_ms DOUBLE
    )
    """,
)

CURRENT_TABLE_SOURCES = {
    "asset_current": "asset_daily",
    "product_current": "product_daily",
    "company_current": "company_daily",
    "company_output_current": "company_output_daily",
    "country_trade_current": "country_trade_daily",
    "fund_allocation_current": "fund_allocation_daily",
    "country_current": "country_daily",
    "global_macro_current": "global_macro_daily",
    "forex_current": "forex_daily",
    "bond_current": "bond_daily",
    "portfolio_current": "portfolio_daily",
    "news_current": "news_events",
    "event_current": "event_log",
    "phase_metric_current": "phase_metric_daily",
}

MIGRATION_COLUMNS = {
    "bond_daily": (
        ("issuer_type", "VARCHAR"),
        ("category", "VARCHAR"),
        ("default_risk", "DOUBLE"),
        ("liquidity", "DOUBLE"),
        ("maturity_date", "VARCHAR"),
        ("change_pct", "DOUBLE"),
        ("duration", "DOUBLE"),
    ),
    "bond_current": (
        ("issuer_type", "VARCHAR"),
        ("category", "VARCHAR"),
        ("default_risk", "DOUBLE"),
        ("liquidity", "DOUBLE"),
        ("maturity_date", "VARCHAR"),
        ("change_pct", "DOUBLE"),
        ("duration", "DOUBLE"),
    ),
    "country_daily": (
        ("debt_to_gdp", "DOUBLE"),
        ("credit_growth", "DOUBLE"),
        ("expected_growth", "DOUBLE"),
        ("expected_inflation", "DOUBLE"),
        ("expected_rate", "DOUBLE"),
        ("macro_surprise", "DOUBLE"),
        ("balance_sheet", "DOUBLE"),
    ),
    "country_current": (
        ("debt_to_gdp", "DOUBLE"),
        ("credit_growth", "DOUBLE"),
        ("expected_growth", "DOUBLE"),
        ("expected_inflation", "DOUBLE"),
        ("expected_rate", "DOUBLE"),
        ("macro_surprise", "DOUBLE"),
        ("balance_sheet", "DOUBLE"),
    ),
}


def create_schema(connection: Any) -> None:
    for statement in CREATE_TABLE_STATEMENTS:
        connection.execute(statement)
    for current_table, source_table in CURRENT_TABLE_SOURCES.items():
        connection.execute(f"CREATE TABLE IF NOT EXISTS {current_table} AS SELECT * FROM {source_table} WHERE FALSE")
    migrate_schema(connection)


def migrate_schema(connection: Any) -> None:
    for table, columns in MIGRATION_COLUMNS.items():
        for column, column_type in columns:
            connection.execute(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {column} {column_type}")
