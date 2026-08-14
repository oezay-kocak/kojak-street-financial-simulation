# Demo Scenarios

This document describes short review scenarios for Kojak Street Financial
Simulation. They are designed for recruiters, finance teams and technical
interviewers who want to understand the project without reading the full code
base first.

## How To Run

Start the Qt application:

```powershell
python kojakstreet_qt_launcher.py
```

Recommended demo setup:

- start with a fresh simulation state
- advance the simulation by several months before opening the analytical views
- use the market, macro, supply-chain, bond and portfolio views as the core tour
- keep the focus on model interaction, not on investment advice

## Scenario 1: Macro Shock Transmission

Purpose: Show how macro variables influence markets and credit.

Suggested flow:

1. Open the Macro view.
2. Compare countries by growth, inflation, rates, unemployment and rating.
3. Advance the simulation several months.
4. Reopen the Macro view and inspect changed rates, inflation and credit risk.
5. Switch to Markets and compare equity, index, bond and derivative reactions.

What this demonstrates:

- macro data is stateful and evolves over time
- interest rates and inflation affect asset pricing
- ratings and default probabilities feed credit products
- the model creates a visible economic narrative instead of isolated prices

Good screenshot:

- Macro dashboard with the country table and KPI row visible.

## Scenario 2: Supply-Chain Bottleneck

Purpose: Show the real-economy layer behind company and commodity movements.

Suggested flow:

1. Open the Supply Chain view.
2. Filter for imbalances or sort by Balance / Pressure.
3. Select a product with visible shortage or pressure.
4. Open the detail view and inspect produced, demanded and country production
   share.
5. Switch to a related company in Markets and inspect drivers.

What this demonstrates:

- commodities and processed products are linked through recipes
- products track supply, demand, inventories, shortages and pressure
- bottlenecks can influence company fundamentals and market prices
- the simulation connects macro markets with production logic

Good screenshot:

- Supply Chain table sorted by imbalance or a product detail page with charts.

## Scenario 3: Credit And Bond Market

Purpose: Show the fixed-income and credit-risk layer.

Suggested flow:

1. Open the Bond Market view.
2. Filter by government or corporate bonds.
3. Inspect yield, duration, rating, price and default risk.
4. Advance the simulation over multiple months or years.
5. Observe how new issues appear and older issues are archived after the active
   market reaches the configured cap.

What this demonstrates:

- the bond market has yield, rating, duration and default-risk mechanics
- portfolio bonds can be marked to market
- the active market is performance-bounded for long simulations
- old off-the-run issues can be archived instead of keeping an unlimited table

Good screenshot:

- Bond Market view showing several maturities, ratings and yields.

## Scenario 4: Derivatives And Hedging Instruments

Purpose: Show that derivatives have specific simulation use cases.

Suggested flow:

1. Open Markets.
2. Filter asset type to Derivatives.
3. Compare commodity futures, FX forwards, options, yield futures, inflation
   swaps and CDS.
4. Open a CDS detail page and read the use case plus pricing note.
5. Open a future or forward and compare its trading mode with spot-settled
   options/CDS.

What this demonstrates:

- derivatives are not only decorative assets
- each instrument has a model role and a UI-visible use case
- CDS are displayed as scaled protection-value indicators
- futures-style products are separated from spot-settled instruments

Good screenshot:

- Markets table filtered to Derivatives plus a CDS detail view showing the
  pricing note.

## Scenario 5: Portfolio And Risk View

Purpose: Show the broker-terminal side of the project.

Suggested flow:

1. Open Portfolio.
2. Review cash, invested amount, unrealized PnL, gross exposure and leveraged
   exposure.
3. Open the Bonds tab to show bond position details.
4. Open the Currencies tab to show FX balances and conversion mechanics.
5. If positions exist, select one and inspect the chart/detail panel.

What this demonstrates:

- the project includes accounting, portfolio state and position analytics
- spot, bond, currency and futures-style exposures share one portfolio layer
- the UI is built as a financial terminal, not only as a price table

Good screenshot:

- Portfolio overview with KPI row and positions/bonds table visible.

## Scenario 6: Long-Run Stability

Purpose: Show that the model can run for years without collapsing.

Suggested flow:

1. Run a multi-year simulation from the runtime or application controls.
2. Verify that prices remain finite and positive.
3. Verify that macro values remain in plausible ranges.
4. Verify that supply-chain metrics stay bounded.
5. Verify that the active bond market is capped and older issues are archived.

Latest local verification:

```text
3 simulation years completed
active bond market capped at 2,400
1,116 older bond issues archived
CDS pricing notes present
226 automated tests passed
```

What this demonstrates:

- the project is not only a static UI mockup
- the state can evolve over long periods
- performance and data growth are monitored
- known simplifications are documented transparently
