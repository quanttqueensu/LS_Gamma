from __future__ import annotations

import itertools
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

import backtest as bt

TRAIN_DAYS = 756
PURGE_DAYS = 30
TEST_DAYS = 126
STEP_DAYS = 126
OBJECTIVE = "sharpe"


@dataclass(frozen=True)
class Fold:
    idx: int
    train_start: pd.Timestamp
    train_end: pd.Timestamp
    test_start: pd.Timestamp
    test_end: pd.Timestamp

    def as_dict(self):
        return {
            "fold": self.idx,
            "train_start": self.train_start.date(),
            "train_end": self.train_end.date(),
            "test_start": self.test_start.date(),
            "test_end": self.test_end.date(),
        }


def make_folds(days, train=TRAIN_DAYS, purge=PURGE_DAYS,
               test=TEST_DAYS, step=STEP_DAYS) -> list[Fold]:
    days = pd.DatetimeIndex(sorted(days))
    folds, i, n = [], 0, 0
    while True:
        tr_lo = n
        tr_hi = tr_lo + train
        te_lo = tr_hi + purge
        te_hi = te_lo + test
        if te_hi > len(days):
            break
        folds.append(Fold(i, days[tr_lo], days[tr_hi - 1], days[te_lo], days[te_hi - 1]))
        i += 1
        n += step
    return folds


def expand_grid(grid: dict | None) -> list[dict]:
    if not grid:
        return [{}]
    keys = list(grid)
    return [dict(zip(keys, vals)) for vals in itertools.product(*(grid[k] for k in keys))]


def evaluate(data_dir, loaded, start, end, cfg) -> dict:
    trades, daily = bt.run(data_dir, start=start, end=end, loaded=loaded, **cfg)
    if daily.empty:
        return {"days": 0, "sharpe": np.nan, "total_pnl": np.nan,
                "trades": 0, "daily": daily}
    m = bt.metrics(daily, trades)
    m["daily"] = daily
    m["trades_df"] = trades
    return m


def _score(m, objective):
    v = m.get(objective)
    return -np.inf if v is None or not np.isfinite(v) else v


def usable_days(loaded, start=None, end=None):
    points, _, spot, sig = loaded
    days = sorted(set(points["date"]) & set(spot.index) & set(sig.index))
    if start:
        days = [d for d in days if d >= pd.Timestamp(start)]
    if end:
        days = [d for d in days if d <= pd.Timestamp(end)]
    return days


def walk_forward(data_dir, base_cfg=None, grid=None, objective=OBJECTIVE,
                 train=TRAIN_DAYS, purge=PURGE_DAYS, test=TEST_DAYS,
                 step=STEP_DAYS, loaded=None, verbose=True,
                 start=None, end=None):
    base_cfg = dict(base_cfg or {})
    loaded = loaded if loaded is not None else bt.load(data_dir)

    days = usable_days(loaded, start, end)
    folds = make_folds(days, train, purge, test, step)
    if not folds:
        raise RuntimeError(
            f"not enough data for a fold: {len(days)} days, "
            f"need at least {train + purge + test}")

    combos = expand_grid(grid)
    rows, oof = [], []

    for f in folds:
        best, best_cfg, best_score = None, dict(base_cfg), -np.inf
        for extra in combos:
            cfg = {**base_cfg, **extra}
            m = evaluate(data_dir, loaded, f.train_start, f.train_end, cfg)
            s = _score(m, objective)
            if s > best_score:
                best, best_cfg, best_score = m, cfg, s

        te = evaluate(data_dir, loaded, f.test_start, f.test_end, best_cfg)

        row = {
            **f.as_dict(),
            "train_sharpe": best.get("sharpe") if best else None,
            "train_pnl": best.get("total_pnl") if best else None,
            "train_trades": best.get("trades", 0) if best else 0,
            "test_sharpe": te.get("sharpe"),
            "test_pnl": te.get("total_pnl"),
            "test_trades": te.get("trades", 0),
            "test_max_dd": te.get("max_drawdown"),
        }
        for k in (grid or {}):
            row[f"chosen_{k}"] = best_cfg.get(k)
        rows.append(row)

        d = te.get("daily")
        if d is not None and not d.empty:
            d = d.copy()
            d["fold"] = f.idx
            oof.append(d)

        if verbose:
            chosen = "  ".join(f"{k}={best_cfg.get(k)}" for k in (grid or {}))
            print(f"  fold {f.idx:>2}  test {f.test_start.date()} to {f.test_end.date()}  "
                  f"sharpe {row['test_sharpe'] if row['test_sharpe'] is not None else float('nan'):>6.3f}  "
                  f"pnl {row['test_pnl'] if row['test_pnl'] is not None else float('nan'):>+9.0f}  "
                  f"trades {row['test_trades']:>3}  {chosen}")

    folds_df = pd.DataFrame(rows)
    oof_daily = (pd.concat(oof, ignore_index=True).sort_values("date")
                 if oof else pd.DataFrame())
    return folds_df, oof_daily


def summarise(folds_df, oof_daily, capital=bt.CAPITAL, grid=None) -> dict:
    s = folds_df["test_sharpe"].dropna()
    p = folds_df["test_pnl"].dropna()

    out = {
        "folds": len(folds_df),
        "folds_scored": int(len(s)),
        "test_sharpe_mean": round(float(s.mean()), 3) if len(s) else None,
        "test_sharpe_median": round(float(s.median()), 3) if len(s) else None,
        "test_sharpe_std": round(float(s.std()), 3) if len(s) > 1 else None,
        "folds_positive": round(float((p > 0).mean()), 3) if len(p) else None,
        "total_test_pnl": round(float(p.sum()), 2) if len(p) else None,
        "worst_fold_pnl": round(float(p.min()), 2) if len(p) else None,
        "best_fold_pnl": round(float(p.max()), 2) if len(p) else None,
        "total_test_trades": int(folds_df["test_trades"].sum()),
    }

    if not oof_daily.empty:
        r = oof_daily["pnl"] / capital
        eq = capital + oof_daily["pnl"].cumsum()
        dd = ((eq - eq.cummax()) / eq.cummax()).min()
        down = r[r < 0].std()
        out["oof"] = {
            "days": len(oof_daily),
            "total_pnl": round(float(oof_daily["pnl"].sum()), 2),
            "sharpe": round(float(r.mean() / r.std() * np.sqrt(252)), 3) if r.std() else None,
            "sortino": round(float(r.mean() / down * np.sqrt(252)), 3) if down else None,
            "max_drawdown": round(float(dd), 4),
            "pnl_from_options": round(float(oof_daily["pnl_option"].sum()), 2),
            "pnl_from_hedging": round(float(oof_daily["pnl_hedge"].sum()), 2),
            "total_costs": round(float(oof_daily["cost"].sum()), 2),
        }

    for k in (grid or {}):
        col = f"chosen_{k}"
        if col in folds_df:
            vc = folds_df[col].value_counts()
            out.setdefault("parameter_stability", {})[k] = {
                "values": {str(i): int(v) for i, v in vc.items()},
                "modal_share": round(float(vc.iloc[0] / vc.sum()), 3),
            }

    return out


HOLDOUT_START = "2024-01-01"


def compare_agents(data_dir, agents: dict, grid=None, **kw):
    loaded = bt.load(data_dir)
    rows, detail = [], {}
    for name, cfg in agents.items():
        print(f"\n{name}")
        folds_df, oof = walk_forward(data_dir, cfg, grid=grid, loaded=loaded, **kw)
        s = summarise(folds_df, oof, grid=grid)
        detail[name] = (folds_df, oof, s)
        rows.append({
            "agent": name,
            "oof_sharpe": s.get("oof", {}).get("sharpe"),
            "oof_pnl": s.get("oof", {}).get("total_pnl"),
            "oof_max_dd": s.get("oof", {}).get("max_drawdown"),
            "fold_sharpe_mean": s["test_sharpe_mean"],
            "fold_sharpe_std": s["test_sharpe_std"],
            "folds_positive": s["folds_positive"],
            "trades": s["total_test_trades"],
        })
    return pd.DataFrame(rows), detail


def parse_grid(spec: list[str] | None) -> dict | None:
    if not spec:
        return None
    grid = {}
    for item in spec:
        key, _, vals = item.partition("=")
        grid[key] = [float(v) if "." in v else int(v) for v in vals.split(",")]
    return grid


if __name__ == "__main__":
    import argparse
    import json

    import agents as ag

    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="Data/data")
    ap.add_argument("--agent", default="agent2_hedge",
                    help="agent name from agents.AGENTS, or 'all'")
    ap.add_argument("--grid", nargs="*", default=None,
                    help="e.g. band_short=0.05,0.10,0.15")
    ap.add_argument("--objective", default=OBJECTIVE)
    ap.add_argument("--train", type=int, default=TRAIN_DAYS)
    ap.add_argument("--purge", type=int, default=PURGE_DAYS)
    ap.add_argument("--test", type=int, default=TEST_DAYS)
    ap.add_argument("--step", type=int, default=STEP_DAYS)
    ap.add_argument("--start", default=None)
    ap.add_argument("--end", default="2023-12-31",
                    help="last usable day; defaults to just before the holdout")
    ap.add_argument("--allow-holdout", action="store_true",
                    help="permit folds to test inside the reserved window")
    ap.add_argument("--save", default=None)
    a = ap.parse_args()

    grid = parse_grid(a.grid)
    if a.allow_holdout:
        a.end = None
        print("WARNING: folds may test inside the reserved holdout window")
    pd.set_option("display.width", 220)
    pd.set_option("display.max_columns", None)

    print(f"loading {a.data} ...")

    if a.agent == "all":
        table, detail = compare_agents(
            a.data, ag.AGENTS, grid=grid, objective=a.objective,
            train=a.train, purge=a.purge, test=a.test, step=a.step,
            start=a.start, end=a.end)
        print("\nout-of-fold comparison")
        print(table.to_string(index=False))
        if a.save:
            Path(a.save).parent.mkdir(parents=True, exist_ok=True)
            table.to_csv(f"{a.save}_comparison.csv", index=False)
            for name, (f, o, _) in detail.items():
                f.to_csv(f"{a.save}_{name}_folds.csv", index=False)
                if not o.empty:
                    o.to_parquet(f"{a.save}_{name}_oof.parquet", index=False)
    else:
        cfg = ag.AGENTS.get(a.agent, {})
        loaded = bt.load(a.data)
        days = usable_days(loaded, a.start, a.end)
        folds = make_folds(days, a.train, a.purge, a.test, a.step)
        print(f"{len(days)} usable days ending {days[-1].date() if days else 'n/a'}, "
              f"{len(folds)} folds "
              f"(train {a.train}, purge {a.purge}, test {a.test}, step {a.step})\n")

        folds_df, oof = walk_forward(a.data, cfg, grid=grid, objective=a.objective,
                                     train=a.train, purge=a.purge, test=a.test,
                                     step=a.step, loaded=loaded,
                                     start=a.start, end=a.end)
        print(f"\n{a.agent}")
        print(json.dumps(summarise(folds_df, oof, grid=grid), indent=2, default=str))
        print("\nfold detail")
        cols = [c for c in folds_df.columns if c not in ("train_start", "train_end")]
        print(folds_df[cols].to_string(index=False))

        if a.save:
            Path(a.save).parent.mkdir(parents=True, exist_ok=True)
            folds_df.to_csv(f"{a.save}_folds.csv", index=False)
            if not oof.empty:
                oof.to_parquet(f"{a.save}_oof.parquet", index=False)
            print(f"\nsaved {a.save}_folds.csv")