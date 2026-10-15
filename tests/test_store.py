import pandas as pd
import pytest

from lsgamma.pipeline import store


def at(s):
    return pd.Timestamp(s, tz="America/New_York")


@pytest.fixture(autouse=True)
def root(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "ROOT", tmp_path)
    return tmp_path


def df(x):
    return pd.DataFrame({"x": [x]})


def test_saves_by_date_and_time(root):
    path = store.save(df(1), "chain", at("2026-10-01 10:15"))
    assert path == root / "2026-10-01" / "1015" / "chain.parquet"


def test_load_latest_at_or_before(root):
    for i, t in enumerate(["2026-10-01 10:15", "2026-10-01 11:15", "2026-10-02 10:15"]):
        store.save(df(i), "chain", at(t))
    assert store.load("chain")["x"].iloc[0] == 2
    assert store.load("chain", at("2026-10-01 12:00"))["x"].iloc[0] == 1
    assert store.load("chain", at("2026-10-01 11:15"))["x"].iloc[0] == 1
    with pytest.raises(FileNotFoundError):
        store.load("chain", at("2026-10-01 10:00"))


def test_old_day_folders_still_load(root):
    (root / "2026-09-29").mkdir()
    df(0).to_parquet(root / "2026-09-29" / "chain.parquet")
    assert store.load("chain")["x"].iloc[0] == 0
    store.save(df(1), "chain", at("2026-09-29 10:15"))
    assert store.load("chain")["x"].iloc[0] == 1
