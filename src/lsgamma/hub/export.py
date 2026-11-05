import json
import re
from pathlib import Path

import pandas as pd

from lsgamma import experiments

OUT = experiments.REPO / "research" / "registry.csv"
COLUMNS = ["card", "variant", "run", "commit", "start", "end", "holdout", "spread_mult",
           "pnl", "sharpe", "max_dd", "es_5", "trades", "win_rate"]
STAMP = re.compile(r"\d{8}-\d{6}")


def backtest_rows(root):
    path = root / "registry.parquet"
    if not path.exists():
        return pd.DataFrame(columns=COLUMNS)
    reg = pd.read_parquet(path)
    parts = reg["experiment"].str.split("/", n=1)
    reg["card"] = parts.str[0]
    reg["variant"] = parts.str[1].fillna("")
    reg["run"] = reg["run"].str.rsplit("/", n=1).str[-1]
    return reg[COLUMNS]


def folder_rows(root, known):
    rows = []
    for card in sorted(p for p in root.iterdir() if p.is_dir() and p.name not in known):
        for run in sorted(p for p in card.iterdir() if p.is_dir() and STAMP.fullmatch(p.name)):
            meta = run / "params.json"
            sha = json.loads(meta.read_text()).get("commit", "") if meta.exists() else ""
            rows.append({"card": card.name, "variant": "", "run": run.name, "commit": sha})
    return pd.DataFrame(rows, columns=COLUMNS)


def export(root=None, out=OUT):
    root = Path(root or experiments.ROOT)
    bt = backtest_rows(root)
    rows = pd.concat([df for df in (bt, folder_rows(root, set(bt["card"]))) if len(df)],
                     ignore_index=True)
    rows = rows.sort_values(["card", "variant", "run", "spread_mult"]).round(4)
    out.parent.mkdir(parents=True, exist_ok=True)
    rows.to_csv(out, index=False)
    return rows


if __name__ == "__main__":
    rows = export()
    print(f"{len(rows)} trials from {rows['card'].nunique()} experiments -> {OUT}")
