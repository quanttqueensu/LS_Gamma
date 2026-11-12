import math

import pytest

from lsgamma.backtest import config as research, report
from lsgamma.trading import config

POINTER = '[strategy]\nbook = "2026-11-02-lower-delta/put20"\n'


def write(tmp_path, head=""):
    # repo paper.toml rules, optional pointer on top
    lines = config.PATH.read_text().splitlines()
    if "[strategy]" in lines:
        i = lines.index("[strategy]")
        lines = lines[:i] + lines[i + 2:]
    path = tmp_path / "paper.toml"
    path.write_text(head + "\n".join(lines) + "\n")
    return path


@pytest.fixture
def real(monkeypatch):
    # undo conftest's pointer stub
    monkeypatch.setattr(config, "book", lambda path=None: config.pointer(config.read(path)))


def test_pointer_parsing():
    assert config.pointer({}) is None
    assert config.pointer({"strategy": {"book": ""}}) is None
    assert config.pointer({"strategy": {"book": "a/b"}}) == "a/b"


def test_load_without_pointer_is_paper_toml(tmp_path, real):
    path = write(tmp_path)
    assert config.load(path) == config.read(path)


def test_load_with_pointer_is_the_book(tmp_path, real):
    cfg = config.load(write(tmp_path, POINTER))
    assert cfg["strategy"] == {"book": "2026-11-02-lower-delta/put20"}
    assert {k: v for k, v in cfg.items() if k != "strategy"} == research.variant("2026-11-02-lower-delta", "put20")
    assert cfg["signal"]["short_band"] == -math.inf and cfg["hedge"]["min_shares"] == 10
    assert cfg["backtest"]["put_delta"] == 0.2 and cfg["size"]["capital"] == 250000


@pytest.mark.parametrize("label", ["no-slash", "no-such-card/x", "2026-11-02-lower-delta/nope"])
def test_bad_pointer_raises(tmp_path, real, label):
    with pytest.raises((ValueError, FileNotFoundError, KeyError)):
        config.load(write(tmp_path, f'[strategy]\nbook = "{label}"\n'))


def test_backtests_ignore_the_pointer(tmp_path, monkeypatch):
    base = research.load()
    monkeypatch.setattr(research, "BASE", [write(tmp_path, POINTER), research.CONFIGS / "backtest.toml"])
    cfg = research.load()
    assert "strategy" not in cfg and cfg["signal"]["short_band"] == 0.02
    assert report.same(base, cfg)
