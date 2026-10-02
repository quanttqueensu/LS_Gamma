import json
import subprocess
import tomllib
from datetime import datetime
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[2]
ROOT = REPO / "results" / "research"
CONFIGS = REPO / "configs" / "experiments"


def load_config(name):
    with open(CONFIGS / f"{name}.toml", "rb") as f:
        return tomllib.load(f)


def commit():
    try:
        out = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=REPO,
                             capture_output=True, text=True, check=True)
        dirty = subprocess.run(["git", "status", "--porcelain"], cwd=REPO,
                               capture_output=True, text=True).stdout.strip()
        return out.stdout.strip() + ("-dirty" if dirty else "")
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def start_run(name, cfg):
    run = ROOT / name / datetime.now().strftime("%Y%m%d-%H%M%S")
    run.mkdir(parents=True, exist_ok=False)
    meta = {"experiment": name, "started": datetime.now().isoformat(timespec="seconds"),
            "commit": commit(), "config": cfg}
    (run / "params.json").write_text(json.dumps(meta, indent=2, default=str))
    return run


def save(run, df, name):
    path = run / f"{name}.parquet"
    df.to_parquet(path)
    return path


def trials(name):
    folder = ROOT / name
    return sorted(p for p in folder.iterdir() if p.is_dir()) if folder.exists() else []
