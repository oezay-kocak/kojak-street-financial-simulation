"""Universal-unit production chains from raw commodities to final demand."""

from __future__ import annotations

from collections import defaultdict
from functools import lru_cache
from types import ModuleType

from kojakstreet.core.shocks import shock_multiplier

from kojakstreet.core.cryptos import CRYPTO_SERVICE_CODES
from kojakstreet.core.production_indexes import company_runtimes, main_country_sectors
from kojakstreet.core.ratings import DEFAULT_RATING, default_probability

COMMODITY_GROUPS = {
    "Energietr\u00e4ger": {
        "Erd\u00f6l": "CL",
        "Erdgas": "TTF",
        "Kohle": "NEWC",
        "Uran": "UX",
    },
    "Industriemetalle und Mineralische Rohstoffe": {
        "Eisenerz": "IRO",
        "Kupfer": "HG",
        "Bauxit": "BAU",
        "Nickel": "NIK",
        "Lithium": "LIT",
        "Kobalt": "COB",
        "Silizium": "SIL",
        "Phosphat": "PHO",
        "Salz": "SAL",
        "Kalkstein": "LST",
        "Stein und Kies": "STN",
    },
    "Edel- und Spezialmetalle": {
        "Gold": "XAU",
        "Silber": "XAG",
        "Platin": "XPT",
        "Palladium": "XPD",
        "Rhodium": "RHD",
    },
    "Seltene Erden": {
        "Neodym": "NDM",
        "Cer": "CER",
        "Europium": "EUP",
        "Scandium": "SCD",
    },
    "Landwirtschaftliche Prim\u00e4rg\u00fcter": {
        "Getreide": "ZW",
        "\u00d6lsaaten und Pflanzen\u00f6le": "ZRC",
        "Kaffee": "COF",
        "Kakao": "COC",
        "Zucker": "SUG",
        "Holz": "WOOD",
        "Baumwolle": "COT",
        "Naturkautschuk": "RUB",
    },
    "Tierische G\u00fcter": {
        "Fleisch": "MEAT",
        "Fisch": "FISH",
    },
}

COMMODITY_USES = {
    "CL": ["Raffinierte Treibstoffe", "Chemie", "Kunststoffe", "Transport und Logistik"],
    "TTF": ["Elektrizit\u00e4t", "Industriew\u00e4rme", "D\u00fcnger", "Chemie"],
    "NEWC": ["Elektrizit\u00e4t", "Stahl", "Industrie"],
    "UX": ["Elektrizit\u00e4t"],
    "IRO": ["Stahl"],
    "HG": ["Kupferprodukte", "Elektronik", "Automobil", "Maschinenbau"],
    "BAU": ["Aluminium"],
    "NIK": ["Edelstahl", "Batterien", "Speziallegierungen"],
    "LIT": ["Batterien"],
    "COB": ["Batterien", "Speziallegierungen"],
    "SIL": ["Halbleiter", "Glas", "Elektronikkomponenten"],
    "PHO": ["Landwirtschaft", "Chemie"],
    "SAL": ["Chemie", "Konsumg\u00fcter"],
    "LST": ["Zement", "Stahl", "Transport und Logistik"],
    "STN": ["Baustoffe", "Immobilien", "Transport und Logistik"],
    "XAU": ["Elektronikkomponenten", "Luxusg\u00fcter"],
    "XAG": ["Elektronikkomponenten", "Luxusg\u00fcter"],
    "XPT": ["Chemie", "Automobil"],
    "XPD": ["Automobil", "Chemie"],
    "RHD": ["Automobil", "Speziallegierungen"],
    "NDM": ["Elektronikkomponenten"],
    "CER": ["Elektronikkomponenten"],
    "EUP": ["Elektronikkomponenten"],
    "SCD": ["Speziallegierungen", "Verteidigung"],
    "ZW": ["Verarbeitete Lebensmittel", "Getr\u00e4nke"],
    "ZRC": ["Verarbeitete Lebensmittel", "K\u00f6rperpflegeprodukte"],
    "COF": ["Getr\u00e4nke"],
    "COC": ["Getr\u00e4nke"],
    "SUG": ["Getr\u00e4nke", "Chemie", "Konsumg\u00fcter"],
    "WOOD": ["Verpackung", "Immobilien", "Konsumg\u00fcter"],
    "COT": ["Textilien", "Konsumg\u00fcter"],
    "RUB": ["Reifen", "Automobil", "Verteidigung"],
    "MEAT": ["Verarbeitete Lebensmittel"],
    "FISH": ["Verarbeitete Lebensmittel"],
}

PROCESSED_PRODUCTS = {
    "ELC": {
        "name": "Elektrizit\u00e4t",
        "category": "Energieprodukte",
        "inputs": ["CL", "TTF", "NEWC", "UX"],
        "users": ["alle Branchen", "Haushalte"],
        "consumer_weight": 0.70,
    },
    "FUEL": {
        "name": "Raffinierte Treibstoffe",
        "category": "Energieprodukte",
        "inputs": ["CL", "ELC", "Chemische Grundstoffe"],
        "users": ["Transport und Logistik", "Landwirtschaft", "Verteidigung"],
        "consumer_weight": 0.10,
    },
    "HEAT": {
        "name": "Industriew\u00e4rme",
        "category": "Energieprodukte",
        "inputs": ["CL", "TTF", "NEWC", "ELC"],
        "users": ["Chemie", "Metallverarbeitung", "Baustoffe"],
    },
    "STL": {"name": "Stahl", "category": "Metall- und Werkstoffprodukte", "inputs": ["IRO", "NEWC", "ELC", "LST"], "users": ["Automobil", "Maschinenbau", "Immobilien", "Transport und Logistik", "Verteidigung"]},
    "ALU": {"name": "Aluminium", "category": "Metall- und Werkstoffprodukte", "inputs": ["BAU", "ELC"], "users": ["Automobil", "Technologie", "Transport und Logistik", "Verteidigung"]},
    "CUW": {"name": "Kupferprodukte", "category": "Metall- und Werkstoffprodukte", "inputs": ["HG", "ELC"], "users": ["Technologie", "Telekommunikation", "Maschinenbau"]},
    "ALLOY": {"name": "Speziallegierungen", "category": "Metall- und Werkstoffprodukte", "inputs": ["NIK", "COB", "SCD", "STL", "ELC"], "users": ["Verteidigung", "Maschinenbau", "Transport und Logistik"]},
    "GLS": {"name": "Glas", "category": "Metall- und Werkstoffprodukte", "inputs": ["SIL", "LST", "ELC"], "users": ["Immobilien", "Technologie", "Konsumg\u00fcter"]},
    "CEM": {"name": "Zement", "category": "Metall- und Werkstoffprodukte", "inputs": ["LST", "ELC"], "users": ["Immobilien"]},
    "BLD": {"name": "Baustoffe", "category": "Metall- und Werkstoffprodukte", "inputs": ["CEM", "STL", "WOOD", "GLS", "STN"], "users": ["Immobilien"]},
    "PACK": {"name": "Verpackung", "category": "Metall- und Werkstoffprodukte", "inputs": ["WOOD", "Chemische Grundstoffe", "ELC"], "users": ["Einzelhandel", "Konsumg\u00fcter", "Gesundheit"], "consumer_weight": 0.05},
    "CHEM": {"name": "Chemische Grundstoffe", "category": "Chemieprodukte", "inputs": ["CL", "TTF", "SAL", "ELC"], "users": ["produzierende Branchen"]},
    "PLAS": {"name": "Kunststoffe", "category": "Chemieprodukte", "inputs": ["CL", "TTF", "CHEM"], "users": ["Automobil", "Konsumg\u00fcter", "Technologie", "Gesundheit"]},
    "FERT": {"name": "D\u00fcnger", "category": "Chemieprodukte", "inputs": ["TTF", "PHO", "CHEM"], "users": ["Landwirtschaft"]},
    "IGAS": {"name": "Industriegase", "category": "Chemieprodukte", "inputs": ["ELC", "CHEM"], "users": ["Gesundheit", "Technologie", "Maschinenbau"]},
    "SRUB": {"name": "Synthetischer Kautschuk", "category": "Chemieprodukte", "inputs": ["CL", "CHEM"], "users": ["Automobil", "Maschinenbau"]},
    "API": {"name": "Pharmawirkstoffe", "category": "Chemieprodukte", "inputs": ["CHEM", "ELC", "CHW", "SDIG"], "users": ["Gesundheit"]},
    "COAT": {"name": "Farben und Beschichtungen", "category": "Chemieprodukte", "inputs": ["CHEM", "CL", "LST"], "users": ["Automobil", "Immobilien", "Maschinenbau"]},
    "CLEAN": {"name": "Reinigungsprodukte", "category": "Chemieprodukte", "inputs": ["CHEM", "PLAS", "PACK"], "users": ["Konsumg\u00fcter", "Gesundheit"], "consumer_weight": 0.25},
    "SEMI": {"name": "Halbleiter", "category": "Elektronik- und Technologieprodukte", "inputs": ["SIL", "HG", "XAU", "NDM", "CER", "EUP", "CHEM", "ELC"], "users": ["Technologie", "Automobil", "Telekommunikation", "Verteidigung"]},
    "ECOMP": {"name": "Elektronikkomponenten", "category": "Elektronik- und Technologieprodukte", "inputs": ["SEMI", "CUW", "XAG", "NDM", "CER", "EUP"], "users": ["Automobil", "Technologie", "Maschinenbau", "Verteidigung"]},
    "BAT": {"name": "Batterien", "category": "Elektronik- und Technologieprodukte", "inputs": ["LIT", "NIK", "COB", "HG", "ELC"], "users": ["Automobil", "Technologie", "Energie"]},
    "COMMS": {"name": "Kommunikationstechnik", "category": "Elektronik- und Technologieprodukte", "inputs": ["ECOMP", "HG", "GLS", "PLAS"], "users": ["Telekommunikation"]},
    "CHW": {"name": "Computerhardware", "category": "Elektronik- und Technologieprodukte", "inputs": ["SEMI", "ECOMP", "ALU", "PLAS"], "users": ["Technologie", "Finanzen"]},
    "SDIG": {"name": "Software und digitale Dienste", "category": "Elektronik- und Technologieprodukte", "inputs": ["ELC", "CHW"], "users": ["alle Branchen"], "consumer_weight": 0.25},
    "MACH": {"name": "Industriemaschinen", "category": "Maschinen und Investitionsg\u00fcter", "inputs": ["STL", "ALU", "CUW", "ECOMP", "ELC"], "users": ["alle produzierenden Branchen"]},
    "MINER": {"name": "F\u00f6rderanlagen", "category": "Maschinen und Investitionsg\u00fcter", "inputs": ["STL", "MACH", "ECOMP"], "users": ["\u00d6l und Gas", "Rohstofff\u00f6rderer"]},
    "AGM": {"name": "Landwirtschaftsmaschinen", "category": "Maschinen und Investitionsg\u00fcter", "inputs": ["STL", "FUEL", "ECOMP"], "users": ["Landwirtschaft"]},
    "CONM": {"name": "Baumaschinen", "category": "Maschinen und Investitionsg\u00fcter", "inputs": ["STL", "ALU", "ECOMP", "FUEL"], "users": ["Immobilien"]},
    "FACT": {"name": "Fabrikausr\u00fcstung", "category": "Maschinen und Investitionsg\u00fcter", "inputs": ["MACH", "ECOMP", "STL"], "users": ["Automobil", "Chemie", "Konsumg\u00fcter", "Technologie"]},
    "PWRP": {"name": "Energieanlagen", "category": "Maschinen und Investitionsg\u00fcter", "inputs": ["STL", "HG", "ECOMP", "ALLOY"], "users": ["Stromerzeuger"]},
    "LOGE": {"name": "Logistikausr\u00fcstung", "category": "Maschinen und Investitionsg\u00fcter", "inputs": ["STL", "Fahrzeuge", "ECOMP"], "users": ["Transport und Logistik", "Einzelhandel"]},
    "VEH": {"name": "Fahrzeuge", "category": "Endprodukte und Dienstleistungen", "inputs": ["STL", "ALU", "PLAS", "GLS", "ECOMP", "Reifen", "BAT", "ELC"], "users": ["Haushalte", "Transport und Logistik"], "consumer_weight": 0.16},
    "PARTS": {"name": "Fahrzeugteile", "category": "Endprodukte und Dienstleistungen", "inputs": ["STL", "ALU", "CUW", "PLAS", "ECOMP"], "users": ["Automobil"]},
    "TIRE": {"name": "Reifen", "category": "Endprodukte und Dienstleistungen", "inputs": ["RUB", "SRUB", "CHEM", "STL"], "users": ["Automobil", "Transport und Logistik"], "consumer_weight": 0.08},
    "FOOD": {"name": "Verarbeitete Lebensmittel", "category": "Konsumg\u00fcter", "inputs": ["ZW", "ZRC", "MEAT", "FISH", "SUG", "PACK", "ELC"], "users": ["Haushalte"], "consumer_weight": 1.20},
    "DRINK": {"name": "Getr\u00e4nke", "category": "Konsumg\u00fcter", "inputs": ["SUG", "COF", "COC", "ZW", "PACK"], "users": ["Haushalte"], "consumer_weight": 0.55},
    "TEXT": {"name": "Textilien", "category": "Konsumg\u00fcter", "inputs": ["COT", "CHEM", "ELC"], "users": ["Bekleidung"]},
    "CLOTH": {"name": "Bekleidung", "category": "Konsumg\u00fcter", "inputs": ["TEXT", "PLAS", "ELC"], "users": ["Haushalte"], "consumer_weight": 0.34},
    "HOME": {"name": "Haushaltswaren", "category": "Konsumg\u00fcter", "inputs": ["PLAS", "STL", "ALU", "GLS", "ECOMP"], "users": ["Haushalte"], "consumer_weight": 0.25},
    "LUX": {"name": "Luxusg\u00fcter", "category": "Konsumg\u00fcter", "inputs": ["XAU", "XAG", "XPT", "TEXT", "GLS"], "users": ["Haushalte"], "consumer_weight": 0.06},
    "CARE": {"name": "K\u00f6rperpflegeprodukte", "category": "Konsumg\u00fcter", "inputs": ["CHEM", "ZRC", "PLAS", "PACK"], "users": ["Haushalte"], "consumer_weight": 0.22},
    "MEDS": {"name": "Medikamente", "category": "Gesundheit", "inputs": ["API", "CHEM", "PACK", "ELC"], "users": ["Haushalte", "Gesundheit"], "consumer_weight": 0.26},
    "MEDT": {"name": "Medizintechnik", "category": "Gesundheit", "inputs": ["ECOMP", "PLAS", "STL", "ALU", "GLS"], "users": ["Gesundheit"]},
    "HLTH": {"name": "Gesundheitsdienstleistungen", "category": "Gesundheit", "inputs": ["MEDS", "MEDT", "ELC"], "users": ["Haushalte"], "consumer_weight": 0.42},
    "CELEC": {"name": "Unterhaltungselektronik", "category": "Technologie", "inputs": ["SEMI", "ECOMP", "BAT", "ALU", "PLAS"], "users": ["Haushalte"], "consumer_weight": 0.18},
    "BHW": {"name": "Unternehmenshardware", "category": "Technologie", "inputs": ["SEMI", "ECOMP", "STL", "ALU"], "users": ["Technologie", "Finanzen"]},
    "SOFT": {"name": "Softwareprodukte", "category": "Technologie", "inputs": ["CHW", "ELC"], "users": ["alle Branchen"], "consumer_weight": 0.18},
    "CLOUD": {"name": "Cloud- und Rechenzentrumsdienste", "category": "Technologie", "inputs": ["CHW", "ELC"], "users": ["alle Branchen"]},
    "PLAT": {"name": "Digitale Plattformen", "category": "Technologie", "inputs": ["SOFT", "ELC"], "users": ["Haushalte", "Einzelhandel"], "consumer_weight": 0.16},
    "REAL": {"name": "Wohngeb\u00e4ude, Gewerbeimmobilien, Vermietungsleistungen", "category": "Immobilien", "inputs": ["BLD", "STL", "CEM", "GLS", "WOOD"], "users": ["Haushalte", "alle Branchen"], "consumer_weight": 0.50},
    "FREIGHT": {"name": "Frachttransport", "category": "Transport und Logistik", "inputs": ["FUEL", "VEH"], "users": ["alle Branchen"]},
    "MOB": {"name": "Mobilfunkdienste", "category": "Telekommunikation", "inputs": ["COMMS", "ELC"], "users": ["Haushalte"], "consumer_weight": 0.28},
    "FIX": {"name": "Festnetzdienste", "category": "Telekommunikation", "inputs": ["CUW", "COMMS", "ELC"], "users": ["Haushalte", "alle Branchen"], "consumer_weight": 0.18},
    "DATA": {"name": "Datendienste", "category": "Telekommunikation", "inputs": ["ELC", "CHW"], "users": ["alle Branchen", "Haushalte"], "consumer_weight": 0.20},
    "LOAN": {"name": "Kredite", "category": "Finanzen", "inputs": [], "users": ["Haushalte", "alle Branchen"], "consumer_weight": 0.18},
    "INS": {"name": "Versicherungsleistungen", "category": "Finanzen", "inputs": [], "users": ["Haushalte", "alle Branchen"], "consumer_weight": 0.12},
    "ASSETM": {"name": "Verm\u00f6gensverwaltung", "category": "Finanzen", "inputs": ["CHW"], "users": ["Haushalte"], "consumer_weight": 0.07},
    "PAY": {"name": "Zahlungsdienste", "category": "Finanzen", "inputs": ["CHW", "COMMS"], "users": ["Haushalte", "Einzelhandel"], "consumer_weight": 0.14},
    "EXCH": {"name": "Exchange and Clearing Services", "category": "Financial Services", "inputs": ["CHW", "CLOUD", "DATA", "CYBR"], "users": ["Finanzen"]},
    "CUST": {"name": "Custody Services", "category": "Financial Services", "inputs": ["CHW", "CLOUD", "DATA", "CYBR"], "users": ["Finanzen"]},
    "RISK": {"name": "Risk and Market Data Services", "category": "Financial Services", "inputs": ["DATA", "CLOUD", "SOFT", "CYBR"], "users": ["Finanzen", "Versicherungsleistungen", "alle Branchen"]},
    "RATING": {"name": "Rating and Credit Data Services", "category": "Financial Services", "inputs": ["RISK", "DATA", "SOFT", "CLOUD"], "users": ["Finanzen"]},
    "ARMS": {"name": "Kleinwaffen", "category": "Verteidigung", "inputs": ["STL", "ALLOY", "CHEM", "ELC", "SEMI", "NDM", "CER", "EUP", "ECOMP", "FUEL"], "users": ["Verteidigung"]},
    "WATR": {"name": "Water", "category": "Utilities", "inputs": ["ELC"], "users": ["Landwirtschaft", "Chemie", "Gesundheit", "Haushalte", "Stromerzeuger", "Technologie"], "consumer_weight": 0.30},
    "WASTE": {"name": "Waste and Recycling Services", "category": "Utilities", "inputs": ["FREIGHT", "ELC", "MACH"], "users": ["alle Branchen", "Haushalte", "Chemie"], "consumer_weight": 0.06},
    "SOLP": {"name": "Solar Modules", "category": "Energy Infrastructure", "inputs": ["SIL", "GLS", "ALU", "CUW", "SEMI", "ELC"], "users": ["Stromerzeuger", "Immobilien"]},
    "WIND": {"name": "Wind Turbines", "category": "Energy Infrastructure", "inputs": ["STL", "ALU", "CUW", "ECOMP", "ALLOY", "ELC"], "users": ["Stromerzeuger"]},
    "GRID": {"name": "Power Grid Equipment", "category": "Energy Infrastructure", "inputs": ["CUW", "ALU", "STL", "ECOMP", "SEMI", "ELC"], "users": ["Stromerzeuger", "Immobilien", "alle Branchen"]},
    "H2": {"name": "Hydrogen", "category": "Energy Infrastructure", "inputs": ["ELC", "WATR", "PWRP"], "users": ["Chemie", "Transport und Logistik", "Stromerzeuger", "Maschinenbau"]},
    "BESS": {"name": "Battery Storage Systems", "category": "Energy Infrastructure", "inputs": ["BAT", "ECOMP", "ALU", "CUW", "ELC"], "users": ["Stromerzeuger", "Technologie", "Immobilien"]},
    "TRAIN": {"name": "Trains and Rail Vehicles", "category": "Industrial Machinery and Capital Goods", "inputs": ["STL", "ALU", "CUW", "ECOMP", "GRID", "BAT", "ELC"], "users": ["Transport und Logistik"]},
    "AIRPL": {"name": "Aircraft", "category": "Industrial Machinery and Capital Goods", "inputs": ["ALU", "ALLOY", "ECOMP", "SEMI", "MACH", "FUEL", "ELC"], "users": ["Transport und Logistik", "Verteidigung"]},
    "SHIPB": {"name": "Ships", "category": "Industrial Machinery and Capital Goods", "inputs": ["STL", "ALLOY", "MACH", "ECOMP", "FUEL", "COAT"], "users": ["Transport und Logistik", "Verteidigung"]},
    "SHIP": {"name": "Ocean Freight", "category": "Transport and Logistics", "inputs": ["FUEL", "SHIPB", "LOGE", "PORT"], "users": ["alle Branchen", "Einzelhandel", "Landwirtschaft"]},
    "AIRF": {"name": "Air Freight", "category": "Transport and Logistics", "inputs": ["FUEL", "AIRPL", "LOGE"], "users": ["Technologie", "Gesundheit", "Einzelhandel", "Konsumg\u00fcter"]},
    "RAIL": {"name": "Rail Logistics", "category": "Transport and Logistics", "inputs": ["TRAIN", "ELC", "LOGE", "GRID"], "users": ["alle Branchen", "Landwirtschaft"]},
    "PORT": {"name": "Port and Terminal Services", "category": "Transport and Logistics", "inputs": ["CONM", "LOGE", "ELC", "DATA"], "users": ["Transport und Logistik", "alle Branchen"]},
    "WARE": {"name": "Warehouse and Fulfillment Services", "category": "Transport and Logistics", "inputs": ["REAL", "LOGE", "DATA", "ELC"], "users": ["Einzelhandel", "Konsumg\u00fcter", "Gesundheit", "Technologie"]},
    "RND": {"name": "Research and Development", "category": "Knowledge Services", "inputs": ["EDU", "CLOUD", "SOFT", "CHW", "DATA"], "users": ["Technologie", "Gesundheit", "Verteidigung", "Maschinenbau", "Chemie"]},
    "EDU": {"name": "Education Services", "category": "Knowledge Services", "inputs": ["REAL", "DATA", "SOFT"], "users": ["alle Branchen", "Haushalte"], "consumer_weight": 0.20},
    "IP": {"name": "Patents and Licenses", "category": "Knowledge Services", "inputs": ["RND", "DATA", "SOFT"], "users": ["Technologie", "Gesundheit", "Verteidigung", "Maschinenbau", "Chemie"]},
    "CYBR": {"name": "Cybersecurity Services", "category": "Technology", "inputs": ["SOFT", "CLOUD", "DATA", "CHW"], "users": ["Finanzen", "Technologie", "Verteidigung", "alle Branchen", "Crypto Network Services"], "consumer_weight": 0.04},
    "SEED": {"name": "Seeds", "category": "Agricultural Inputs", "inputs": ["RND", "WATR", "CHEM"], "users": ["Landwirtschaft"]},
    "PEST": {"name": "Crop Protection Products", "category": "Agricultural Inputs", "inputs": ["CHEM", "WATR", "PACK"], "users": ["Landwirtschaft"]},
    "FEED": {"name": "Animal Feed", "category": "Agricultural Inputs", "inputs": ["ZW", "ZRC", "FISH", "PACK"], "users": ["Landwirtschaft"]},
    "CRSTORE": {"name": "Digital Store-of-Value Network Services", "category": "Crypto Network Services", "inputs": ["ELC", "ECOMP", "SDIG", "CHW"], "users": ["Haushalte", "Finanzen"], "consumer_weight": 0.08},
    "CRPAY": {"name": "Crypto Payment Rail Services", "category": "Crypto Network Services", "inputs": ["ELC", "ECOMP", "SDIG", "CHW"], "users": ["Einzelhandel", "Finanzen", "alle Branchen"], "consumer_weight": 0.03},
    "CRDATA": {"name": "Decentralized Storage Network Services", "category": "Crypto Network Services", "inputs": ["ELC", "ECOMP", "SDIG", "CHW"], "users": ["Technologie", "alle Branchen"]},
    "CRGRID": {"name": "Energy Trading Network Services", "category": "Crypto Network Services", "inputs": ["ELC", "ECOMP", "SDIG", "CHW"], "users": ["Stromerzeuger", "Maschinenbau", "Technologie"]},
}

PRODUCT_NAME_TO_CODE = {data["name"]: code for code, data in PROCESSED_PRODUCTS.items()}
PRODUCT_NAME_TO_CODE.update({
    "Strom": "ELC",
    "Energie": "ELC",
    "Treibstoffe": "FUEL",
    "Chemikalien": "CHEM",
    "Chemie": "CHEM",
    "Elektronik": "ECOMP",
    "Maschinen": "MACH",
    "Fahrzeuge": "VEH",
    "Reifen": "TIRE",
})

INPUT_RECIPES = {
    "ELC": {"CL": 0.26, "TTF": 0.34, "NEWC": 0.22, "UX": 0.18},
    "FUEL": {"CL": 1.72, "ELC": 0.18, "CHEM": 0.10},
    "HEAT": {"TTF": 0.42, "NEWC": 0.28, "CL": 0.18, "ELC": 0.12},
    "STL": {"IRO": 1.70, "NEWC": 0.82, "ELC": 0.22, "LST": 0.18},
    "ALU": {"BAU": 1.88, "ELC": 0.72},
    "CUW": {"HG": 1.24, "ELC": 0.28},
    "ALLOY": {"NIK": 0.62, "COB": 0.28, "SCD": 0.08, "STL": 0.46, "ELC": 0.18},
    "GLS": {"SIL": 0.72, "LST": 0.22, "ELC": 0.18},
    "CEM": {"LST": 1.26, "ELC": 0.20},
    "BLD": {"CEM": 0.44, "STL": 0.20, "WOOD": 0.18, "GLS": 0.10, "STN": 0.48},
    "CHEM": {"CL": 0.42, "TTF": 0.34, "SAL": 0.18, "ELC": 0.16},
    "PLAS": {"CL": 0.54, "TTF": 0.20, "CHEM": 0.46},
    "FERT": {"TTF": 0.42, "PHO": 0.38, "CHEM": 0.22},
    "SEMI": {"SIL": 0.34, "HG": 0.08, "XAU": 0.04, "NDM": 0.05, "CER": 0.05, "EUP": 0.03, "CHEM": 0.34, "ELC": 0.48},
    "ECOMP": {"SEMI": 0.42, "CUW": 0.30, "XAG": 0.07, "NDM": 0.05, "CER": 0.04, "EUP": 0.03},
    "BAT": {"LIT": 0.42, "NIK": 0.34, "COB": 0.18, "HG": 0.10, "ELC": 0.16},
    "COMMS": {"ECOMP": 0.54, "HG": 0.18, "GLS": 0.12, "PLAS": 0.18},
    "CHW": {"SEMI": 0.46, "ECOMP": 0.38, "ALU": 0.22, "PLAS": 0.20},
    "SDIG": {"ELC": 0.34, "CHW": 0.28},
    "MACH": {"STL": 0.44, "ALU": 0.18, "CUW": 0.16, "ECOMP": 0.20, "ELC": 0.10},
    "MINER": {"STL": 0.46, "MACH": 0.34, "ECOMP": 0.12},
    "VEH": {"STL": 0.32, "ALU": 0.22, "PLAS": 0.16, "GLS": 0.09, "ECOMP": 0.15, "TIRE": 0.14, "BAT": 0.17, "XPD": 0.015, "RHD": 0.010, "ELC": 0.08},
    "PARTS": {"STL": 0.28, "ALU": 0.18, "CUW": 0.14, "PLAS": 0.18, "ECOMP": 0.16, "XPD": 0.010, "RHD": 0.006},
    "TIRE": {"RUB": 0.36, "SRUB": 0.28, "CHEM": 0.18, "STL": 0.10, "ELC": 0.04},
    "FOOD": {"ZW": 0.42, "ZRC": 0.24, "MEAT": 0.20, "FISH": 0.14, "SUG": 0.16, "PACK": 0.12, "ELC": 0.08},
    "DRINK": {"SUG": 0.28, "COF": 0.12, "COC": 0.10, "ZW": 0.10, "PACK": 0.16},
    "TEXT": {"COT": 0.44, "CHEM": 0.18, "ELC": 0.10, "WATR": 0.08},
    "CLOTH": {"TEXT": 0.46, "PLAS": 0.14, "PACK": 0.10, "ELC": 0.06},
    "HOME": {"PLAS": 0.24, "STL": 0.16, "ALU": 0.12, "GLS": 0.12, "ECOMP": 0.10, "PACK": 0.08},
    "LUX": {"XAU": 0.22, "XAG": 0.12, "XPT": 0.08, "TEXT": 0.18, "GLS": 0.12, "PACK": 0.06},
    "CARE": {"CHEM": 0.32, "ZRC": 0.16, "PLAS": 0.14, "PACK": 0.14, "WATR": 0.08},
    "PACK": {"WOOD": 0.30, "CHEM": 0.16, "PLAS": 0.18, "ELC": 0.08},
    "CLEAN": {"CHEM": 0.36, "PLAS": 0.16, "PACK": 0.12, "WATR": 0.16, "ELC": 0.04},
    "COAT": {"CHEM": 0.34, "CL": 0.12, "LST": 0.10, "PLAS": 0.12, "ELC": 0.06},
    "IGAS": {"ELC": 0.32, "CHEM": 0.28, "WATR": 0.10},
    "SRUB": {"CL": 0.48, "CHEM": 0.34, "ELC": 0.08},
    "API": {"CHEM": 0.58, "ELC": 0.16, "CHW": 0.09, "SDIG": 0.13},
    "MEDS": {"API": 0.46, "CHEM": 0.18, "PACK": 0.14, "ELC": 0.08},
    "MEDT": {"ECOMP": 0.28, "PLAS": 0.22, "STL": 0.14, "ALU": 0.12, "GLS": 0.08, "CYBR": 0.04},
    "HLTH": {"MEDS": 0.36, "MEDT": 0.22, "ELC": 0.12},
    "CARE": {"CHEM": 0.32, "ZRC": 0.16, "PLAS": 0.14, "PACK": 0.14, "WATR": 0.08},
    "CELEC": {"SEMI": 0.32, "ECOMP": 0.24, "BAT": 0.14, "ALU": 0.10, "PLAS": 0.08},
    "BHW": {"SEMI": 0.30, "ECOMP": 0.24, "STL": 0.12, "ALU": 0.12, "CYBR": 0.04},
    "SOFT": {"CHW": 0.26, "ELC": 0.18, "CLOUD": 0.16, "DATA": 0.14, "CYBR": 0.06},
    "CLOUD": {"CHW": 0.28, "ELC": 0.34, "DATA": 0.14, "CYBR": 0.08, "BESS": 0.04},
    "PLAT": {"SOFT": 0.34, "ELC": 0.16, "DATA": 0.18, "CLOUD": 0.20, "CYBR": 0.06},
    "REAL": {"BLD": 0.44, "STL": 0.16, "CEM": 0.20, "GLS": 0.10, "WOOD": 0.18},
    "FREIGHT": {"FUEL": 0.38, "VEH": 0.20},
    "WATR": {"ELC": 0.20},
    "WASTE": {"FREIGHT": 0.18, "ELC": 0.16, "MACH": 0.12},
    "SOLP": {"SIL": 0.30, "GLS": 0.22, "ALU": 0.16, "CUW": 0.10, "SEMI": 0.12, "ELC": 0.10},
    "WIND": {"STL": 0.34, "ALU": 0.14, "CUW": 0.12, "ECOMP": 0.13, "ALLOY": 0.16, "ELC": 0.08},
    "GRID": {"CUW": 0.32, "ALU": 0.16, "STL": 0.20, "ECOMP": 0.14, "SEMI": 0.08, "ELC": 0.08},
    "H2": {"ELC": 0.58, "WATR": 0.22, "PWRP": 0.12},
    "BESS": {"BAT": 0.44, "ECOMP": 0.18, "ALU": 0.14, "CUW": 0.10, "ELC": 0.08},
    "TRAIN": {"STL": 0.38, "ALU": 0.12, "CUW": 0.12, "ECOMP": 0.14, "GRID": 0.10, "BAT": 0.08, "ELC": 0.06},
    "AIRPL": {"ALU": 0.30, "ALLOY": 0.22, "ECOMP": 0.14, "SEMI": 0.08, "MACH": 0.14, "FUEL": 0.06, "ELC": 0.06},
    "AGM": {"STL": 0.30, "FUEL": 0.18, "ECOMP": 0.14, "MACH": 0.18, "TIRE": 0.08},
    "CONM": {"STL": 0.34, "ALU": 0.16, "ECOMP": 0.12, "FUEL": 0.12, "MACH": 0.14},
    "FACT": {"MACH": 0.38, "ECOMP": 0.20, "STL": 0.18, "ELC": 0.08, "CYBR": 0.04},
    "PWRP": {"STL": 0.26, "HG": 0.14, "ECOMP": 0.14, "ALLOY": 0.16, "SEMI": 0.08, "ELC": 0.08},
    "LOGE": {"STL": 0.24, "VEH": 0.20, "ECOMP": 0.16, "DATA": 0.10, "TIRE": 0.08},
    "SHIPB": {"STL": 0.42, "ALLOY": 0.16, "MACH": 0.16, "ECOMP": 0.08, "FUEL": 0.06, "COAT": 0.08},
    "SHIP": {"FUEL": 0.28, "SHIPB": 0.22, "LOGE": 0.16, "PORT": 0.18},
    "AIRF": {"FUEL": 0.36, "AIRPL": 0.24, "LOGE": 0.14},
    "RAIL": {"TRAIN": 0.28, "ELC": 0.24, "LOGE": 0.16, "GRID": 0.14},
    "PORT": {"CONM": 0.20, "LOGE": 0.24, "ELC": 0.12, "DATA": 0.10},
    "WARE": {"REAL": 0.26, "LOGE": 0.22, "DATA": 0.14, "ELC": 0.10},
    "EXCH": {"CHW": 0.20, "CLOUD": 0.28, "DATA": 0.22, "CYBR": 0.18},
    "CUST": {"CHW": 0.18, "CLOUD": 0.30, "DATA": 0.22, "CYBR": 0.18},
    "RISK": {"DATA": 0.28, "CLOUD": 0.22, "SOFT": 0.20, "CYBR": 0.16},
    "RATING": {"RISK": 0.38, "DATA": 0.22, "SOFT": 0.18, "CLOUD": 0.12},
    "PAY": {"CHW": 0.22, "COMMS": 0.20, "DATA": 0.18, "CLOUD": 0.16, "CYBR": 0.10},
    "ASSETM": {"CHW": 0.18, "DATA": 0.20, "RISK": 0.18, "CLOUD": 0.16, "CYBR": 0.08},
    "ARMS": {"STL": 0.22, "ALLOY": 0.18, "CHEM": 0.10, "ELC": 0.06, "SEMI": 0.08, "NDM": 0.04, "CER": 0.03, "EUP": 0.02, "ECOMP": 0.10, "FUEL": 0.05},
    "RND": {"EDU": 0.24, "CLOUD": 0.18, "SOFT": 0.20, "CHW": 0.12, "DATA": 0.16},
    "EDU": {"REAL": 0.22, "DATA": 0.16, "SOFT": 0.14},
    "IP": {"RND": 0.48, "DATA": 0.16, "SOFT": 0.14},
    "CYBR": {"SOFT": 0.30, "CLOUD": 0.22, "DATA": 0.20, "CHW": 0.12},
    "SEED": {"RND": 0.22, "WATR": 0.18, "CHEM": 0.20},
    "PEST": {"CHEM": 0.44, "WATR": 0.12, "PACK": 0.10},
    "FEED": {"ZW": 0.32, "ZRC": 0.22, "FISH": 0.10, "PACK": 0.08},
    "CRSTORE": {"ELC": 0.34, "ECOMP": 0.22, "SDIG": 0.20, "CHW": 0.16, "CYBR": 0.08},
    "CRPAY": {"ELC": 0.30, "ECOMP": 0.22, "SDIG": 0.18, "CHW": 0.14, "PAY": 0.10, "CYBR": 0.08},
    "CRDATA": {"ELC": 0.32, "ECOMP": 0.20, "SDIG": 0.18, "CHW": 0.18, "DATA": 0.10, "CYBR": 0.08},
    "CRGRID": {"ELC": 0.36, "ECOMP": 0.18, "SDIG": 0.16, "CHW": 0.12, "GRID": 0.12, "CYBR": 0.06},
    "LOAN": {},
    "INS": {},
}

SECTOR_OUTPUTS = {
    "\u00d6l und Gas": ["CL", "TTF", "FUEL"],
    "Edelmetallf\u00f6rderer": ["IRO", "HG", "BAU", "NIK", "LIT", "COB", "SIL", "PHO", "SAL", "LST", "STN", "XAU", "XAG", "XPT", "XPD", "RHD", "NDM", "CER", "EUP", "SCD"],
    "Landwirtschaft": ["ZW", "ZRC", "COF", "COC", "SUG", "WOOD", "COT", "RUB", "MEAT", "FISH", "FERT", "FOOD", "WATR", "SEED", "FEED"],
    "Stromerzeuger": ["ELC", "HEAT", "SOLP", "H2"],
    "Chemie": ["CHEM", "PLAS", "FERT", "IGAS", "SRUB", "API", "COAT", "CLEAN", "PEST"],
    "Automobil": ["VEH", "PARTS", "TIRE", "BAT"],
    "Maschinenbau": ["STL", "ALU", "CUW", "ALLOY", "MACH", "MINER", "AGM", "CONM", "FACT", "PWRP", "LOGE", "WIND", "GRID", "TRAIN", "AIRPL", "SHIPB"],
    "Telekommunikation": ["MOB", "FIX", "DATA", "COMMS"],
    "Einzelhandel": ["FREIGHT", "PAY", "PACK", "WARE"],
    "Konsumg\u00fcter": ["FOOD", "DRINK", "CLOTH", "HOME", "LUX", "CARE"],
    "Finanzen": ["LOAN", "INS", "ASSETM", "PAY", "EXCH", "CUST", "RISK", "RATING"],
    "Gesundheit": ["API", "MEDS", "MEDT", "HLTH", "EDU"],
    "Technologie": ["SEMI", "ECOMP", "CHW", "SDIG", "CELEC", "BHW", "SOFT", "CLOUD", "PLAT", "BESS", "RND", "IP", "CYBR"],
    "Immobilien": ["CEM", "BLD", "GLS", "REAL"],
    "Transport und Logistik": ["FREIGHT", "LOGE", "WASTE", "SHIP", "AIRF", "RAIL", "PORT"],
    "Verteidigung": ["ARMS", "ALLOY", "SEMI", "ECOMP", "AIRPL", "SHIPB"],
}

SECTOR_INPUT_WEIGHTS = {
    "Automobil": {"STL": 0.22, "ALU": 0.16, "PLAS": 0.12, "GLS": 0.07, "ECOMP": 0.15, "TIRE": 0.10, "BAT": 0.12, "ELC": 0.06},
    "Chemie": {"CL": 0.16, "TTF": 0.14, "SAL": 0.08, "HEAT": 0.16, "ELC": 0.12, "PACK": 0.04},
    "\u00d6l und Gas": {"MINER": 0.22, "STL": 0.13, "MACH": 0.10, "ELC": 0.10, "FUEL": 0.08},
    "Stromerzeuger": {"CL": 0.07, "TTF": 0.15, "NEWC": 0.10, "UX": 0.05, "PWRP": 0.14, "CUW": 0.06, "SOLP": 0.07, "WIND": 0.06, "GRID": 0.08, "BESS": 0.05},
    "Maschinenbau": {"STL": 0.20, "ALU": 0.10, "CUW": 0.09, "ECOMP": 0.12, "ELC": 0.07, "MACH": 0.08, "RND": 0.04, "IP": 0.03},
    "Telekommunikation": {"COMMS": 0.26, "CUW": 0.12, "GLS": 0.08, "ELC": 0.18, "DATA": 0.10},
    "Einzelhandel": {"FREIGHT": 0.14, "PACK": 0.18, "PAY": 0.10, "ELC": 0.08, "DATA": 0.06, "WARE": 0.16, "WASTE": 0.04},
    "Konsumg\u00fcter": {"FOOD": 0.16, "DRINK": 0.09, "TEXT": 0.07, "PLAS": 0.10, "PACK": 0.14, "ELC": 0.07, "WASTE": 0.04, "WARE": 0.06},
    "Finanzen": {"CHW": 0.14, "DATA": 0.13, "PAY": 0.10, "CLOUD": 0.14, "ELC": 0.05, "EXCH": 0.08, "CUST": 0.07, "RISK": 0.08, "RATING": 0.05, "CYBR": 0.08},
    "Edelmetallf\u00f6rderer": {"MINER": 0.22, "MACH": 0.12, "FUEL": 0.12, "ELC": 0.10, "STL": 0.08},
    "Gesundheit": {"MEDS": 0.20, "MEDT": 0.16, "CLEAN": 0.07, "IGAS": 0.07, "ELC": 0.08, "PACK": 0.05, "RND": 0.06, "IP": 0.04, "AIRF": 0.04},
    "Technologie": {"SEMI": 0.18, "ECOMP": 0.16, "CHW": 0.10, "CLOUD": 0.09, "ELC": 0.12, "ALU": 0.05, "RND": 0.08, "IP": 0.06, "CYBR": 0.08, "BESS": 0.04},
    "Immobilien": {"BLD": 0.24, "STL": 0.14, "CEM": 0.16, "GLS": 0.10, "WOOD": 0.08, "CONM": 0.08},
    "Transport und Logistik": {"FUEL": 0.16, "VEH": 0.08, "TIRE": 0.06, "LOGE": 0.12, "ELC": 0.05, "SHIP": 0.10, "AIRF": 0.07, "RAIL": 0.08, "PORT": 0.08, "WARE": 0.05},
    "Verteidigung": {"ARMS": 0.16, "STL": 0.10, "ALLOY": 0.12, "SEMI": 0.09, "ECOMP": 0.10, "FUEL": 0.08, "CYBR": 0.06, "RND": 0.06, "IP": 0.04, "AIRPL": 0.04, "SHIPB": 0.03},
    "Landwirtschaft": {"FERT": 0.15, "AGM": 0.12, "FUEL": 0.10, "PACK": 0.05, "ELC": 0.06, "WATR": 0.14, "SEED": 0.10, "PEST": 0.08, "FEED": 0.09},
}

CONSUMER_BASKET = {
    "FOOD": 1.20,
    "DRINK": 0.55,
    "ELC": 0.70,
    "REAL": 0.50,
    "HLTH": 0.42,
    "CLOTH": 0.34,
    "MOB": 0.28,
    "MEDS": 0.26,
    "HOME": 0.25,
    "CARE": 0.22,
    "DATA": 0.20,
    "LOAN": 0.18,
    "FIX": 0.18,
    "SOFT": 0.18,
    "CELEC": 0.18,
    "VEH": 0.16,
    "PLAT": 0.16,
    "PAY": 0.14,
    "INS": 0.12,
    "FUEL": 0.10,
    "TIRE": 0.08,
    "ASSETM": 0.07,
    "LUX": 0.06,
    "PACK": 0.05,
    "WATR": 0.30,
    "WASTE": 0.06,
    "EDU": 0.20,
    "CYBR": 0.04,
}

BALANCE_PROFILES = {
    "essential": {
        "supply_floor": 0.96,
        "supply_ceiling": 1.10,
        "pressure_multiplier": 0.72,
        "capacity_multiplier": 0.72,
    },
    "industrial": {
        "supply_floor": 0.90,
        "supply_ceiling": 1.18,
        "pressure_multiplier": 1.00,
        "capacity_multiplier": 1.00,
    },
    "cyclical": {
        "supply_floor": 0.84,
        "supply_ceiling": 1.24,
        "pressure_multiplier": 1.18,
        "capacity_multiplier": 1.14,
    },
    "strategic": {
        "supply_floor": 0.82,
        "supply_ceiling": 1.22,
        "pressure_multiplier": 1.25,
        "capacity_multiplier": 1.20,
    },
    "discretionary": {
        "supply_floor": 0.78,
        "supply_ceiling": 1.32,
        "pressure_multiplier": 1.12,
        "capacity_multiplier": 0.92,
    },
}

ESSENTIAL_OUTPUTS = {"ELC", "FUEL", "FOOD", "DRINK", "MEDS", "HLTH", "REAL", "MOB", "FIX", "DATA", "FERT", "WATR", "WASTE", "EDU", "FEED"}
CYCLICAL_OUTPUTS = {"SEMI", "ECOMP", "BAT", "CHW", "CELEC", "BHW", "SOFT", "CLOUD", "PLAT", "VEH", "PARTS", "MACH", "SOLP", "WIND", "BESS", "SHIP", "AIRF", "RAIL", "PORT", "WARE", "TRAIN", "AIRPL", "SHIPB"}
STRATEGIC_OUTPUTS = {"ARMS", "ALLOY", "MINER", "PWRP", "COMMS", "GRID", "H2", "EXCH", "CUST", "RISK", "RATING", "RND", "IP", "CYBR", "SEED", "PEST"}
DISCRETIONARY_OUTPUTS = {"LUX", "HOME", "CLOTH", "CARE", "ASSETM"}
ESSENTIAL_COMMODITIES = {"CL", "TTF", "NEWC", "UX", "ZW", "ZRC", "SUG", "MEAT", "FISH", "WOOD"}
STRATEGIC_COMMODITIES = {"LIT", "COB", "NIK", "SIL", "NDM", "CER", "EUP", "SCD", "XPT", "XPD", "RHD"}
DISCRETIONARY_COMMODITIES = {"XAU", "XAG", "COF", "COC", "COT"}

COUNTRY_PROFILE_REBALANCE_DAYS = 365 * 5
OUTPUT_MIX_VERSION = 2
TRADE_PARTNER_WEIGHTS = {
}


@lru_cache(maxsize=1)
def commodity_definitions() -> dict[str, dict]:
    definitions = {}
    for category, items in COMMODITY_GROUPS.items():
        for name, ticker in items.items():
            definitions[ticker] = {
                "name": name,
                "kategorie": category,
                "uses": COMMODITY_USES.get(ticker, []),
                "is_primary_input": True,
            }
    return definitions


def ensure_processed_products(daten: ModuleType) -> None:
    if not hasattr(daten, "processed_products") or not isinstance(daten.processed_products, dict):
        daten.processed_products = {}
    for code, definition in PROCESSED_PRODUCTS.items():
        product = daten.processed_products.setdefault(
            code,
            {
                "name": definition["name"],
                "kategorie": definition["category"],
                "inputs": list(definition["inputs"]),
                "users": list(definition["users"]),
                "supply": _initial_supply(code),
                "demand": _initial_demand(code),
                "inventories": _initial_inventories(code),
                "supply_change": 0.0,
                "demand_change": 0.0,
                "inventories_change": 0.0,
                "producer_count": 0,
                "shortage": 0.0,
                "surplus": 0.0,
                "imbalance": 0.0,
                "price_pressure": 0.0,
                "previous_price_pressure": 0.0,
            },
        )
        product.setdefault("inputs", list(definition["inputs"]))
        product.setdefault("users", list(definition["users"]))
        product.setdefault("price_pressure", 0.0)
        product.setdefault("previous_price_pressure", float(product.get("price_pressure", 0.0)))
        product.setdefault("price_index", 100.0)
        _seed_legacy_flat_market(product, code)


def ensure_population(daten: ModuleType) -> None:
    for country in daten.makro.values():
        country.setdefault("bevoelkerung", 20_000_000.0)
        country.setdefault("population_growth", 0.0)


def ensure_country_economies(daten: ModuleType) -> None:
    ensure_population(daten)
    used_focuses: set[str] = set()
    for country_name, country in daten.makro.items():
        profile = country.setdefault("economic_profile", {})
        if not profile.get("sector_focus"):
            profile["sector_focus"] = _initial_country_sector_focus(country_name, used_focuses)
        used_focuses.update(profile["sector_focus"])
        profile.setdefault("product_focus", _initial_country_product_focus(profile["sector_focus"]))
        profile.setdefault("last_rebalanced_year", getattr(daten, "datum", None).year if hasattr(getattr(daten, "datum", None), "year") else 1990)
        country.setdefault("regional_supply", {})
        country.setdefault("regional_demand", {})
        country.setdefault("regional_shortage", {})
        country.setdefault("regional_pressure", {})
        country.setdefault("exports", {})
        country.setdefault("imports", {})
        country.setdefault("trade_partners", {})
        country.setdefault("trade_partner_details", {})
        country.setdefault("regional_history", {})
        country.setdefault("trade_balance", 0.0)
        country.setdefault("import_dependency", 0.0)
        country.setdefault("export_strength", 0.0)
        country.setdefault("main_sector", next(iter(profile["sector_focus"]), ""))
        country.setdefault("main_bottleneck", "")


def update_population(daten: ModuleType) -> None:
    from kojakstreet.core.workforce import advance_population

    ensure_population(daten)
    for country in daten.makro.values():
        if "workforce" in country:
            advance_population(country, 1.0 / 12.0, floor=2_000_000.0, when=daten.datum.date())
            continue
        growth = float(country.get("bip_prozent", 0.0))
        unemployment = float(country.get("arbeitslosigkeit", 0.06))
        monthly = _clamp((growth - 0.005) * 0.025 - max(0.0, unemployment - 0.08) * 0.010, -0.0025, 0.0035)
        country["bevoelkerung"] = max(2_000_000.0, float(country["bevoelkerung"]) * (1.0 + monthly))
        country["population_growth"] = monthly


def assign_company_specialization(asset: dict, index_hint: int = 0) -> None:
    sector = str(asset.get("branche", ""))
    outputs = SECTOR_OUTPUTS.get(sector) or SECTOR_OUTPUTS.get(_normalized_sector(sector), [])
    if not outputs:
        outputs = ["SDIG"]
    specialization = _company_primary_output(asset, outputs, index_hint)
    if "output_mix" not in asset or int(asset.get("_output_mix_version", 0)) < OUTPUT_MIX_VERSION:
        output_mix = _company_output_mix(asset, outputs, index_hint, specialization)
        asset["output_mix"] = _normalize_mix(output_mix)
        asset["_output_mix_normalized"] = asset["output_mix"]
        asset["_output_mix_version"] = OUTPUT_MIX_VERSION
    asset.setdefault("production_role", "extractor" if specialization in commodity_definitions() else "processor")
    asset["specialization"] = _primary_output(asset["output_mix"])
    asset["specialization_name"] = _output_name(asset["specialization"])
    if "production_capacity" not in asset:
        asset["production_capacity"] = _company_capacity(asset)
    asset.setdefault("capacity_utilization", 0.0)


def assign_company_specializations(daten: ModuleType) -> None:
    counters = defaultdict(int)
    for asset in daten.aktien.values():
        sector = str(asset.get("branche", ""))
        country = str(asset.get("land", ""))
        counter_key = (country, sector)
        assign_company_specialization(asset, counters[counter_key])
        counters[counter_key] += 1


def _ensure_company_specializations(daten: ModuleType) -> None:
    if any(
        "output_mix" not in asset
        or "specialization" not in asset
        or int(asset.get("_output_mix_version", 0)) < OUTPUT_MIX_VERSION
        for asset in daten.aktien.values()
    ):
        assign_company_specializations(daten)
        return
    for asset in daten.aktien.values():
        _cached_output_mix(asset)
        asset.setdefault("production_capacity", _company_capacity(asset))
        asset.setdefault("capacity_utilization", 0.0)


def _company_primary_output(asset: dict, outputs: list[str], index_hint: int) -> str:
    if len(outputs) == 1:
        return outputs[0]
    country = str(asset.get("land", ""))
    sector = str(asset.get("branche", ""))
    offset = int(_stable_unit_interval(f"{country}:{sector}:offset") * len(outputs))
    return outputs[(offset + index_hint) % len(outputs)]


def _company_output_mix(asset: dict, outputs: list[str], index_hint: int, specialization: str) -> dict[str, float]:
    if len(outputs) == 1:
        return {specialization: 1.0}
    country = str(asset.get("land", ""))
    sector = str(asset.get("branche", ""))
    name = str(asset.get("name", ""))
    primary_index = outputs.index(specialization)
    coverage_stride = 4
    secondary = outputs[(primary_index + coverage_stride) % len(outputs)]
    tertiary = outputs[(primary_index + coverage_stride * 2) % len(outputs)]
    quaternary = outputs[(primary_index + coverage_stride * 3) % len(outputs)]
    concentration = _stable_unit_interval(f"{country}:{sector}:{name}:concentration")
    primary_weight = 0.58 + concentration * 0.24
    secondary_weight = 0.12 + _stable_unit_interval(f"{name}:secondary_weight") * 0.15
    tertiary_weight = 0.05 + _stable_unit_interval(f"{name}:tertiary_weight") * 0.08
    output_mix = {
        specialization: primary_weight,
        secondary: secondary_weight,
        tertiary: tertiary_weight,
    }
    if _stable_unit_interval(f"{name}:wide_mix") > 0.36:
        output_mix[quaternary] = 0.03 + _stable_unit_interval(f"{name}:quaternary_weight") * 0.06
    return output_mix


def update_production_chain(
    daten: ModuleType,
    *,
    advance_population: bool = True,
    update_country_trade: bool = True,
    rebalance_country_profiles: bool = True,
    rebalance_company_outputs: bool = True,
    record_regional_history: bool = True,
    record_company_history: bool = True,
) -> None:
    ensure_processed_products(daten)
    ensure_country_economies(daten)
    if advance_population:
        update_population(daten)
    else:
        ensure_population(daten)
    _ensure_company_specializations(daten)
    company_rows = company_runtimes(daten)
    capacities = _company_capacities(daten, company_rows)
    sector_activity = _sector_activity(company_rows)
    sector_input_demand = _sector_input_demand(sector_activity)
    total_sector_activity = sum(sector_activity.values())
    total_population = sum(float(country.get("bevoelkerung", 20_000_000.0)) for country in daten.makro.values())
    consumer_base = total_population / 1_000_000.0
    household_demand = _household_demand(consumer_base)
    primary_usage = defaultdict(float)
    product_usage = defaultdict(float)
    date_label = daten.datum.strftime("%d.%m.%Y") if hasattr(daten, "datum") else ""

    for code, definition in _processed_product_definitions().items():
        product = daten.processed_products[code]
        product["code"] = code
        _seed_legacy_flat_market(product, code)
        previous_supply = max(1.0, float(product.get("supply", 100.0)))
        previous_demand = max(1.0, float(product.get("demand", 100.0)))
        previous_inventories = max(1.0, float(product.get("inventories", 100.0)))
        direct_demand = _product_demand(
            code,
            definition,
            sector_activity,
            sector_input_demand,
            household_demand,
            total_sector_activity,
        )
        requirements = _input_requirements(code, definition["inputs"], direct_demand)
        input_ratio = _input_availability_ratio(daten, requirements)
        capacity = max(_initial_supply(code) * 0.72, capacities.get(code, 0.0), direct_demand * 0.88)
        profile = _balance_profile(code)
        potential_supply = capacity * input_ratio
        supply = _clamp(
            potential_supply,
            direct_demand * profile["supply_floor"],
            direct_demand * profile["supply_ceiling"],
        )
        inventories = _buffered_inventory(previous_inventories, supply, direct_demand)
        shock_mode = bool(getattr(daten, "aktives_event", None))
        _set_supply_demand(product, previous_supply, previous_demand, previous_inventories, supply, direct_demand, inventories, date_label, shock_mode=shock_mode)
        product["producer_count"] = capacities.get(f"{code}:count", 0)
        product["input_availability"] = input_ratio
        _set_balance_metrics(product)
        for normalized, required in requirements.items():
            if normalized in daten.rohstoffe:
                primary_usage[normalized] += required
            elif normalized in daten.processed_products:
                product_usage[normalized] += required

    for ticker, commodity in daten.rohstoffe.items():
        commodity["code"] = ticker
        _seed_legacy_flat_market(commodity, ticker)
        previous_supply = max(1.0, float(commodity.get("production", 100.0)))
        previous_demand = max(1.0, float(commodity.get("demand", 100.0)))
        previous_inventories = max(1.0, float(commodity.get("inventories", 100.0)))
        base_consumer = _commodity_consumer_demand(ticker, consumer_base)
        demand = max(18.0, primary_usage[ticker] * 0.55 + base_consumer)
        profile = _balance_profile(ticker)
        potential_supply = max(_initial_supply(ticker) * 0.76, capacities.get(ticker, _initial_supply(ticker)))
        demand *= shock_multiplier(daten, "demand", ticker)
        supply = _clamp(
            potential_supply,
            demand * profile["supply_floor"],
            demand * profile["supply_ceiling"],
        )
        # Apply the shared availability state after the normal equilibrium
        # corridor; otherwise the corridor immediately reconstructs the shock.
        supply *= shock_multiplier(daten, "supply", ticker)
        inventories = _buffered_inventory(previous_inventories, supply, demand)
        shock_mode = bool(getattr(daten, "aktives_event", None))
        _set_supply_demand(commodity, previous_supply, previous_demand, previous_inventories, supply, demand, inventories, date_label, shock_mode=shock_mode)
        commodity["producer_count"] = capacities.get(f"{ticker}:count", 0)
        _set_balance_metrics(commodity)
        commodity["f\u00f6rder_menge"] = _clamp((commodity["supply"] - commodity["demand"]) / max(1.0, commodity["demand"]), -3.0, 3.0)

    for code, usage in product_usage.items():
        product = daten.processed_products[code]
        product["downstream_usage"] = usage

    opportunity_scores = _opportunity_scores_by_sector(daten) if rebalance_company_outputs else None
    company_market_exposures = _company_market_exposures(daten, company_rows)
    _update_company_utilization(
        daten,
        date_label,
        opportunity_scores,
        company_rows,
        company_market_exposures,
        record_history=record_company_history,
        rebalance_outputs=rebalance_company_outputs,
    )
    if update_country_trade:
        _update_country_trade_flows(
            daten,
            date_label,
            company_rows=company_rows,
            company_market_exposures=company_market_exposures,
            record_history=record_regional_history,
        )
    if rebalance_company_outputs:
        # Rebalancing affects the next production step.  Discard the direct
        # market-reference rows once the monthly mixes have changed.
        daten._production_company_market_exposures = None
    if rebalance_country_profiles:
        _maybe_rebalance_country_profiles(daten)


def _company_capacities(daten: ModuleType, company_rows=None) -> dict[str, float]:
    capacities = defaultdict(float)
    for row in company_rows if company_rows is not None else company_runtimes(daten):
        asset = row.asset
        if "output_mix" not in asset or "specialization" not in asset:
            assign_company_specialization(asset)
        output_mix = _cached_output_mix(asset)
        capacity = _company_capacity(asset)
        asset["production_capacity"] = capacity
        for code, share in output_mix.items():
            if not code:
                continue
            capacities[code] += capacity * share
            if share >= 0.05:
                capacities[f"{code}:count"] += 1
    for asset in getattr(daten, "kryptos", {}).values():
        task_code = str(asset.get("task_type", "PAY"))
        service_code = str(asset.get("service_code", CRYPTO_SERVICE_CODES.get(task_code, "CRPAY")))
        capacity = max(1.0, float(asset.get("network_capacity", asset.get("demand", 1.0))))
        utilization = max(0.05, float(asset.get("network_utilization", 0.7)))
        service_supply = capacity * min(1.2, max(0.25, utilization + 0.25))
        capacities[service_code] += service_supply
        capacities[f"{service_code}:count"] += 1
        asset["production_capacity"] = service_supply
    return capacities


def _company_capacity(asset: dict) -> float:
    revenue = max(1.0, float(asset.get("revenue", asset.get("market_cap", 1_000_000_000.0) / 2.0)))
    margin_bonus = 1.0 + max(-0.35, min(0.45, float(asset.get("fcf_margin", 0.08))))
    base_capacity = max(12.0, (revenue ** 0.5 / 95.0) * margin_bonus)
    existing_capacity = float(asset.get("production_capacity", base_capacity))
    return max(8.0, (existing_capacity * 0.75) + (base_capacity * 0.25))


def _sector_activity(company_rows) -> dict[str, float]:
    activity = defaultdict(float)
    for row in company_rows:
        asset = row.asset
        normalized = _normalized_sector(row.sector)
        utilization = float(asset.get("capacity_utilization", 0.85))
        growth = max(-0.08, min(0.12, float(asset.get("revenue_growth", 0.0))))
        capacity = float(asset.get("production_capacity", 0.0)) or _company_capacity(asset)
        activity[normalized] += capacity * (0.45 + utilization * 0.25 + max(0.0, growth) * 1.4)
    return activity


def _sector_input_demand(sector_activity: dict[str, float]) -> dict[str, float]:
    demand = defaultdict(float)
    for sector, activity in sector_activity.items():
        for item, weight in SECTOR_INPUT_WEIGHTS.get(sector, {}).items():
            demand[_normalize_input(item)] += activity * weight
    return demand


@lru_cache(maxsize=256)
def _initial_supply(code: str) -> float:
    demand = _initial_demand(code)
    profile = _balance_profile(code)
    if code in ESSENTIAL_OUTPUTS or code in ESSENTIAL_COMMODITIES:
        balance = 0.985 + _stable_unit_interval(f"{code}:supply") * 0.085
    elif code in STRATEGIC_OUTPUTS or code in STRATEGIC_COMMODITIES:
        balance = 0.88 + _stable_unit_interval(f"{code}:supply") * 0.24
    elif code in DISCRETIONARY_OUTPUTS or code in DISCRETIONARY_COMMODITIES:
        balance = 0.78 + _stable_unit_interval(f"{code}:supply") * 0.38
    else:
        balance = 0.86 + _stable_unit_interval(f"{code}:supply") * 0.28
    return max(12.0, demand * _clamp(balance, profile["supply_floor"] * 0.96, profile["supply_ceiling"]))


@lru_cache(maxsize=256)
def _initial_demand(code: str) -> float:
    scale = _market_scale(code)
    bias = 1.0 + ((_stable_unit_interval(f"{code}:demand") - 0.5) * 0.18)
    return max(10.0, scale * bias)


@lru_cache(maxsize=256)
def _initial_inventories(code: str) -> float:
    demand = _initial_demand(code)
    if code in {"LOAN", "INS", "ASSETM", "PAY", "SDIG", "SOFT", "CLOUD", "PLAT", "HLTH", "MOB", "FIX", "DATA"}:
        cover = 0.18 + _stable_unit_interval(f"{code}:inventory") * 0.30
    elif code in ESSENTIAL_OUTPUTS or code in ESSENTIAL_COMMODITIES:
        cover = 0.72 + _stable_unit_interval(f"{code}:inventory") * 0.65
    elif code in STRATEGIC_OUTPUTS or code in STRATEGIC_COMMODITIES:
        cover = 0.88 + _stable_unit_interval(f"{code}:inventory") * 0.85
    else:
        cover = 0.48 + _stable_unit_interval(f"{code}:inventory") * 0.78
    return max(1.0, demand * cover)


@lru_cache(maxsize=256)
def _market_scale(code: str) -> float:
    if code in ESSENTIAL_OUTPUTS or code in ESSENTIAL_COMMODITIES:
        base = 260.0
    elif code in STRATEGIC_OUTPUTS or code in STRATEGIC_COMMODITIES:
        base = 145.0
    elif code in DISCRETIONARY_OUTPUTS or code in DISCRETIONARY_COMMODITIES:
        base = 74.0
    elif code in CYCLICAL_OUTPUTS:
        base = 178.0
    else:
        base = 132.0
    return base * (0.68 + _stable_unit_interval(f"{code}:scale") * 0.84)


@lru_cache(maxsize=256)
def _demand_texture(code: str) -> float:
    return 0.92 + _stable_unit_interval(f"{code}:texture") * 0.18


def _seed_legacy_flat_market(asset: dict, code: str) -> None:
    if asset.get("_supply_chain_seeded") is True:
        return
    history_exists = any(asset.get(key) for key in ("supply_history", "demand_history", "inventory_history"))
    supply = float(asset.get("supply", asset.get("production", 100.0)) or 100.0)
    demand = float(asset.get("demand", 100.0) or 100.0)
    inventories = float(asset.get("inventories", 100.0) or 100.0)
    if not history_exists and abs(supply - 100.0) < 0.0001 and abs(demand - 100.0) < 0.0001 and abs(inventories - 100.0) < 0.0001:
        seeded_supply = _initial_supply(code)
        asset["supply"] = seeded_supply
        asset["production"] = seeded_supply
        asset["demand"] = _initial_demand(code)
        asset["inventories"] = _initial_inventories(code)
    asset["_supply_chain_seeded"] = True


def _input_requirements(code: str, inputs: list[str], demand: float) -> dict[str, float]:
    coefficients = _input_recipe_coefficients(code, tuple(inputs))
    return {
        input_code: demand * coefficient
        for input_code, coefficient in coefficients.items()
    }


@lru_cache(maxsize=256)
def _input_recipe_coefficients(code: str, inputs: tuple[str, ...]) -> dict[str, float]:
    recipe = INPUT_RECIPES.get(code, {})
    if recipe:
        return {
            _normalize_input(item): max(0.0, float(weight))
            for item, weight in recipe.items()
            if float(weight) > 0.0
        }
    if not inputs:
        return {}
    weighted = {}
    for index, item in enumerate(inputs):
        input_code = _normalize_input(item)
        texture = 0.72 + _stable_unit_interval(f"{code}:{input_code}:{index}") * 0.62
        weighted[input_code] = weighted.get(input_code, 0.0) + texture
    total_weight = sum(weighted.values()) or 1.0
    return {
        input_code: weight / total_weight
        for input_code, weight in weighted.items()
    }


def _visible_shortage(asset: dict) -> float:
    supply = float(asset.get("supply", asset.get("production", 0.0)))
    demand = float(asset.get("demand", 0.0))
    return max(0.0, demand - supply) / max(1.0, demand)


def _visible_surplus(asset: dict) -> float:
    supply = float(asset.get("supply", asset.get("production", 0.0)))
    demand = float(asset.get("demand", 0.0))
    return max(0.0, supply - demand) / max(1.0, demand)


def _set_balance_metrics(asset: dict) -> None:
    shortage = _visible_shortage(asset)
    surplus = _visible_surplus(asset)
    asset["shortage"] = shortage
    asset["surplus"] = surplus
    asset["imbalance"] = shortage - surplus


def _stable_unit_interval(text: str) -> float:
    value = 0
    for char in text:
        value = (value * 131 + ord(char)) % 10_000
    return value / 10_000.0


def _household_demand(consumer_base: float) -> dict[str, float]:
    return {code: consumer_base * weight for code, weight in CONSUMER_BASKET.items()}


def _product_demand(
    code: str,
    definition: dict,
    sector_activity: dict[str, float],
    sector_input_demand: dict[str, float],
    household_demand: dict[str, float],
    total_sector_activity: float,
) -> float:
    demand = household_demand.get(code, 0.0)
    users = definition.get("users", [])
    if any(user in {"alle Branchen", "alle produzierenden Branchen", "produzierende Branchen"} for user in users):
        demand += total_sector_activity * 0.020
    for user in users:
        demand += sector_activity.get(_normalized_sector(user), 0.0) * 0.085
    demand += sector_input_demand.get(code, 0.0) * 0.38
    return max(_initial_demand(code) * 0.28, demand * _demand_texture(code))


def _update_country_trade_flows(
    daten: ModuleType,
    date_label: str,
    *,
    company_rows=None,
    company_market_exposures=None,
    record_history: bool = True,
) -> None:
    countries = _country_names(daten)
    if not countries:
        return
    item_codes, markets = _trade_market_cache(daten)
    supply_by_country = {country: defaultdict(float) for country in countries}
    demand_by_country = {country: defaultdict(float) for country in countries}
    trade_capacity = {
        (country, direction): _country_trade_capacity(daten, country, direction)
        for country in countries
        for direction in ("export", "import")
    }
    partner_base_weights = _cached_partner_base_weights(daten, countries)
    company_rows = company_rows if company_rows is not None else company_runtimes(daten)
    company_market_exposures = company_market_exposures or _company_market_exposures(daten, company_rows)
    main_sector_by_country = main_country_sectors(company_rows)
    # Country profiles/ratings stay fixed throughout this aggregation.
    country_bonuses = {}

    def append_history(target: dict, key: str, value: float) -> None:
        history = target.setdefault(key, [])
        history.append((float(value), date_label, ""))
        if len(history) > 900:
            del history[:-900]

    for row, exposures in company_market_exposures:
        asset = row.asset
        country = row.country
        if country not in supply_by_country:
            continue
        capacity = max(1.0, float(asset["production_capacity"] if "production_capacity" in asset else _company_capacity(asset)))
        bonus_key = (country, row.sector)
        country_bonus = country_bonuses.get(bonus_key)
        if country_bonus is None:
            country_bonus = _country_sector_bonus(daten, country, row.sector)
            country_bonuses[bonus_key] = country_bonus
        for code, share, _market in exposures:
            supply_by_country[country][code] += capacity * share * country_bonus

    for code in item_codes:
        global_market = markets[code]
        global_demand = float(global_market.get("demand", 0.0))
        global_supply = float(global_market.get("supply", global_market.get("production", 0.0)))
        demand_weights = {country: _country_demand_weight(daten, country, code) for country in countries}
        total_weight = sum(demand_weights.values()) or 1.0
        total_supply = sum(supply_by_country[country][code] for country in countries)
        for country in countries:
            demand_share = demand_weights[country] / total_weight
            demand_by_country[country][code] = global_demand * demand_share
            if total_supply > 0 and global_supply > 0:
                supply_by_country[country][code] = supply_by_country[country][code] * global_supply / total_supply
            elif total_supply <= 0 and global_supply > 0:
                supply_by_country[country][code] = global_supply * demand_share
    exports_by_country, imports_by_country, partner_trade_by_country, partner_details_by_country = _match_country_trade(
        daten,
        countries,
        item_codes,
        supply_by_country,
        demand_by_country,
        trade_capacity,
        partner_base_weights,
    )
    trade_balance_values = {}
    for country in countries:
        macro = daten.makro[country]
        exports = exports_by_country[country]
        imports = imports_by_country[country]
        partner_trade = partner_trade_by_country[country]
        partner_details = partner_details_by_country[country]
        regional_supply = {}
        regional_demand = {}
        regional_shortage = {}
        regional_pressure = {}

        for code in item_codes:
            supply = float(supply_by_country[country][code])
            demand = float(demand_by_country[country][code])
            import_amount = float(imports.get(code, 0.0))
            export_amount = float(exports.get(code, 0.0))
            effective_supply = max(0.0, supply + import_amount - export_amount)
            regional_supply[code] = supply
            regional_demand[code] = demand
            regional_shortage[code] = max(0.0, demand - effective_supply) / max(1.0, demand)
            regional_pressure[code] = _clamp(
                regional_shortage[code] * 0.44 - max(0.0, effective_supply - demand) / max(1.0, demand) * 0.08,
                -0.10,
                0.32,
            )

        total_imports = sum(imports.values())
        total_exports = sum(exports.values())
        total_demand = sum(regional_demand.values()) or 1.0
        macro["regional_supply"] = dict(regional_supply)
        macro["regional_demand"] = dict(regional_demand)
        macro["regional_shortage"] = dict(regional_shortage)
        macro["regional_pressure"] = dict(regional_pressure)
        macro["exports"] = dict(exports)
        macro["imports"] = dict(imports)
        macro["trade_partners"] = dict(sorted(partner_trade.items(), key=lambda item: item[1], reverse=True)[:4])
        macro["trade_partner_details"] = {code: dict(partners) for code, partners in partner_details.items()}
        macro["trade_balance"] = total_exports - total_imports
        trade_balance_values[country] = macro["trade_balance"]
        macro["import_dependency"] = total_imports / total_demand
        macro["export_strength"] = total_exports / total_demand
        macro["main_sector"] = main_sector_by_country.get(country, "")
        macro["main_bottleneck"] = _item_name(max(regional_shortage, key=regional_shortage.get)) if regional_shortage else ""
        if record_history:
            regional_history = macro.setdefault("regional_history", {})
            for code in item_codes:
                code_history = regional_history.setdefault(code, {})
                supply = float(regional_supply.get(code, 0.0))
                demand = float(regional_demand.get(code, 0.0))
                export = float(exports.get(code, 0.0))
                import_value = float(imports.get(code, 0.0))
                append_history(code_history, "produced", supply)
                append_history(code_history, "demanded", demand)
                append_history(code_history, "gap", supply - demand)
                append_history(code_history, "shortage", float(regional_shortage.get(code, 0.0)) * 100.0)
                append_history(code_history, "pressure", float(regional_pressure.get(code, 0.0)) * 100.0)
                append_history(code_history, "exports", export)
                append_history(code_history, "imports", import_value)
                append_history(code_history, "net", export - import_value)
            append_history(macro, "import_dependency_history", macro["import_dependency"] * 100.0)
            append_history(macro, "export_strength_history", macro["export_strength"] * 100.0)
    average_balance = sum(trade_balance_values.values()) / len(trade_balance_values) if trade_balance_values else 0.0
    for country in countries:
        macro = daten.makro[country]
        macro["trade_balance"] = float(macro.get("trade_balance", 0.0)) - average_balance
        if record_history:
            append_history(macro, "trade_balance_history", macro["trade_balance"])


def _match_country_trade(
    daten: ModuleType,
    countries: list[str],
    item_codes: tuple[str, ...],
    supply_by_country: dict[str, defaultdict[str, float]],
    demand_by_country: dict[str, defaultdict[str, float]],
    trade_capacity: dict[tuple[str, str], float],
    partner_base_weights: dict[str, dict[str, float]],
) -> tuple[
    dict[str, defaultdict[str, float]],
    dict[str, defaultdict[str, float]],
    dict[str, defaultdict[str, float]],
    dict[str, dict[str, defaultdict[str, float]]],
]:
    exports_by_country = {country: defaultdict(float) for country in countries}
    imports_by_country = {country: defaultdict(float) for country in countries}
    partner_trade_by_country = {country: defaultdict(float) for country in countries}
    partner_details_by_country = {country: {} for country in countries}
    for code in item_codes:
        exportable = {
            country: max(0.0, float(supply_by_country[country][code]) - float(demand_by_country[country][code]))
            * trade_capacity[(country, "export")]
            for country in countries
        }
        importable = {
            country: max(0.0, float(demand_by_country[country][code]) - float(supply_by_country[country][code]))
            * trade_capacity[(country, "import")]
            for country in countries
        }
        remaining_exports = {country: amount for country, amount in exportable.items() if amount > 0.0}
        remaining_imports = {country: amount for country, amount in importable.items() if amount > 0.0}
        if not remaining_exports or not remaining_imports:
            continue
        total_exportable = sum(remaining_exports.values())
        total_importable = sum(remaining_imports.values())
        trade_volume = min(total_exportable, total_importable)
        for importer, import_capacity in sorted(remaining_imports.items(), key=lambda item: item[1], reverse=True):
            import_target = trade_volume * import_capacity / total_importable
            while import_target > 0.0001 and remaining_exports:
                exporter = _best_export_partner(importer, remaining_exports, partner_base_weights)
                shipment = min(import_target, remaining_exports[exporter])
                imports_by_country[importer][code] += shipment
                exports_by_country[exporter][code] += shipment
                partner_trade_by_country[importer][exporter] += shipment
                partner_trade_by_country[exporter][importer] += shipment
                partner_details_by_country[importer].setdefault(code, defaultdict(float))[exporter] += shipment
                partner_details_by_country[exporter].setdefault(code, defaultdict(float))[importer] += shipment
                import_target -= shipment
                remaining_exports[exporter] -= shipment
                if remaining_exports[exporter] <= 0.0001:
                    del remaining_exports[exporter]
    return exports_by_country, imports_by_country, partner_trade_by_country, partner_details_by_country


def _best_export_partner(
    importer: str,
    exporters: dict[str, float],
    partner_base_weights: dict[str, dict[str, float]],
) -> str:
    weights = partner_base_weights.get(importer, {})
    return max(
        exporters,
        key=lambda exporter: exporters[exporter] * float(weights.get(exporter, 0.01)),
    )


def _input_availability_ratio(daten: ModuleType, requirements: dict[str, float]) -> float:
    if not requirements:
        return 1.0
    ratios = []
    for input_code, required in requirements.items():
        source = daten.rohstoffe.get(input_code) or daten.processed_products.get(input_code)
        if not source:
            ratios.append(0.90)
            continue
        inventories = float(source.get("inventories", 100.0))
        supply = float(source.get("supply", source.get("production", 100.0)))
        available = supply + (inventories * 0.35)
        ratios.append(_clamp(available / max(1.0, required), 0.15, 1.25))
    return min(1.15, sum(ratios) / len(ratios))


def _buffered_inventory(previous_inventories: float, supply: float, demand: float) -> float:
    gap = supply - demand
    if gap < 0:
        drawdown = min(previous_inventories * 0.45, abs(gap) * 0.70)
        return max(1.0, previous_inventories - drawdown)
    rebuild = min(gap * 0.55, max(demand * 1.8 - previous_inventories, 0.0))
    return max(1.0, previous_inventories + rebuild)


def _set_supply_demand(
    asset: dict,
    previous_supply: float,
    previous_demand: float,
    previous_inventories: float,
    supply: float,
    demand: float,
    inventories: float,
    date_label: str = "",
    *,
    shock_mode: bool = False,
) -> None:
    previous_price_pressure = float(asset.get("price_pressure", 0.0))
    is_first_supply_chain_point = not asset.get("supply_history") and not asset.get("demand_history")
    if is_first_supply_chain_point:
        previous_supply = supply
        previous_demand = demand
        previous_inventories = inventories
    else:
        supply = _smooth_real_economy_value(previous_supply, supply, shock_mode=shock_mode)
        demand = _smooth_real_economy_value(previous_demand, demand, shock_mode=shock_mode)
        inventories = _smooth_real_economy_value(previous_inventories, inventories, shock_mode=shock_mode)
    shortage = max(0.0, demand - supply) / max(1.0, demand)
    surplus = max(0.0, supply - demand) / max(1.0, demand)
    stock_cover = inventories / max(1.0, demand)
    asset["previous_production"] = previous_supply
    asset["previous_supply"] = previous_supply
    asset["previous_demand"] = previous_demand
    asset["previous_inventories"] = previous_inventories
    asset["previous_price_pressure"] = previous_price_pressure
    asset["production"] = supply
    asset["supply"] = supply
    asset["demand"] = demand
    asset["inventories"] = inventories
    asset["shortage"] = shortage
    asset["surplus"] = surplus
    asset["imbalance"] = shortage - surplus
    asset["production_change"] = _clamp((supply - previous_supply) / previous_supply, -0.18, 0.18)
    asset["supply_change"] = asset["production_change"]
    asset["demand_change"] = _clamp((demand - previous_demand) / previous_demand, -0.18, 0.18)
    asset["inventories_change"] = _clamp((inventories - previous_inventories) / previous_inventories, -0.22, 0.22)
    profile = _balance_profile(str(asset.get("code", "")))
    raw_pressure = (
        (shortage * 0.45)
        - (surplus * 0.28)
        + (asset["demand_change"] * 0.18)
        - max(0.0, stock_cover - 2.0) * 0.045
        + max(0.0, 0.45 - stock_cover) * 0.035
    ) * profile["pressure_multiplier"]
    asset["price_pressure"] = _clamp((previous_price_pressure * 0.82) + (raw_pressure * 0.18), -0.18, 0.55)
    previous_price_index = max(1.0, float(asset.get("price_index", asset.get("kurs", 100.0))))
    index_return = _clamp(
        (asset["price_pressure"] * 0.020)
        + (asset["demand_change"] * 0.010)
        - (asset["inventories_change"] * 0.005),
        -0.020,
        0.030,
    )
    asset["previous_price_index"] = previous_price_index
    asset["price_index"] = max(1.0, previous_price_index * (1.0 + index_return))
    _append_metric_history(asset, "supply_history", supply, date_label)
    _append_metric_history(asset, "demand_history", demand, date_label)
    _append_metric_history(asset, "inventory_history", inventories, date_label)
    _append_metric_history(asset, "shortage_history", shortage * 100.0, date_label)
    _append_metric_history(asset, "surplus_history", surplus * 100.0, date_label)
    _append_metric_history(asset, "imbalance_history", (shortage - surplus) * 100.0, date_label)
    _append_metric_history(asset, "price_pressure_history", asset["price_pressure"] * 100.0, date_label)
    _append_metric_history(asset, "price_index_history", asset["price_index"], date_label)


def _smooth_real_economy_value(previous: float, target: float, *, shock_mode: bool) -> float:
    previous = max(1.0, float(previous))
    target = max(1.0, float(target))
    raw_change = (target - previous) / previous
    if shock_mode:
        max_step = 0.16
        alpha = 0.72
    else:
        max_step = 0.055
        alpha = 0.34
    capped_target = previous * (1.0 + _clamp(raw_change, -max_step, max_step))
    return previous + ((capped_target - previous) * alpha)


def _append_metric_history(asset: dict, key: str, value: float, date_label: str) -> None:
    history = asset.setdefault(key, [])
    history.append((float(value), date_label, ""))
    if len(history) > 900:
        del history[:-900]


def _update_company_utilization(
    daten: ModuleType,
    date_label: str = "",
    opportunity_scores: dict[str, dict[str, float]] | None = None,
    company_rows=None,
    company_market_exposures=None,
    *,
    record_history: bool = True,
    rebalance_outputs: bool = True,
) -> None:
    company_rows = company_rows if company_rows is not None else company_runtimes(daten)
    company_market_exposures = company_market_exposures or _company_market_exposures(daten, company_rows)
    # These market measures are read-only during company utilization. Keep the
    # cache within this call, and do not cache an aliased company/market object.
    company_ids = {id(row.asset) for row in company_rows}
    market_measures = {}
    for row, exposures in company_market_exposures:
        asset = row.asset
        weighted_utilization = 0.0
        weighted_shortage = 0.0
        weighted_input_availability = 0.0
        weighted_pricing_power = 0.0
        for _code, share, market in exposures:
            identity = id(market)
            measures = market_measures.get(identity)
            if measures is None:
                demand = max(1.0, float(market.get("demand", 100.0)))
                supply = max(1.0, float(market.get("supply", market.get("production", 100.0))))
                measures = (
                    _clamp(demand / supply, 0.35, 1.25),
                    float(market.get("shortage", 0.0)),
                    float(market.get("input_availability", 1.0)),
                    float(market.get("price_pressure", 0.0)),
                )
                if identity not in company_ids:
                    market_measures[identity] = measures
            weighted_utilization += measures[0] * share
            weighted_shortage += measures[1] * share
            weighted_input_availability += measures[2] * share
            weighted_pricing_power += measures[3] * share
        utilization = weighted_utilization
        shortage = weighted_shortage
        input_availability = weighted_input_availability
        pricing_power = _clamp(weighted_pricing_power - 0.10, -0.35, 0.45)
        asset["capacity_utilization"] = utilization
        asset["input_availability"] = input_availability
        asset["supply_chain_shortage"] = shortage
        asset["production_score"] = _clamp(
            0.03
            + (utilization - 0.70) * 0.35
            + pricing_power * 0.25
            - shortage * 0.20
            + (input_availability - 0.75) * 0.15,
            -0.35,
            0.35,
        )
        profile_multiplier = _sector_capacity_multiplier(str(asset.get("branche", "")))
        if shortage > 0.20:
            input_multiplier = 0.55 + min(0.45, input_availability * 0.45)
            capacity_growth = min(
                0.18,
                (shortage * 0.13 + max(0.0, utilization - 0.90) * 0.05) * input_multiplier * profile_multiplier,
            )
        elif utilization < 0.50:
            capacity_growth = -0.006
        else:
            capacity_growth = 0.005
        asset["production_capacity"] = max(8.0, float(asset.get("production_capacity", 0.0) or _company_capacity(asset)) * (1.0 + capacity_growth))
        asset["capacity_growth"] = capacity_growth
        if record_history:
            _record_company_quantity_history(asset, date_label)
        if rebalance_outputs:
            _rebalance_output_mix(asset, daten, opportunity_scores)


def _company_market_exposures(daten: ModuleType, company_rows) -> list[tuple[object, tuple[tuple[str, float, dict], ...]]]:
    """Cache invariant company/output/market links; market values stay live."""

    stocks = getattr(daten, "aktien", {})
    signature = (
        tuple(stocks.keys()),
        tuple(getattr(daten, "rohstoffe", {}).keys()),
        tuple(getattr(daten, "processed_products", {}).keys()),
    )
    cache = getattr(daten, "_production_company_market_exposures", None)
    if isinstance(cache, dict) and cache.get("signature") == signature:
        return cache["rows"]
    commodities = getattr(daten, "rohstoffe", {})
    products = getattr(daten, "processed_products", {})
    rows = [
        (
            row,
            tuple(
                (code, share, commodities.get(code) or products.get(code, {}))
                for code, share in _cached_output_mix(row.asset).items()
            ),
        )
        for row in company_rows
    ]
    daten._production_company_market_exposures = {"signature": signature, "rows": rows}
    return rows


def _record_company_quantity_history(asset: dict, date_label: str) -> None:
    capacity = max(1.0, float(asset.get("production_capacity", 0.0)))
    output_plan, input_plan = _company_quantity_plan(asset)
    output_history = asset.setdefault("company_output_history", {})
    for code, share in output_plan:
        company_qty = capacity * share
        history = output_history.setdefault(code, {}).setdefault("history", [])
        history.append((float(company_qty), date_label, ""))
        if len(history) > 900:
            del history[:-900]
    input_history = asset.setdefault("company_input_history", {})
    for code, capacity_share in input_plan:
        required = capacity * capacity_share
        history = input_history.setdefault(code, {}).setdefault("history", [])
        history.append((float(required), date_label, ""))
        if len(history) > 900:
            del history[:-900]


def _company_quantity_plan(asset: dict) -> tuple[tuple[tuple[str, float], ...], tuple[tuple[str, float], ...]]:
    output_mix = _cached_output_mix(asset)
    cached = asset.get("_company_quantity_plan")
    if isinstance(cached, dict) and cached.get("source") is output_mix:
        return cached["outputs"], cached["inputs"]
    outputs = tuple(output_mix.items())
    input_shares = defaultdict(float)
    for code, share in outputs:
        definition = PROCESSED_PRODUCTS.get(code)
        if not definition:
            continue
        inputs = definition["inputs"]
        input_share = share / max(1, len(inputs))
        for input_code in inputs:
            input_shares[_normalize_input(input_code)] += input_share
    inputs = tuple(input_shares.items())
    asset["_company_quantity_plan"] = {"source": output_mix, "outputs": outputs, "inputs": inputs}
    return outputs, inputs


def _balance_profile(code: str) -> dict[str, float]:
    if code in ESSENTIAL_OUTPUTS or code in ESSENTIAL_COMMODITIES:
        return BALANCE_PROFILES["essential"]
    if code in STRATEGIC_OUTPUTS or code in STRATEGIC_COMMODITIES:
        return BALANCE_PROFILES["strategic"]
    if code in DISCRETIONARY_OUTPUTS or code in DISCRETIONARY_COMMODITIES:
        return BALANCE_PROFILES["discretionary"]
    if code in CYCLICAL_OUTPUTS:
        return BALANCE_PROFILES["cyclical"]
    return BALANCE_PROFILES["industrial"]


def _sector_capacity_multiplier(sector: str) -> float:
    if sector in {"Stromerzeuger", "Gesundheit", "Landwirtschaft", "Telekommunikation"}:
        return BALANCE_PROFILES["essential"]["capacity_multiplier"]
    if sector in {"Technologie", "Verteidigung", "Automobil"}:
        return BALANCE_PROFILES["cyclical"]["capacity_multiplier"]
    if sector in {"Konsumg\u00fcter", "Finanzen"}:
        return BALANCE_PROFILES["discretionary"]["capacity_multiplier"]
    return BALANCE_PROFILES["industrial"]["capacity_multiplier"]


def _commodity_consumer_demand(ticker: str, consumer_base: float) -> float:
    weights = {
        "XAU": 0.04,
        "XAG": 0.03,
        "ZW": 0.05,
        "ZRC": 0.04,
        "COF": 0.04,
        "COC": 0.03,
        "SUG": 0.05,
        "WOOD": 0.03,
        "COT": 0.03,
        "MEAT": 0.08,
        "FISH": 0.06,
    }
    return consumer_base * weights.get(ticker, 0.0)


def _initial_country_sector_focus(country_name: str, used_focuses: set[str]) -> dict[str, float]:
    candidates = list(SECTOR_OUTPUTS)
    preferred = {
        "Ameron": ["Technologie", "Finanzen", "Verteidigung", "\u00d6l und Gas"],
        "Albionia": ["Finanzen", "Verteidigung", "Immobilien", "Transport und Logistik"],
        "Ardonia": ["Maschinenbau", "Automobil", "Chemie", "Stromerzeuger"],
        "Valoria": ["Gesundheit", "Konsumg\u00fcter", "Chemie", "Technologie"],
        "Romara": ["Automobil", "Konsumg\u00fcter", "Immobilien", "Transport und Logistik"],
        "Soleria": ["Landwirtschaft", "Einzelhandel", "Stromerzeuger", "Konsumg\u00fcter"],
        "Nordmark": ["\u00d6l und Gas", "Stromerzeuger", "Transport und Logistik", "Edelmetallf\u00f6rderer"],
        "Sarmatia": ["Maschinenbau", "Landwirtschaft", "Transport und Logistik", "Chemie"],
        "Danubria": ["Landwirtschaft", "Automobil", "Maschinenbau", "Gesundheit"],
        "Carpathia": ["\u00d6l und Gas", "Edelmetallf\u00f6rderer", "Verteidigung", "Maschinenbau"],
        "Anatria": ["Transport und Logistik", "Einzelhandel", "Automobil", "Verteidigung"],
        "Azaria": ["\u00d6l und Gas", "Finanzen", "Stromerzeuger", "Immobilien"],
        "Indara": ["Technologie", "Gesundheit", "Einzelhandel", "Landwirtschaft"],
        "Hanxia": ["Maschinenbau", "Technologie", "Konsumg\u00fcter", "Edelmetallf\u00f6rderer"],
        "Pacifica": ["Technologie", "Maschinenbau", "Automobil", "Telekommunikation"],
        "Koryo": ["Technologie", "Telekommunikation", "Automobil", "Verteidigung"],
        "Amazonia": ["Landwirtschaft", "Edelmetallf\u00f6rderer", "Konsumg\u00fcter", "Stromerzeuger"],
        "Canadia": ["Edelmetallf\u00f6rderer", "Transport und Logistik", "Finanzen", "Landwirtschaft"],
        "Auroria": ["Edelmetallf\u00f6rderer", "Landwirtschaft", "Stromerzeuger", "Transport und Logistik"],
        "Savanna": ["Edelmetallf\u00f6rderer", "Landwirtschaft", "Finanzen", "Stromerzeuger"],
    }.get(country_name, candidates[:4])
    ordered = preferred + [sector for sector in candidates if sector not in preferred]
    focus: dict[str, float] = {}
    for sector in ordered:
        if len(focus) >= 4:
            break
        uniqueness_bonus = 0.08 if sector not in used_focuses else 0.0
        base = 1.18 + uniqueness_bonus if sector in preferred else 1.08
        focus[sector] = base + ((len(focus) % 3) * 0.04)
    return focus


def _initial_country_product_focus(sector_focus: dict[str, float]) -> dict[str, float]:
    products: dict[str, float] = {}
    for sector in sector_focus:
        for code in SECTOR_OUTPUTS.get(sector, [])[:3]:
            products[code] = 1.10
    return products


def _country_sector_bonus(daten: ModuleType, country: str, sector: str) -> float:
    macro = daten.makro.get(country, {})
    profile = macro.get("economic_profile", {})
    rating = str(macro.get("rating", DEFAULT_RATING))
    rating_strength = _clamp(1.05 - default_probability(rating) * 0.75, 0.72, 1.08)
    return float(profile.get("sector_focus", {}).get(sector, 1.0)) * rating_strength


def _country_demand_weight(daten: ModuleType, country: str, code: str) -> float:
    macro = daten.makro.get(country, {})
    population = float(macro.get("bevoelkerung", 20_000_000.0)) / 20_000_000.0
    growth = 1.0 + max(-0.20, min(0.25, float(macro.get("bip_prozent", 0.02)) * 3.0))
    unemployment_drag = max(0.65, 1.0 - max(0.0, float(macro.get("arbeitslosigkeit", 0.06)) - 0.05) * 2.0)
    rate_drag = max(0.70, 1.0 - max(0.0, float(macro.get("zins", 0.035)) - 0.035) * 4.0)
    profile = macro.get("economic_profile", {})
    focus_bonus = float(profile.get("product_focus", {}).get(code, 1.0))
    if code in DISCRETIONARY_OUTPUTS or code in DISCRETIONARY_COMMODITIES:
        growth *= 1.0 + max(-0.15, float(macro.get("bip_prozent", 0.02)) * 4.0)
        rate_drag *= 0.95
    if code in ESSENTIAL_OUTPUTS or code in ESSENTIAL_COMMODITIES:
        unemployment_drag = max(unemployment_drag, 0.90)
        rate_drag = max(rate_drag, 0.92)
    return max(0.10, population * growth * unemployment_drag * rate_drag * focus_bonus)


def _trade_partner_allocations(
    daten: ModuleType,
    country: str,
    code: str,
    amount: float,
    direction: str,
    partner_base_weights: dict[str, dict[str, float]] | None = None,
) -> dict[str, float]:
    partners = [partner for partner in daten.makro if partner != country]
    if not partners or amount <= 0:
        return {}
    base_weights = (partner_base_weights or {}).get(country, {})
    if base_weights:
        return {partner: amount * share for partner, share in base_weights.items()}
    weights = {}
    for partner in partners:
        partner_macro = daten.makro[partner]
        rating_trust = _rating_trade_trust(str(partner_macro.get("rating", DEFAULT_RATING)))
        weights[partner] = _partner_weight(country, partner) * rating_trust
    total = sum(weights.values())
    if total <= 0:
        equal = amount / len(partners)
        return {partner: equal for partner in partners}
    return {partner: amount * weight / total for partner, weight in weights.items() if weight > 0}


def _weighted_partner_allocations(amount: float, weights: dict[str, float]) -> dict[str, float]:
    if amount <= 0 or not weights:
        return {}
    return {partner: amount * share for partner, share in weights.items() if share > 0}


def _country_trade_capacity(daten: ModuleType, country: str, direction: str) -> float:
    macro = daten.makro.get(country, {})
    rating_trust = _rating_trade_trust(str(macro.get("rating", DEFAULT_RATING)))
    freight = getattr(daten, "processed_products", {}).get("FREIGHT", {})
    freight_shortage = float(freight.get("shortage", 0.0))
    freight_factor = _clamp(1.0 - freight_shortage * 0.65, 0.45, 1.0)
    if direction == "import":
        dependency_drag = max(0.58, 1.0 - float(macro.get("import_dependency", 0.0)) * 0.35)
        base = _clamp(0.42 + rating_trust * 0.34 * freight_factor * dependency_drag, 0.25, 0.82)
        return _clamp(base * shock_multiplier(daten, "trade", f"{country}:import"), 0.05, 1.0)
    export_strength = min(0.40, float(macro.get("export_strength", 0.0)) * 0.16)
    base = _clamp(0.46 + rating_trust * 0.28 * freight_factor + export_strength, 0.28, 0.88)
    return _clamp(base * shock_multiplier(daten, "trade", f"{country}:export"), 0.05, 1.0)


def _partner_base_weights(daten: ModuleType, countries: list[str]) -> dict[str, dict[str, float]]:
    rating_trust = {
        country: _rating_trade_trust(str(daten.makro.get(country, {}).get("rating", DEFAULT_RATING)))
        for country in countries
    }
    weights = {
        country: {
            partner: _partner_weight(country, partner) * rating_trust[partner]
            for partner in countries
            if partner != country
        }
        for country in countries
    }
    for country, partner_weights in weights.items():
        total = sum(partner_weights.values()) or 1.0
        weights[country] = {partner: weight / total for partner, weight in partner_weights.items() if weight > 0}
    return weights


@lru_cache(maxsize=2048)
def _partner_weight(country: str, partner: str) -> float:
    if country in TRADE_PARTNER_WEIGHTS:
        return TRADE_PARTNER_WEIGHTS[country].get(partner, 0.72)
    combined = sum(ord(char) for char in f"{country}:{partner}")
    return 0.58 + ((combined % 35) / 100.0)


@lru_cache(maxsize=64)
def _rating_trade_trust(rating: str) -> float:
    return _clamp(1.05 - default_probability(rating) * 0.65, 0.62, 1.08)


def _main_country_sector(daten: ModuleType, country: str) -> str:
    totals = defaultdict(float)
    for asset in daten.aktien.values():
        if asset.get("land") == country:
            totals[str(asset.get("branche", ""))] += float(asset.get("production_capacity", 0.0))
    return max(totals, key=totals.get) if totals else ""


def _country_names(daten: ModuleType) -> list[str]:
    signature = tuple(getattr(daten, "makro", {}).keys())
    cache = getattr(daten, "_production_country_names_cache", None)
    if isinstance(cache, dict) and cache.get("signature") == signature:
        return cache["countries"]
    countries = list(signature)
    daten._production_country_names_cache = {"signature": signature, "countries": countries}
    return countries


def _processed_product_definitions() -> dict[str, dict]:
    return PROCESSED_PRODUCTS


def _trade_market_cache(daten: ModuleType) -> tuple[tuple[str, ...], dict[str, dict]]:
    commodities = getattr(daten, "rohstoffe", {})
    products = getattr(daten, "processed_products", {})
    signature = (tuple(commodities.keys()), tuple(products.keys()))
    cache = getattr(daten, "_production_trade_market_cache", None)
    if isinstance(cache, dict) and cache.get("signature") == signature:
        return cache["item_codes"], cache["markets"]
    item_codes = tuple(list(commodities) + list(products))
    markets = {code: commodities.get(code) or products.get(code, {}) for code in item_codes}
    daten._production_trade_market_cache = {
        "signature": signature,
        "item_codes": item_codes,
        "markets": markets,
    }
    return item_codes, markets


def _cached_partner_base_weights(daten: ModuleType, countries: list[str]) -> dict[str, dict[str, float]]:
    signature = tuple(
        (country, str(getattr(daten, "makro", {}).get(country, {}).get("rating", DEFAULT_RATING)))
        for country in countries
    )
    cache = getattr(daten, "_production_partner_base_weights_cache", None)
    if isinstance(cache, dict) and cache.get("signature") == signature:
        return cache["weights"]
    weights = _partner_base_weights(daten, countries)
    daten._production_partner_base_weights_cache = {"signature": signature, "weights": weights}
    return weights


def _append_country_history(country: dict, key: str, value: float, date_label: str) -> None:
    history = country.setdefault(key, [])
    history.append((float(value), date_label, ""))
    if len(history) > 900:
        del history[:-900]


def _maybe_rebalance_country_profiles(daten: ModuleType) -> None:
    current_year = getattr(getattr(daten, "datum", None), "year", 1990)
    for country_name, country in daten.makro.items():
        profile = country.get("economic_profile", {})
        last_year = int(profile.get("last_rebalanced_year", current_year))
        if current_year - last_year < 5:
            continue
        focus = dict(profile.get("sector_focus", {}))
        best_sector = _main_country_sector(daten, country_name)
        if best_sector:
            focus[best_sector] = min(1.38, float(focus.get(best_sector, 1.0)) + 0.08)
        weakest = min(focus, key=focus.get) if focus else None
        if weakest and weakest != best_sector:
            focus[weakest] = max(1.02, float(focus[weakest]) - 0.05)
        profile["sector_focus"] = focus
        profile["product_focus"] = _initial_country_product_focus(focus)
        profile["last_rebalanced_year"] = current_year
        if best_sector:
            country["profile_change_news"] = {
                "year": current_year,
                "gaining_sector": best_sector,
                "losing_sector": weakest if weakest != best_sector else "",
            }


def _rebalance_output_mix(
    asset: dict,
    daten: ModuleType,
    opportunity_scores: dict[str, dict[str, float]] | None = None,
) -> None:
    sector = _normalized_sector(str(asset.get("branche", "")))
    allowed_outputs = SECTOR_OUTPUTS.get(sector, [])
    if not allowed_outputs:
        return
    output_mix = _cached_output_mix(asset)
    scores = (opportunity_scores or {}).get(sector) or {code: _output_opportunity_score(code, daten) for code in allowed_outputs}
    if not scores:
        return
    best_code = max(scores, key=scores.get)
    changed = False
    if best_code not in output_mix and len(output_mix) < 3 and scores[best_code] > 0.25:
        donor = min(output_mix, key=output_mix.get)
        shift = min(0.08, max(0.0, output_mix[donor] - 0.12))
        if shift > 0:
            output_mix[donor] -= shift
            output_mix[best_code] = shift
            changed = True
    else:
        donor = min(output_mix, key=lambda code: scores.get(code, 0.0))
        if best_code != donor and scores[best_code] > scores.get(donor, 0.0) + 0.10:
            shift = min(0.045, max(0.0, output_mix[donor] - 0.10))
            if shift > 0:
                output_mix[donor] -= shift
                output_mix[best_code] = output_mix.get(best_code, 0.0) + shift
                changed = True
    if not changed:
        return
    asset["output_mix"] = _normalize_mix(output_mix)
    asset["_output_mix_normalized"] = asset["output_mix"]
    asset["specialization"] = _primary_output(asset["output_mix"])
    asset["specialization_name"] = _output_name(asset["specialization"])
    asset["production_role"] = "extractor" if asset["specialization"] in commodity_definitions() else "processor"


def _opportunity_scores_by_sector(daten: ModuleType) -> dict[str, dict[str, float]]:
    return {
        sector: {code: _output_opportunity_score(code, daten) for code in outputs}
        for sector, outputs in SECTOR_OUTPUTS.items()
    }


def _output_opportunity_score(code: str, daten: ModuleType) -> float:
    market = getattr(daten, "rohstoffe", {}).get(code) or getattr(daten, "processed_products", {}).get(code, {})
    shortage = float(market.get("shortage", 0.0))
    price_pressure = float(market.get("price_pressure", 0.0))
    demand = float(market.get("demand", 100.0))
    supply = max(1.0, float(market.get("supply", market.get("production", 100.0))))
    return _clamp((shortage * 0.65) + (price_pressure * 0.35) + max(0.0, demand / supply - 1.0) * 0.08, 0.0, 1.5)


def _normalize_mix(output_mix: dict) -> dict[str, float]:
    cleaned = {
        str(code): max(0.0, float(share))
        for code, share in dict(output_mix).items()
        if code and float(share) > 0.001
    }
    if not cleaned:
        return {"SDIG": 1.0}
    total = sum(cleaned.values())
    return {code: share / total for code, share in cleaned.items()}


def _cached_output_mix(asset: dict) -> dict[str, float]:
    cached = asset.get("_output_mix_normalized")
    source = asset.get("output_mix") or {asset.get("specialization"): 1.0}
    if isinstance(cached, dict) and cached:
        return cached
    normalized = _normalize_mix(source)
    asset["_output_mix_normalized"] = normalized
    return normalized


def _primary_output(output_mix: dict[str, float]) -> str:
    return max(output_mix, key=output_mix.get)


def opportunity_sector(daten: ModuleType) -> str | None:
    sector_scores = defaultdict(float)
    for sector, outputs in SECTOR_OUTPUTS.items():
        for code in outputs:
            sector_scores[sector] += _output_opportunity_score(code, daten)
    if not sector_scores:
        return None
    best_sector = max(sector_scores, key=sector_scores.get)
    return best_sector if sector_scores[best_sector] > 0.35 else None


def _normalize_input(item: str) -> str:
    return PRODUCT_NAME_TO_CODE.get(item, item)


def _normalized_sector(sector: str) -> str:
    replacements = {
        "Ã–l und Gas": "\u00d6l und Gas",
        "KonsumgÃ¼ter": "Konsumg\u00fcter",
        "EdelmetallfÃ¶rderer": "Edelmetallf\u00f6rderer",
    }
    return replacements.get(sector, sector)


def _output_name(code: str) -> str:
    commodities = commodity_definitions()
    if code in commodities:
        return commodities[code]["name"]
    if code in PROCESSED_PRODUCTS:
        return PROCESSED_PRODUCTS[code]["name"]
    return code


def _item_name(code: str) -> str:
    return _output_name(code)


def _clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))
