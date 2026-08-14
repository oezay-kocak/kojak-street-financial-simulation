"""Simulation random seed helpers."""

from __future__ import annotations

import random
from typing import Any

import numpy as np


def set_simulation_seed(daten: Any, seed: int | None) -> None:
    if seed is None:
        return
    seed = int(seed)
    random.seed(seed)
    np.random.seed(seed)
    setattr(daten, "simulation_seed", seed)
