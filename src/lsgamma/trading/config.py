import tomllib
from pathlib import Path

from lsgamma.backtest import config as research

PATH = Path(__file__).resolve().parents[3] / "configs" / "paper.toml"


def read(path=None):
    with open(path or PATH, "rb") as f:
        return tomllib.load(f)


def pointer(cfg):
    # [strategy] book = "exp/variant"
    return cfg.get("strategy", {}).get("book") or None


def book(path=None):
    return pointer(read(path))


def load(path=None):
    # the live book's config, else paper.toml
    label = book(path)
    if not label:
        return read(path)
    exp, name = label.split("/")
    return {**research.variant(exp, name), "strategy": {"book": label}}


def backtest_defaults():
    return research.read(research.CONFIGS / "backtest.toml")["backtest"]
