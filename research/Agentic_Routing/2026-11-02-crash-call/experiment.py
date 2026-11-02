import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from lsgamma.backtest import config, report, run

NAME = "2026-11-02-crash-call"  # matches configs/experiments/<NAME>.toml
FIGS = Path(__file__).resolve().parent / "figures"
REF = "2026-10-22-stress-sized-puts/hedged"  # reused, not rerun
CONTEXT = []  # shown in charts only
MULTS = (1.0, 2.0)
LIMIT = 87500.0  # 35% stress budget of $250k
RULES = {
    "higher": lambda v, r, x: v > r,
    "less_severe": lambda v, r, x: abs(v) < abs(r),
    "abs_within": lambda v, r, x: abs(v) <= x * abs(r),
    "not_below": lambda v, r, x: v >= r - x,
    "above": lambda v, r, x: v > x,  # absolute
    "at_most": lambda v, r, x: v <= x,  # absolute
}


def load_sets(cfg, holdout=False):
    ref = report.runs(REF, holdout)
    if not ref:
        raise SystemExit(f"no {'hold-out ' if holdout else ''}runs for {REF}")
    labels = [cfg["pass"]["primary"]] if holdout else list(cfg["variants"])
    ctx = {} if holdout else {k.split("/")[-1] + "_ref": report.runs(k) for k in CONTEXT}
    return {"hedged": ref, **ctx, **{v: report.runs(f"{NAME}/{v}", holdout) for v in labels}}


def value(tab, label, mult, period, metric):
    row = tab[(tab["label"] == label) & (tab["mult"] == mult) & (tab["period"] == period)]
    return float(row[metric].iloc[0])


def checks(cfg, tab, holdout=False):
    p, rows = cfg["pass"], []
    for c in p["check"]:
        if holdout and c["period"] != "all":
            continue
        for m in MULTS:
            v = value(tab, p["primary"], m, c["period"], c["metric"])
            r = value(tab, p["against"], m, c["period"], c["metric"])
            ok = RULES[c["rule"]](v, r, c.get("value", 0.0))
            rows.append({"check": f"{c['metric']} {c['rule']} {c.get('value', '')} ({c['period']})",
                         "mult": m, "variant": v, "against": r, "pass": ok})
    return pd.DataFrame(rows)


KEY = ["entry_ts", "right", "strike", "expiry"]


def legs(out):
    # round trips by entry time and contract
    t = out["trades"]
    o = t[t["action"] == "open"].assign(entry_ts=lambda x: x["ts"])
    c = t[t["action"] == "close"]
    if "crash" not in o:
        o = o.assign(crash=False)
    o = o[KEY + ["date", "qty", "price", "crash"]].add_prefix("open_")
    o = o.rename(columns={f"open_{k}": k for k in KEY})
    return c.merge(o, on=KEY, how="left", validate="one_to_one").assign(
        leg=lambda x: np.where(x["open_crash"].fillna(False).astype(bool), "crash call", "put"))


def verdict(cfg, sets, chk, holdout=False):
    p = cfg["pass"]
    if p.get("min_events", 0) and not holdout:
        n = events(sets[p["primary"]][1.0], p["event"])
        if n < p["min_events"]:
            return f"INCONCLUSIVE ({n} {p['event']} < {p['min_events']})"
    return "PASSED" if chk["pass"].all() else "FAILED"


def cum_pnl(sets, path):
    fig, ax = plt.subplots(figsize=(7, 3.4))
    for i, (label, by_mult) in enumerate(sets.items()):
        for mult, out in sorted(by_mult.items()):
            d = report.daily(out).cumsum()
            ax.plot(d.index, d.values, report.STYLE.get(mult, ":"), color=report.color(i, label),
                    lw=1.1, label=f"{label} {mult:g}x")
    ax.axhline(0, color="k", lw=0.6)
    ax.set(title="Cumulative net P&L", ylabel="USD")
    ax.legend(fontsize=7, ncol=2, frameon=False)
    return report.save(fig, path)


def drawdown(sets, path):
    fig, axes = plt.subplots(2, 1, figsize=(7, 4), sharex=True)
    for ax, mult in zip(axes, MULTS):
        for i, (label, by_mult) in enumerate(sets.items()):
            if mult in by_mult:
                eq = report.daily(by_mult[mult]).cumsum()
                ax.plot(eq.index, (eq - eq.cummax().clip(lower=0)).values,
                        color=report.color(i, label), lw=1, label=label)
        ax.axhline(-LIMIT, color="tab:red", lw=0.8, ls=":")
        ax.set(title=f"Drawdown, {mult:g}x spreads (dotted: stress budget)", ylabel="USD")
    axes[0].legend(fontsize=7, frameon=False, ncol=3)
    return report.save(fig, path)


def yearly(sets, path):
    fig, axes = plt.subplots(1, 2, figsize=(7.5, 3), sharey=True)
    n = len(sets)
    for ax, mult in zip(axes, MULTS):
        for i, (label, by_mult) in enumerate(sets.items()):
            if mult in by_mult:
                y = report.daily(by_mult[mult]).groupby(lambda t: t.year).sum()
                ax.bar(y.index + (i - (n - 1) / 2) * 0.8 / n, y.values, 0.8 / n,
                       color=report.color(i, label), label=label)
        ax.axhline(0, color="k", lw=0.6)
        ax.set(title=f"Net P&L by year, {mult:g}x", ylabel="USD")
    axes[0].legend(fontsize=7, frameon=False, loc="lower left")
    return report.save(fig, path)


def standard(sets, folder):
    return [cum_pnl(sets, folder / "cum_pnl.png"), drawdown(sets, folder / "drawdown.png"),
            yearly(sets, folder / "yearly.png"), by_reason(sets, folder / "vs_hedged.png"),
            report.fees(sets, folder / "fees.png")]


def show(folder, name, df):
    df.to_csv(folder / f"{name}.csv", index=False)
    print(f"\n{name}\n{df.round(3).to_string(index=False)}")


def marginal(sets, k, mult):
    # crash variant minus hedged, daily net P&L
    return (report.daily(sets[k][mult]) - report.daily(sets["hedged"][mult])).fillna(0.0)


def by_reason(sets, path):
    # cumulative P&L vs hedged; leg split unreliable
    fig, axes = plt.subplots(2, 1, figsize=(7, 4), sharex=True)
    for ax, mult in zip(axes, MULTS):
        for i, k in enumerate(sets):
            if k != "hedged":
                d = marginal(sets, k, mult).cumsum()
                ax.plot(d.index, d.values, color=report.color(i, k), lw=1, label=k)
        ax.axhline(0, color="k", lw=0.6)
        ax.set(title=f"Cumulative net P&L minus hedged, {mult:g}x", ylabel="USD")
    axes[0].legend(fontsize=7, frameon=False)
    return report.save(fig, path)


def opens(out):
    t = out["trades"]
    return t[(t["action"] == "open") & t.get("crash", pd.Series(False, index=t.index)).fillna(False)
             .astype(bool)]


def events(out, kind):
    # crash: crash calls opened
    if kind == "round_trip":
        return len(legs(out))
    return len(opens(out))


def split(sets):
    rows = []
    for k, by_mult in sets.items():
        if k == "hedged":
            continue
        for mult, out in sorted(by_mult.items()):
            lg = legs(out)
            cc = lg[lg["leg"] == "crash call"]
            t = out["trades"]
            fees = float(t.loc[t["right"] == "C", "commission"].sum())
            rows.append({"book": k, "mult": mult, "calls": len(cc),
                         "contracts": float(cc["open_qty"].mean()) if len(cc) else 0.0,
                         "premium": float((cc["open_price"] * cc["open_qty"] * 100).sum()),
                         "option_net": float(((cc["price"] - cc["open_price"]) * cc["qty"]
                                              * 100).sum()) - fees,
                         "marginal": float(marginal(sets, k, mult).sum())})
    return pd.DataFrame(rows)


def crash_years(sets, folder):
    keys = [k for k in sets if k != "hedged"]
    fig, axes = plt.subplots(1, 2, figsize=(7.5, 3))
    n = len(keys)
    for i, k in enumerate(keys):
        d = marginal(sets, k, 1.0)
        y = d.groupby(d.index.year).sum()
        c = opens(sets[k][1.0])
        m = c.groupby(pd.to_datetime(c["date"]).dt.year).size()
        for ax, s in zip(axes, (y, m)):
            ax.bar(s.index + (i - (n - 1) / 2) * 0.8 / n, s.values, 0.8 / n,
                   color=report.color(i + 1, k), label=k)
    axes[0].axhline(0, color="k", lw=0.6)
    axes[0].set(title="Net P&L minus hedged, by year, 1x", ylabel="USD")
    axes[1].set(title="Crash calls opened per year", ylabel="calls")
    axes[1].legend(fontsize=7, frameon=False)
    return report.save(fig, folder / "crash_years.png")


def extra(cfg, sets, folder):
    # crash-call cost and effect; calls per year
    show(folder, "legs", split(sets))
    return [crash_years(sets, folder)]


def build(cfg, holdout=False):
    sets = load_sets(cfg, holdout)
    folder = FIGS / "holdout" if holdout else FIGS
    tab = report.table(sets)
    folder.mkdir(parents=True, exist_ok=True)
    tab.to_csv(folder / "table.csv", index=False)
    paths = [cum_pnl(sets, folder / "cum_pnl.png")] if holdout else (
        standard(sets, folder) + extra(cfg, sets, folder))
    chk = checks(cfg, tab, holdout)
    chk.to_csv(folder / "pass_bar.csv", index=False)
    cols = ["label", "mult", "period", "pnl", "sharpe", "max_dd", "es_5", "trades",
            "win_rate", "gross", "option_fees", "hedge_fees", "hedge_orders"]
    print(tab[cols].round(2).to_string(index=False))
    print("\npass bar" + (" (hold-out)" if holdout else ""))
    print(chk.round(2).to_string(index=False))
    print(f"\nverdict: {verdict(cfg, sets, chk, holdout)}")
    print(f"trials: {report.trials(NAME)} (+ baseline {report.trials('baseline')}; "
          f"reference {REF} reused, not rerun)")
    print("figures:", *[p.name for p in paths])


def main():
    p = argparse.ArgumentParser(description=NAME)
    p.add_argument("--report-only", action="store_true", help="rebuild from registered runs")
    p.add_argument("--holdout", action="store_true", help="final run: primary variant, once")
    a = p.parse_args()
    cfg = config.load(NAME)
    if a.holdout and not a.report_only:
        if not report.runs(REF, True):
            raise SystemExit(f"run the {REF} hold-out first; it is the reference")
        for label, rows in run.holdout(NAME, cfg["pass"]["primary"], cfg, config.load()).items():
            print(f"\n{label} (hold-out)\n{run.table(rows)}")
    elif not a.report_only:
        if report.trials(NAME):
            raise SystemExit(f"{NAME} already has trials; use --report-only")
        for label, rows in run.variants(NAME, cfg, cfg["variants"]).items():
            print(f"\n{label}\n{run.table(rows)}")
    build(cfg, a.holdout)


if __name__ == "__main__":
    main()
