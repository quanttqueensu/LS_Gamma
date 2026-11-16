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


def live(cfg, strategy):
    # live-only account size over [size] capital
    cap = strategy.get("capital")
    size = {**cfg["size"], "capital": cap} if cap else cfg["size"]
    return {**cfg, "size": size, **({"strategy": strategy} if strategy else {})}


def load(path=None):
    # the live book's config, else paper.toml
    raw, label = read(path), book(path)
    strategy = {**raw.get("strategy", {}), "book": label} if label else raw.get("strategy", {})
    if not label:
        return live(raw, strategy)
    exp, name = label.split("/")
    return live(research.variant(exp, name), strategy)


def backtest_defaults():
    return research.read(research.CONFIGS / "backtest.toml")["backtest"]
