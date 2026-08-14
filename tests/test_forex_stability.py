from __future__ import annotations


def test_forex_normal_noise_is_small_relative_to_crisis_move() -> None:
    base_noise = 0.0016
    crisis_move = 0.0065

    assert crisis_move > base_noise * 4
