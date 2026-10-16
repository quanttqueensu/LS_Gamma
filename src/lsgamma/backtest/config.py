import tomllib
from pathlib import Path

from lsgamma import experiments

CONFIGS = Path(__file__).resolve().parents[3] / "configs"
BASE = [CONFIGS / "paper.toml", CONFIGS / "backtest.toml"]
PINNED = ["holdout_start", "first_day"]  # [backtest] keys no experiment sets


def read(path):
    with open(path, "rb") as f:
        return tomllib.load(f)


def merge(base, over):
    out = dict(base)
    for k, v in over.items():
        out[k] = merge(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else v
    return out


def check_pins(over, name):
    fixed = [f"[history].{k}" for k in over.get("history", {}) if k != "version"]
    fixed += [f"[backtest].{k}" for k in over.get("backtest", {}) if k in PINNED]
    if fixed:
        raise SystemExit(f"{name}.toml sets {', '.join(fixed)}; these are fixed in "
                         "configs/backtest.toml (history settings change only with a new version)")


def load(exp=None):
    cfg = {}
    for path in BASE:
        cfg = merge(cfg, read(path))
    if not exp:
        return cfg
    over = experiments.load_config(exp)
    check_pins(over, exp)
    return merge(cfg, over)
