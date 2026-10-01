import tomllib
from pathlib import Path

PATH = Path(__file__).resolve().parents[3] / "configs" / "paper.toml"


def load(path=None):
    with open(path or PATH, "rb") as f:
        return tomllib.load(f)
