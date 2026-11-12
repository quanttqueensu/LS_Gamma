import json
import math

import numpy as np
import pandas as pd
import pytest

from lsgamma import experiments
from lsgamma.backtest import config
from lsgamma.pipeline import features
from lsgamma.trading import ledger, runner, shadow
from test_backtest import chain

SPEC = """
[shadow]
start = "2026-09-28"
capital = 100000
min_days = 60

[[book]]
name = "Paper rules"

[[book]]
name = "Broken"
exp = "no-such-card"
variant = "x"

[[book]]
name = "Hourly"
exp = "2026-10-21-signal-times"
variant = "hourly"
placeholder = "Waiting"
"""


class Flat:
    def fit(self, returns):
        return self

    def predict(self, horizon):
        return 0.10


def snap(root, key, when, iv=0.15, parts=("chain", "atm_iv", "features")):
    folder = root / key
    folder.mkdir(parents=True)
    c = chain(pd.Timestamp(when, tz="America/New_York")).assign(iv=iv)
    idx = pd.bdate_range("2021-01-01", when[:10], name="date")
    frames = {"chain": c, "atm_iv": features.atm_iv(c),
              "features": pd.DataFrame({"ret": np.random.default_rng(0).normal(0, 0.01, len(idx))}, index=idx)}
    for p in parts:
        frames[p].to_parquet(folder / f"{p}.parquet")
    return folder


@pytest.fixture
def live(tmp_path, monkeypatch):
    monkeypatch.setitem(runner.FORECASTERS, "garch", Flat)
    monkeypatch.setattr(experiments, "ROOT", tmp_path / "results")
    root = shadow.LIVE
    snap(root, "2026-09-28", "2026-09-28 16:00")
    snap(root, "2026-09-29/0959", "2026-09-29 10:00", iv=math.nan)
    snap(root, "2026-09-29/1240", "2026-09-29 12:41")
    snap(root, "2026-09-30/1015", "2026-09-30 10:15", parts=("features",))
    snap(root, "2026-10-01/1014", "2026-10-01 10:14")
    snap(root, "2026-10-01/1500", "2026-10-01 15:00")
    snap(root, "2026-10-02/1016", "2026-10-02 10:16", iv=math.nan)
    ledger.log("signals", {"date": "2026-10-01", "signal": "short", "ts": "2026-10-01T10:20:00-04:00"})
    spec = tmp_path / "shadow.toml"
    spec.write_text(SPEC)
    return root, spec


def test_plan_picks_the_folder_the_live_run_used(live):
    root, _ = live
    plan = shadow.plan(root, "2026-09-28", config.load())
    assert [shadow.key(root, f) for _, f in plan] == ["2026-09-28", "2026-09-29/1240", "2026-10-01/1014",
                                                      "2026-10-02/1016"]
    assert str(plan[1][0]) == "2026-09-29 12:41:00-04:00"


def test_book_cfg_merges_variant_and_capital():
    cfg = shadow.book_cfg({"exp": "2026-10-16-short-only", "variant": "short_only"}, 123)
    assert cfg["signal"]["long_band"] == -math.inf and cfg["size"]["capital"] == 123
    assert "variants" not in cfg


def test_write_is_strict_json_and_isolates_errors(live, tmp_path):
    root, spec = live
    out = shadow.write(tmp_path / "out.json", spec)
    snap = json.loads(out.read_text(), parse_constant=lambda c: pytest.fail(f"bad JSON constant {c}"))
    paper, broken, hourly = snap["books"]
    assert broken["error"] and "summary" not in broken
    assert hourly["placeholder"] == "Waiting" and "summary" not in hourly
    assert paper["error"] is None and paper["summary"]["days"] == 3
    assert paper["summary"]["skipped"] == 1
    assert len({b["date"] for b in paper["book"]}) == len(paper["book"]) == 3
    assert paper["trades"][0]["action"] == "open" and paper["position"]["side"] == "short"
    assert snap["capital"] == 100000 and [s["folder"] for s in snap["snapshots"]][-1] == "2026-10-02/1016"
    assert not (experiments.ROOT / "registry.parquet").exists()


def test_traded_follows_the_pointer(live, tmp_path, monkeypatch):
    root, spec = live
    books = json.loads(shadow.write(tmp_path / "a.json", spec).read_text())["books"]
    assert [b["traded"] for b in books] == [True, False, False]
    monkeypatch.setattr(shadow.paper, "book", lambda path=None: "no-such-card/x")
    books = json.loads(shadow.write(tmp_path / "b.json", spec).read_text())["books"]
    assert [b["traded"] for b in books] == [False, True, False]


def test_base_book_ignores_the_pointer(tmp_path, monkeypatch):
    path = tmp_path / "paper.toml"
    path.write_text('[strategy]\nbook = "2026-11-02-lower-delta/put20"\n' + config.CONFIGS.joinpath("paper.toml").read_text())
    monkeypatch.setattr(config, "BASE", [path, config.CONFIGS / "backtest.toml"])
    cfg = shadow.book_cfg({"name": "base"}, 250000)
    assert cfg["signal"]["short_band"] == 0.02 and "strategy" not in cfg
