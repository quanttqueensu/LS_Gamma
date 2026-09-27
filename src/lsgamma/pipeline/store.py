"""Save and load daily snapshots under data/live/<YYYY-MM-DD>/."""

from datetime import date
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[3] / "data" / "live"


def save(df, name, day=None):
    folder = ROOT / str(day or date.today())
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{name}.parquet"
    df.to_parquet(path)
    return path


def load(name, day=None):
    """Load a dataset from `day`, or from the latest snapshot that has it."""
    if day is not None:
        return pd.read_parquet(ROOT / str(day) / f"{name}.parquet")
    for folder in sorted(ROOT.glob("*"), reverse=True):
        path = folder / f"{name}.parquet"
        if path.exists():
            return pd.read_parquet(path)
    raise FileNotFoundError(f"no snapshot of {name} in {ROOT}")
