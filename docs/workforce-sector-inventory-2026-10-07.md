# Sektorinventur zum Workforce-Audit – 7. Oktober 2026

> Dated engineering evidence for the revision described below. Test counts,
> model versions and measurements are historical unless explicitly carried
> into the [current verification record](portfolio-closeout-2026-10-08.md).
> Raw cache artifacts remain local; source links identify modules, not the
> original audit line numbers.


Automatisch aus den unveränderten Produktionskonstanten gelesen. Keine Workforce-Anteile festgelegt.

| Kanonischer Name / Display | Stabile ID | Firmen je Land beim Start | P/S | FCF-Grundmarge | Grunddividende | Kapazitäts-Wachstumsmodifier |
|---|---|---|---|---|---|---|
| Automobil | AUTOMOTIVE | 4 | 0.8 | 4.5 % | 1.5 % | 1.14 |
| Chemie | CHEMICALS | 4 | 1.2 | 7.5 % | 2.2 % | 1 |
| Öl und Gas | OIL_GAS | 4 | 1.1 | 16 % | 4 % | 1 |
| Stromerzeuger | POWER_UTILITIES | 4 | 1.5 | 8 % | 3.5 % | 0.72 |
| Maschinenbau | INDUSTRIAL_MACHINERY | 4 | 1.4 | 9 % | 1.7 % | 1 |
| Telekommunikation | TELECOM | 4 | 1.8 | 10 % | 4.5 % | 0.72 |
| Einzelhandel | RETAIL | 4 | 0.9 | 5.5 % | 1.8 % | 1 |
| Konsumgüter | CONSUMER_GOODS | 4 | 2.4 | 12 % | 2.5 % | 0.92 |
| Finanzen | FINANCIALS | 4 | 2.2 | 24 % | 3 % | 0.92 |
| Edelmetallförderer | PRECIOUS_METALS_MINING | 4 | 1.6 | 14 % | 1.8 % | 1 |
| Gesundheit | HEALTHCARE | 4 | 4 | 18 % | 1.2 % | 0.72 |
| Technologie | TECHNOLOGY | 4 | 5 | 20 % | 0.6 % | 1.14 |
| Immobilien | REAL_ESTATE | 4 | 6 | 28 % | 3.5 % | 1 |
| Transport und Logistik | TRANSPORT_LOGISTICS | 4 | 0.9 | 6 % | 1.2 % | 1 |
| Verteidigung | DEFENSE | 4 | 2 | 11 % | 2 % | 1.14 |
| Landwirtschaft | AGRICULTURE | 4 | 1 | 6.5 % | 2 % | 0.72 |

Die Modifier gelten nur im bestehenden Engpass-Expansionszweig. Bei normaler Auslastung ist Growth .005, bei Auslastung unter .50 −.006; Kapazität wird täglich .75/.25 zur Umsatzbasis zurückgeführt. Kein Beschäftigtenbestand. Produkt-Angebotskorridore haben eigene essential/industrial/cyclical/strategic/discretionary-Profile; eine Branche kann Produkte aus mehreren Profilen enthalten.

## Outputs und sektorale Inputs

Inputgewichte sind bestehende wirtschaftliche Nachfragegewichte, keine Mitarbeiteranteile. Produktrezepte in `PROCESSED_PRODUCTS`/`INPUT_RECIPES` kommen zusätzlich hinzu. Ein Unternehmen nutzt seinen Teilmix dieser sektoralen Outputliste; nicht jede Firma produziert alles.

### Automobil (AUTOMOTIVE)

Outputs: VEH, PARTS, TIRE, BAT.

Sektorale Inputs: STL=0.22; ALU=0.16; PLAS=0.12; GLS=0.07; ECOMP=0.15; TIRE=0.1; BAT=0.12; ELC=0.06.

### Chemie (CHEMICALS)

Outputs: CHEM, PLAS, FERT, IGAS, SRUB, API, COAT, CLEAN, PEST.

Sektorale Inputs: CL=0.16; TTF=0.14; SAL=0.08; HEAT=0.16; ELC=0.12; PACK=0.04.

### Öl und Gas (OIL_GAS)

Outputs: CL, TTF, FUEL.

Sektorale Inputs: MINER=0.22; STL=0.13; MACH=0.1; ELC=0.1; FUEL=0.08.

### Stromerzeuger (POWER_UTILITIES)

Outputs: ELC, HEAT, SOLP, H2.

Sektorale Inputs: CL=0.07; TTF=0.15; NEWC=0.1; UX=0.05; PWRP=0.14; CUW=0.06; SOLP=0.07; WIND=0.06; GRID=0.08; BESS=0.05.

### Maschinenbau (INDUSTRIAL_MACHINERY)

Outputs: STL, ALU, CUW, ALLOY, MACH, MINER, AGM, CONM, FACT, PWRP, LOGE, WIND, GRID, TRAIN, AIRPL, SHIPB.

Sektorale Inputs: STL=0.2; ALU=0.1; CUW=0.09; ECOMP=0.12; ELC=0.07; MACH=0.08; RND=0.04; IP=0.03.

### Telekommunikation (TELECOM)

Outputs: MOB, FIX, DATA, COMMS.

Sektorale Inputs: COMMS=0.26; CUW=0.12; GLS=0.08; ELC=0.18; DATA=0.1.

### Einzelhandel (RETAIL)

Outputs: FREIGHT, PAY, PACK, WARE.

Sektorale Inputs: FREIGHT=0.14; PACK=0.18; PAY=0.1; ELC=0.08; DATA=0.06; WARE=0.16; WASTE=0.04.

### Konsumgüter (CONSUMER_GOODS)

Outputs: FOOD, DRINK, CLOTH, HOME, LUX, CARE.

Sektorale Inputs: FOOD=0.16; DRINK=0.09; TEXT=0.07; PLAS=0.1; PACK=0.14; ELC=0.07; WASTE=0.04; WARE=0.06.

### Finanzen (FINANCIALS)

Outputs: LOAN, INS, ASSETM, PAY, EXCH, CUST, RISK, RATING.

Sektorale Inputs: CHW=0.14; DATA=0.13; PAY=0.1; CLOUD=0.14; ELC=0.05; EXCH=0.08; CUST=0.07; RISK=0.08; RATING=0.05; CYBR=0.08.

### Edelmetallförderer (PRECIOUS_METALS_MINING)

Outputs: IRO, HG, BAU, NIK, LIT, COB, SIL, PHO, SAL, LST, STN, XAU, XAG, XPT, XPD, RHD, NDM, CER, EUP, SCD.

Sektorale Inputs: MINER=0.22; MACH=0.12; FUEL=0.12; ELC=0.1; STL=0.08.

### Gesundheit (HEALTHCARE)

Outputs: API, MEDS, MEDT, HLTH, EDU.

Sektorale Inputs: MEDS=0.2; MEDT=0.16; CLEAN=0.07; IGAS=0.07; ELC=0.08; PACK=0.05; RND=0.06; IP=0.04; AIRF=0.04.

### Technologie (TECHNOLOGY)

Outputs: SEMI, ECOMP, CHW, SDIG, CELEC, BHW, SOFT, CLOUD, PLAT, BESS, RND, IP, CYBR.

Sektorale Inputs: SEMI=0.18; ECOMP=0.16; CHW=0.1; CLOUD=0.09; ELC=0.12; ALU=0.05; RND=0.08; IP=0.06; CYBR=0.08; BESS=0.04.

### Immobilien (REAL_ESTATE)

Outputs: CEM, BLD, GLS, REAL.

Sektorale Inputs: BLD=0.24; STL=0.14; CEM=0.16; GLS=0.1; WOOD=0.08; CONM=0.08.

### Transport und Logistik (TRANSPORT_LOGISTICS)

Outputs: FREIGHT, LOGE, WASTE, SHIP, AIRF, RAIL, PORT.

Sektorale Inputs: FUEL=0.16; VEH=0.08; TIRE=0.06; LOGE=0.12; ELC=0.05; SHIP=0.1; AIRF=0.07; RAIL=0.08; PORT=0.08; WARE=0.05.

### Verteidigung (DEFENSE)

Outputs: ARMS, ALLOY, SEMI, ECOMP, AIRPL, SHIPB.

Sektorale Inputs: ARMS=0.16; STL=0.1; ALLOY=0.12; SEMI=0.09; ECOMP=0.1; FUEL=0.08; CYBR=0.06; RND=0.06; IP=0.04; AIRPL=0.04; SHIPB=0.03.

### Landwirtschaft (AGRICULTURE)

Outputs: ZW, ZRC, COF, COC, SUG, WOOD, COT, RUB, MEAT, FISH, FERT, FOOD, WATR, SEED, FEED.

Sektorale Inputs: FERT=0.15; AGM=0.12; FUEL=0.1; PACK=0.05; ELC=0.06; WATR=0.14; SEED=0.1; PEST=0.08; FEED=0.09.

## Länderfokus und Bonusmechanik

Alle Sektoren verwenden dieselbe Funktion `_country_sector_bonus`: Fokuswert (sonst 1) × clamp(1.05−Defaultwahrscheinlichkeit×.75,.72,1.08). Regionale Angebote werden danach auf globales Angebot normalisiert. Der Fokus ist kein zusätzlicher globaler Produktivitätsroot.

Anfangsfokuswerte bei regulärer Länderreihenfolge und gemeinsamem `used_focuses`-Set:

| Land | Vier Branchen mit Fokuswert |
|---|---|
| Ameron | Technologie ×1.26; Finanzen ×1.3; Verteidigung ×1.34; Öl und Gas ×1.26 |
| Albionia | Finanzen ×1.18; Verteidigung ×1.22; Immobilien ×1.34; Transport und Logistik ×1.26 |
| Ardonia | Maschinenbau ×1.26; Automobil ×1.3; Chemie ×1.34; Stromerzeuger ×1.26 |
| Valoria | Gesundheit ×1.26; Konsumgüter ×1.3; Chemie ×1.26; Technologie ×1.18 |
| Romara | Automobil ×1.18; Konsumgüter ×1.22; Immobilien ×1.26; Transport und Logistik ×1.18 |
| Soleria | Landwirtschaft ×1.26; Einzelhandel ×1.3; Stromerzeuger ×1.26; Konsumgüter ×1.18 |
| Nordmark | Öl und Gas ×1.18; Stromerzeuger ×1.22; Transport und Logistik ×1.26; Edelmetallförderer ×1.26 |
| Sarmatia | Maschinenbau ×1.18; Landwirtschaft ×1.22; Transport und Logistik ×1.26; Chemie ×1.18 |
| Danubria | Landwirtschaft ×1.18; Automobil ×1.22; Maschinenbau ×1.26; Gesundheit ×1.18 |
| Carpathia | Öl und Gas ×1.18; Edelmetallförderer ×1.22; Verteidigung ×1.26; Maschinenbau ×1.18 |
| Anatria | Transport und Logistik ×1.18; Einzelhandel ×1.22; Automobil ×1.26; Verteidigung ×1.18 |
| Azaria | Öl und Gas ×1.18; Finanzen ×1.22; Stromerzeuger ×1.26; Immobilien ×1.18 |
| Indara | Technologie ×1.18; Gesundheit ×1.22; Einzelhandel ×1.26; Landwirtschaft ×1.18 |
| Hanxia | Maschinenbau ×1.18; Technologie ×1.22; Konsumgüter ×1.26; Edelmetallförderer ×1.18 |
| Pacifica | Technologie ×1.18; Maschinenbau ×1.22; Automobil ×1.26; Telekommunikation ×1.26 |
| Koryo | Technologie ×1.18; Telekommunikation ×1.22; Automobil ×1.26; Verteidigung ×1.18 |
| Amazonia | Landwirtschaft ×1.18; Edelmetallförderer ×1.22; Konsumgüter ×1.26; Stromerzeuger ×1.18 |
| Canadia | Edelmetallförderer ×1.18; Transport und Logistik ×1.22; Finanzen ×1.26; Landwirtschaft ×1.18 |
| Auroria | Edelmetallförderer ×1.18; Landwirtschaft ×1.22; Stromerzeuger ×1.26; Transport und Logistik ×1.18 |
| Savanna | Edelmetallförderer ×1.18; Landwirtschaft ×1.22; Finanzen ×1.26; Stromerzeuger ×1.18 |

Die Initialisierung verwendet 1.18 für bevorzugte Branchen, +.08 solange eine Branche noch nicht im gemeinsamen Fokusset vorkam, sowie einen positionsabhängigen Zuschlag (Position modulo 3)×.04. Das ist keine zeitliche Rotation. Die bestehende zeitliche Veränderung erfolgt nach mindestens fünf Kalenderjahren: stärkste Kapazitätsbranche +.08 bis 1.38, schwächster anderer Fokus −.05 bis 1.02; Produktfokus wird neu abgeleitet. Initialer Produktfokus: erste drei Outputs je Fokusbranche ×1.10. Heterogeneous verwendet für die Firmenplatzierung statische bevorzugte Mitgliedschaft, keine laufenden Bonuswerte.

## Weitere Sektormodifikatoren

Monatliches `sector_energy_factor`: Transport/Automobil/Chemie/Maschinenbau/Landwirtschaft max(.70,1−(Energiepreisrelation−1)×.25); Öl/Gas min(1.40,1+(Relation−1)×.30); Technologie zusätzlich max(.75,1−(Metallschock−1)×.20). Stromerzeuger erhalten keinen gesonderten Energie-Windfall. Der regionale Faktor (.78–1.18) wird hinzugenommen; Unternehmens-Hedge schwächt Sektorexposition ab.

Tägliches `stock_energy_price_signal` ist ein separater Kurskanal: Energie-Return auf ±.08 begrenzt, Transport/Automobil/Maschinenbau/Landwirtschaft −.30×Return, Öl/Gas +.18×Return, sonst 0. Das ist keine Arbeitsproduktivität. Kein Workforce-Effekt sollte zugleich in beide Kanäle eingebaut werden.

## Quellen

- [core/companies.py:20](../src/kojakstreet/core/companies.py)
- [core/label_codes.py:8](../src/kojakstreet/core/label_codes.py)
- [core/fundamentals.py:7](../src/kojakstreet/core/fundamentals.py)
- [core/production_chains.py:315](../src/kojakstreet/core/production_chains.py)
- [core/production_chains.py:334](../src/kojakstreet/core/production_chains.py)
- [core/production_chains.py:1403](../src/kojakstreet/core/production_chains.py)
- [core/production_chains.py:1430](../src/kojakstreet/core/production_chains.py)
- [core/production_chains.py:1473](../src/kojakstreet/core/production_chains.py)
- [core/production_chains.py:1636](../src/kojakstreet/core/production_chains.py)
- [core/company_lifecycle.py:284](../src/kojakstreet/core/company_lifecycle.py)
- [core/market_calculations.py:358](../src/kojakstreet/core/market_calculations.py)
