import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from lsgamma import experiments
from lsgamma.backtest import engine, metrics

SPLIT = "2020-01-01"  # robustness halves: 2014-2019, 2020-2024
BASE = "0.55"
COLORS = ["tab:blue", "tab:orange", "tab:green", "tab:red", "tab:purple", "tab:brown"]
STYLE = {1.0: "-", 2.0: "--"}

plt.rcParams.update({"figure.dpi": 150, "font.size": 9, "axes.grid": True,
                     "grid.alpha": 0.3, "axes.spines.top": False, "axes.spines.right": False})


def load(run):
    run = Path(run)
    run = run if run.is_absolute() else experiments.ROOT / run
    out = {k: pd.read_parquet(run / f"{k}.parquet") if (run / f"{k}.parquet").exists()
           else pd.DataFrame() for k in engine.OUTPUTS}
    return {**out, "cfg": json.loads((run / "params.json").read_text())["config"]}


def registry():
    path = experiments.ROOT / "registry.parquet"
    return pd.read_parquet(path) if path.exists() else pd.DataFrame(
        columns=["experiment", "run", "spread_mult", "holdout"])


def same(saved, cur):
    # keys added later count only if switched on
    if isinstance(cur, dict):
        saved = saved if isinstance(saved, dict) else {}
        return all(same(saved.get(k), v) if k in saved else not v
                   for k, v in cur.items() if k != "spread_mult")
    return json.dumps(saved, default=str) == json.dumps(cur, default=str)


def baseline(cfg, holdout=False):
    # first baseline run per mult on the same config
    reg = registry()
    rows = reg[(reg["experiment"] == "baseline") & (reg["holdout"] == holdout)]
    out = {}
    for r in rows.itertuples():
        run = load(r.run)
        if float(r.spread_mult) not in out and same(run["cfg"], cfg):
            out[float(r.spread_mult)] = run
    return out


def stale(cfg, holdout=False):
    want = {cfg["backtest"]["spread_mult"], cfg["backtest"]["stress_mult"]}
    return not want <= set(baseline(cfg, holdout))


def runs(name, holdout=False):
    # latest run per spread multiple
    reg = registry()
    last = reg[(reg["experiment"] == name) & (reg["holdout"] == holdout)]
    last = last.groupby("spread_mult").tail(1)
    return {float(r.spread_mult): load(r.run) for r in last.itertuples()}


def trials(prefix):
    e = registry()["experiment"]
    return int(((e == prefix) | e.str.startswith(prefix + "/")).sum())


def daily(out):
    d = metrics.daily_pnl(out["equity"])
    d.index = pd.to_datetime(d.index)
    return d


def between(df, col, lo, hi):
    if df.empty:
        return df
    t = pd.to_datetime(df[col])
    keep = (t >= pd.Timestamp(lo or "1900")) & (t < pd.Timestamp(hi or "2100"))
    return df[keep]


def round_trips(out):
    t = out["trades"]
    if t.empty:
        return t
    o = t[t["action"] == "open"].reset_index(drop=True)
    c = t[t["action"] == "close"].reset_index(drop=True)
    o = o.iloc[:len(c)]
    return pd.DataFrame({"side": o["side"], "entry_date": o["date"], "exit_date": c["date"],
                         "reason": c["reason"], "premium": o["price"] * 100 * o["qty"],
                         "pnl": c["pnl"], "pnl_net": c["pnl_net"]})


def stats(out, lo=None, hi=None):
    d = daily(out)
    d = d[(d.index >= pd.Timestamp(lo or "1900")) & (d.index < pd.Timestamp(hi or "2100"))]
    c = between(round_trips(out), "exit_date", lo, hi)
    t, h = between(out["trades"], "date", lo, hi), between(out["hedges"], "date", lo, hi)
    return {"pnl": float(d.sum()), "sharpe": metrics.sharpe(d, out["cfg"]["size"]["capital"]),
            "max_dd": metrics.max_drawdown(d), "es_5": metrics.expected_shortfall(d),
            "trades": len(c), "win_rate": float((c["pnl_net"] > 0).mean()) if len(c) else None,
            "gross": float(c["pnl"].sum()) if len(c) else 0.0,
            "option_fees": float(t["commission"].sum()) if len(t) else 0.0,
            "hedge_fees": float(h["commission"].sum()) if len(h) else 0.0,
            "hedge_orders": len(h)}


def table(sets, split=SPLIT):
    # sets: {label: {mult: out}}
    rows = []
    for label, by_mult in sets.items():
        for mult, out in sorted(by_mult.items()):
            for period, lo, hi in (("all", None, None), ("2014-2019", None, split),
                                   ("2020-2024", split, None)):
                rows.append({"label": label, "mult": mult, "period": period,
                             **stats(out, lo, hi)})
    return pd.DataFrame(rows)


def color(i, label):
    return BASE if label == "baseline" else COLORS[i % len(COLORS)]


def save(fig, path):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)
    return path


def cum_pnl(sets, path, title="Cumulative net P&L"):
    fig, ax = plt.subplots(figsize=(7, 3.4))
    for i, (label, by_mult) in enumerate(sets.items()):
        for mult, out in sorted(by_mult.items()):
            d = daily(out).cumsum()
            ax.plot(d.index, d.values, STYLE.get(mult, ":"), color=color(i, label), lw=1.1,
                    label=f"{label} {mult:g}x")
    ax.axhline(0, color="k", lw=0.6)
    ax.set(title=title, ylabel="USD, 1 contract")
    ax.legend(fontsize=7, ncol=2, frameon=False)
    return save(fig, path)


def drawdown(sets, path):
    fig, axes = plt.subplots(2, 1, figsize=(7, 4), sharex=True)
    for ax, mult in zip(axes, (1.0, 2.0)):
        for i, (label, by_mult) in enumerate(sets.items()):
            if mult in by_mult:
                eq = daily(by_mult[mult]).cumsum()
                dd = eq - eq.cummax().clip(lower=0)
                ax.plot(dd.index, dd.values, color=color(i, label), lw=1, label=label)
        ax.set(title=f"Drawdown, {mult:g}x spreads", ylabel="USD")
    axes[0].legend(fontsize=7, frameon=False)
    return save(fig, path)


def yearly(sets, path):
    fig, axes = plt.subplots(1, 2, figsize=(7.5, 3), sharey=True)
    n = len(sets)
    for ax, mult in zip(axes, (1.0, 2.0)):
        for i, (label, by_mult) in enumerate(sets.items()):
            if mult not in by_mult:
                continue
            y = daily(by_mult[mult]).groupby(lambda t: t.year).sum()
            ax.bar(y.index + (i - (n - 1) / 2) * 0.8 / n, y.values, 0.8 / n,
                   color=color(i, label), label=label)
        ax.axhline(0, color="k", lw=0.6)
        ax.set(title=f"Net P&L by year, {mult:g}x", ylabel="USD")
    axes[0].legend(fontsize=7, frameon=False)
    return save(fig, path)


def by_reason(sets, path, mult=1.0):
    rows = []
    for label, by_mult in sets.items():
        rt = round_trips(by_mult[mult]) if mult in by_mult else pd.DataFrame()
        if len(rt):
            g = rt.groupby(["side", "reason"])["pnl_net"].sum()
            rows.append(g.rename(label))
    df = pd.concat(rows, axis=1).fillna(0)
    fig, ax = plt.subplots(figsize=(7, 3))
    df.index = [f"{s} {r}" for s, r in df.index]
    df.plot.barh(ax=ax, color=[color(i, c) for i, c in enumerate(df.columns)], width=0.8)
    ax.axvline(0, color="k", lw=0.6)
    ax.set(title=f"Net P&L by side and exit reason, {mult:g}x", xlabel="USD")
    ax.legend(fontsize=7, frameon=False)
    return save(fig, path)


def fees(sets, path):
    labels, opt, hed = [], [], []
    for label, by_mult in sets.items():
        for mult, out in sorted(by_mult.items()):
            s = stats(out)
            labels.append(f"{label}\n{mult:g}x")
            opt.append(s["option_fees"])
            hed.append(s["hedge_fees"])
    fig, ax = plt.subplots(figsize=(7, 3))
    ax.bar(labels, opt, color="tab:blue", label="option commissions")
    ax.bar(labels, hed, bottom=opt, color="tab:orange", label="hedge commissions")
    ax.set(title="Commissions paid", ylabel="USD", ylim=(0, max(map(sum, zip(opt, hed))) * 1.3))
    ax.tick_params(axis="x", labelsize=7)
    ax.legend(fontsize=7, frameon=False, ncol=2, loc="upper left")
    return save(fig, path)


def standard(sets, folder):
    folder = Path(folder)
    return [cum_pnl(sets, folder / "cum_pnl.png"), drawdown(sets, folder / "drawdown.png"),
            yearly(sets, folder / "yearly.png"), by_reason(sets, folder / "by_reason.png"),
            fees(sets, folder / "fees.png")]
