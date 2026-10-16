"""Save and load snapshots under data/live/<YYYY-MM-DD>/<HHMM>/ (US Eastern)."""

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[3] / "data" / "live"
TZ = "America/New_York"


def now():
    return pd.Timestamp.now(tz=TZ)


def key(asof):
    return f"{asof.date()}/{asof:%H%M}"


def folder(asof, root=None):
    return (root or ROOT) / key(asof)


def save(df, name, asof=None, root=None):
    path = folder(asof or now(), root) / f"{name}.parquet"
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path)
    return path


def load(name, asof=None, root=None):
    """Load a dataset from the latest snapshot at or before `asof` (any time if None)."""
    # old day-only folders sort before that day's runs
    root = root or ROOT
    paths = [*root.glob(f"*/{name}.parquet"), *root.glob(f"*/*/{name}.parquet")]
    folders = sorted((p.parent.relative_to(root).as_posix(), p) for p in paths)
    if asof is not None:
        folders = [(k, p) for k, p in folders if k <= key(asof)]
    if not folders:
        raise FileNotFoundError(f"no snapshot of {name} in {root}")
    return pd.read_parquet(folders[-1][1])
