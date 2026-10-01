import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[3] / "results" / "paper"


def load_position():
    path = ROOT / "position.json"
    if not path.exists():
        return None
    return json.loads(path.read_text())


def save_position(pos):
    ROOT.mkdir(parents=True, exist_ok=True)
    (ROOT / "position.json").write_text(json.dumps(pos, default=str, indent=2))


def clear_position():
    (ROOT / "position.json").unlink(missing_ok=True)


def log(name, row):
    ROOT.mkdir(parents=True, exist_ok=True)
    path = ROOT / f"{name}.parquet"
    df = pd.DataFrame([row])
    if path.exists():
        df = pd.concat([pd.read_parquet(path), df], ignore_index=True)
    df.to_parquet(path)


def read_log(name):
    path = ROOT / f"{name}.parquet"
    return pd.read_parquet(path) if path.exists() else pd.DataFrame()


def signal_history(n):
    df = read_log("signals")
    if df.empty:
        return []
    return df["signal"].tail(n).tolist()
