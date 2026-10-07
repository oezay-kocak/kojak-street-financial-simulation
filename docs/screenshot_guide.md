# Screenshot guide

Current portfolio images live in `docs/assets/` and are linked from the
[README](../README.md). They show one real Heterogeneous World, seed 1729, after
75 daily steps on 17 March 1990. `tools/portfolio_captures.py` reproduces them
through the actual Qt shell; its before/after digest checks that navigation does
not mutate world, player or RNG state.

| Image | Purpose |
| --- | --- |
| [Markets](assets/markets.png) | Main terminal, quote table, price history and trade controls |
| [Company detail](assets/company-detail.png) | Fundamentals, drivers and credit information |
| [Country](assets/country.png) | Actual observed macro history |
| [Society and Politics](assets/society-politics.png) | Demography, workforce, stability and initial mandates |
| [Supply chain](assets/supply-chain.png) | Production, demand, inventories and pressure |
| [Portfolio](assets/portfolio.png) | Real holding, valuation, PnL and exposure |

Use complete, readable windows with real simulated history. Label fixtures and
initial allocations honestly. Avoid personal paths, unrelated windows and raw
test-terminal images. Test evidence belongs in text with its exact conditions.

The older interface images in `screenshots/` are retained as historical assets;
they are not the current product tour or proof of current test counts. The old
test-terminal image was removed from publication because it exposed a local
path and an obsolete test count.
