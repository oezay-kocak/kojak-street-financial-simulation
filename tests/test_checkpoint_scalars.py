"""Simple scalar dispatch must retain the tagged and NumPy wire protocol."""
from datetime import datetime

import numpy as np

from kojakstreet.core.checkpoints import decode, encode


def test_scalar_shortcut_preserves_numpy_subclasses_and_container_tags():
    class FloatSubclass(float):
        pass

    subclass = FloatSubclass(3.5)
    values = [None, True, 123, 3.5, "text", np.float64(3.5), np.int64(123), np.str_("text")]
    encoded = encode(values)
    assert encoded == [None, True, 123, 3.5, "text", 3.5, 123, "text"]
    assert [type(item) for item in encoded] == [type(None), bool, int, float, str, float, int, str]
    assert encode(subclass) is subclass
    value = {7: (datetime(1990, 1, 1), {"text"}), "array": np.array([1, 2], dtype=np.int64)}  # noqa: DTZ001 -- simulation dates are naive
    encoded = encode(value)
    assert encoded == {
        "__type__": "mapping", "items": [
            [7, {"__type__": "tuple", "items": [
                {"__type__": "datetime", "value": "1990-01-01T00:00:00"},
                {"__type__": "set", "items": ["text"]},
            ]}],
            ["array", {"__type__": "ndarray", "dtype": "int64", "items": [1, 2]}],
        ],
    }
    restored = decode(encoded)
    assert restored[7] == value[7]
    assert np.array_equal(restored["array"], value["array"])
