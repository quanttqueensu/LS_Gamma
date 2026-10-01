from lsgamma.signals import SIGNALS
from lsgamma.signals.vrp_band import decide

CFG = {"signal": {"long_band": 0.05, "short_band": -0.02}}


def test_edges_are_flat():
    assert decide(0.05, 0.0, CFG) == "flat"
    assert decide(0.0, 0.02, CFG) == "flat"


def test_beyond_edges():
    assert decide(0.0501, 0.0, CFG) == "long"
    assert decide(0.0, 0.0201, CFG) == "short"


def test_inside_band_is_flat():
    assert decide(0.20, 0.20, CFG) == "flat"


def test_registry():
    assert SIGNALS["vrp_band"] is decide
