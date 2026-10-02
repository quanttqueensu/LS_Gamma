import json

import pandas as pd
import pytest

from lsgamma import experiments


@pytest.fixture(autouse=True)
def tmp_root(tmp_path, monkeypatch):
    monkeypatch.setattr(experiments, "ROOT", tmp_path)


def test_start_run_writes_params():
    run = experiments.start_run("demo", {"model": "har", "horizon": 20})
    meta = json.loads((run / "params.json").read_text())
    assert meta["experiment"] == "demo"
    assert meta["config"]["horizon"] == 20
    assert meta["commit"]


def test_save_and_trials():
    first = experiments.start_run("demo", {})
    experiments.save(first, pd.DataFrame({"x": [1, 2]}), "out")
    assert (first / "out.parquet").exists()
    assert experiments.trials("demo") == [first]
    assert experiments.trials("missing") == []


def test_load_config_template():
    cfg = experiments.load_config("TEMPLATE")
    assert "experiment" in cfg and "walk_forward" in cfg
