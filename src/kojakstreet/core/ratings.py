"""S&P-style credit ratings, simplified default probabilities and spreads."""

from __future__ import annotations

RATINGS = [
    "AAA",
    "AA+",
    "AA",
    "AA-",
    "A+",
    "A",
    "A-",
    "BBB+",
    "BBB",
    "BBB-",
    "BB+",
    "BB",
    "BB-",
    "B+",
    "B",
    "B-",
    "CCC+",
    "CCC",
    "CCC-",
    "CC",
    "C",
    "D",
]

DEFAULT_RATING = "BBB"
RECOVERY_RATE = 0.40

DEFAULT_PROBABILITIES = {
    "AAA": 0.0005,
    "AA+": 0.0010,
    "AA": 0.0020,
    "AA-": 0.0030,
    "A+": 0.0040,
    "A": 0.0060,
    "A-": 0.0080,
    "BBB+": 0.0120,
    "BBB": 0.0200,
    "BBB-": 0.0300,
    "BB+": 0.0500,
    "BB": 0.0750,
    "BB-": 0.1000,
    "B+": 0.1200,
    "B": 0.1800,
    "B-": 0.2500,
    "CCC+": 0.3000,
    "CCC": 0.4000,
    "CCC-": 0.5500,
    "CC": 0.7000,
    "C": 0.8500,
    "D": 1.0000,
}


def normalize_rating(rating: str | None) -> str:
    return rating if rating in RATINGS else DEFAULT_RATING


def rating_index(rating: str | None) -> int:
    return RATINGS.index(normalize_rating(rating))


def default_probability(rating: str | None) -> float:
    return DEFAULT_PROBABILITIES[normalize_rating(rating)]


def rating_spread(rating: str | None) -> float:
    probability = default_probability(rating)
    expected_loss = probability * (1.0 - RECOVERY_RATE)
    risk_premium = (probability**0.5) * 0.018
    floor = 0.0006
    return floor + expected_loss + risk_premium
