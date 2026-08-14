# Model Assumptions

Kojak Street is a fictional financial-market simulation. The model is designed
for explainability, learning value and interactive behavior rather than real
market calibration.

## Scope

The simulation includes:

- macroeconomic country data
- currencies and FX strength
- raw commodities and processed products
- company fundamentals
- equities, indices, funds and ETFs
- bonds and credit ratings
- derivatives and hedging instruments
- portfolio accounting and risk mechanics

## Market Data

All market data is generated inside the simulation. Countries, companies,
asset prices, histories and events are fictional or synthetic. Prices are
driven by rules, stochastic shocks and internal state variables.

The simulation does not ingest live exchange data and does not attempt to
forecast real markets.

## Price Formation

Asset prices are influenced by simplified drivers:

- macro growth, rates, inflation and liquidity
- market psychology and momentum
- supply-chain shortages, inventories and price pressure
- company fundamentals such as revenue growth and free cash flow
- fund flows and positioning
- event shocks
- credit quality and default probability

The goal is plausible interaction, not empirical calibration.

## Supply Chains

The supply-chain model links raw commodities to processed products and company
output. Products use weighted input recipes where available. Supply, demand,
inventories, shortages and regional trade flows are updated through the
simulation.

Supply-chain pressure can affect:

- product prices
- company input availability
- capacity utilization
- production scores
- company fundamentals
- derivative prices for futures, freight and input-cost spreads

## Financial Products

Derivatives are modeled as simplified instruments with clear simulation use
cases:

- commodity futures track future raw-material or processed-product exposure
- commodity spread futures track relative scarcity between linked markets
- freight futures track transport and shipping pressure
- input-cost spreads track finished-product margin pressure
- FX forwards track currency and rate-differential exposure
- inflation swaps track realized/expected inflation versus a fixed rate
- yield futures track rates and yield-curve exposure
- options use intrinsic value plus simplified time value
- CDS contracts track sovereign or corporate default risk

Options and CDS can be held as spot-settled derivative positions. Futures,
forwards, swaps and spreads are traded through long/short futures-style
positions.

## Bonds And Credit

Bond pricing uses simplified yield, duration, spread and rating logic. Credit
ratings map to default probabilities. Portfolio bonds are marked to market
where market prices are available.

The active bond market is capped and older off-the-run issues can be moved into
a compact archive. This keeps long simulations responsive while preserving the
visible term structure, current issuers and base benchmark bonds.

CDS contracts are linked to default risk and can settle when sovereign or
corporate default conditions are triggered.

CDS prices are displayed as scaled protection-value indicators. They are based
on spread, default risk and notional exposure, not on an equity-style share
price. Large displayed CDS values therefore mean materially higher simulated
credit-protection value, not a conventional stock-like market quote.

## Funds And ETFs

Funds and ETFs are baskets of equities, commodities, crypto assets, bonds or
indices. They do not charge expense ratios in the simulation. Their purpose is
to model allocation, exposure and fund-flow pressure on underlying assets.

## Company Hedging

Companies can receive a simplified hedge profile based on their sector,
input mix and macro risk. Hedging can reduce the impact of input-cost,
interest-rate, inflation, credit and event pressure on company fundamentals.

This is a compact approximation of corporate risk management rather than a
full treasury or derivative accounting model.

## Portfolio Mechanics

The portfolio supports:

- spot positions
- FX balances
- bonds
- loans
- futures-style long/short positions
- option and CDS settlement
- liquidation checks
- realized PnL history

The simulation currently excludes real transaction fees, taxes and slippage.

## Limitations

The model should not be interpreted as:

- a real pricing engine
- an investment recommendation system
- a calibrated risk model
- a regulatory model
- a backtesting system for real strategies

It is a financial engineering showcase focused on architecture, interaction
between model components, explainability and LLM-assisted development.
