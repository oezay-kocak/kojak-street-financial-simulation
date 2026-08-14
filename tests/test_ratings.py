from __future__ import annotations

from kojakstreet.core.ratings import default_probability, rating_spread


def test_rating_default_probabilities_and_spreads_rise_with_credit_risk() -> None:
    assert default_probability("AAA") < default_probability("BBB") < default_probability("B") < default_probability("CCC")
    assert rating_spread("AAA") < rating_spread("BBB") < rating_spread("B") < rating_spread("CCC")
