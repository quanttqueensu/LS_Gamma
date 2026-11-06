import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

import pytest


@pytest.fixture(autouse=True)
def desk_snapshot(tmp_path, monkeypatch):
    # tests must never touch research/desk.json or the real paper ledger
    from lsgamma.hub import desk
    from lsgamma.trading import ledger
    monkeypatch.setattr(desk, "OUT", tmp_path / "desk.json")
    monkeypatch.setattr(ledger, "ROOT", tmp_path / "paper")
    from lsgamma.trading import shadow
    monkeypatch.setattr(shadow, "OUT", tmp_path / "shadow.json")
    monkeypatch.setattr(shadow, "LIVE", tmp_path / "live")
