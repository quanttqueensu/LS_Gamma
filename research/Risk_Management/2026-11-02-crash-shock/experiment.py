import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from lsgamma.backtest import config, engine, metrics, report, run, sim
from lsgamma.pipeline import store
from lsgamma.pipeline.store import TZ

NAME = "2026-11-02-crash-shock"  # matches configs/experiments/<NAME>.toml
FIGS = Path(__file__).resolve().parent / "figures"
REF = "2026-10-22-stress-sized-puts/hedged"  # reused, not rerun
CONTEXT = []  # shown in charts only
MULTS = (1.0, 2.0)
HIGH_IV = 0.40  # 1.5x IV beats the 60% floor
CRASH = ("2020-02-15", "2020-04-30")  # March 2020 window
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


def legs(out):
    # each round trip with its opening row
    o, c = metrics.pairs(out["trades"])
    o = o.reset_index(drop=True).add_prefix("open_")
    return pd.concat([o, c.reset_index(drop=True)], axis=1)


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
    axes[0].legend(fontsize=7, frameon=False, loc="upper left")
    return report.save(fig, path)


def standard(sets, folder):
    return [cum_pnl(sets, folder / "cum_pnl.png"), drawdown(sets, folder / "drawdown.png"),
            yearly(sets, folder / "yearly.png"), report.by_reason(sets, folder / "by_reason.png"),
            report.fees(sets, folder / "fees.png")]


def show(folder, name, df):
    df.to_csv(folder / f"{name}.csv", index=False)
    print(f"\n{name}\n{df.round(3).to_string(index=False)}")


IVS = {}


def entry_iv(ts, expiry, strike, right):
    # put IV in the decision chain at entry
    key = (ts, expiry, strike, right)
    if key not in IVS:
        root = engine.snapshots(config.load())
        chain = engine.read(store.folder(pd.Timestamp(ts), root), "chain")
        r = sim.row(chain, expiry, strike, right)
        IVS[key] = np.nan if r is None else float(r["iv"])
    return IVS[key]


def with_iv(rt):
    iv = [entry_iv(*k) for k in zip(rt["open_ts"], rt["open_expiry"], rt["open_strike"],
                                   rt["open_right"])]
    return rt.assign(iv=iv, per=rt["pnl_net"] / rt["open_qty"])


def events(out, kind):
    rt = legs(out)
    if kind == "high_iv_entry":
        return int((with_iv(rt)["iv"] > HIGH_IV).sum())
    return len(rt)


def iv_buckets(sets):
    # contracts and P&L by entry IV, 1x
    rows = []
    for k, by_mult in sets.items():
        rt = with_iv(legs(by_mult[1.0]))
        b = pd.cut(rt["iv"], [0, 0.15, 0.25, HIGH_IV, 5], labels=["<15%", "15-25%", "25-40%", ">40%"])
        g = rt.groupby(b, observed=True).agg(trips=("per", "size"), contracts=("open_qty", "mean"),
                                             per_contract=("per", "mean"), net=("pnl_net", "sum"))
        rows.append(g.assign(book=k).reset_index())
    return pd.concat(rows)


def crash_window(sets):
    # round trips opened in the March 2020 window
    rows = []
    lo, hi = CRASH
    for k, by_mult in sets.items():
        for mult, out in sorted(by_mult.items()):
            rt = legs(out)
            d = pd.to_datetime(rt["open_date"])
            w = rt[(d >= lo) & (d <= hi)]
            rows.append({"book": k, "mult": mult, "entries": len(w), "contracts": int(w["open_qty"].sum()),
                         "max_contracts": int(w["open_qty"].max()) if len(w) else 0,
                         "net": float(w["pnl_net"].sum())})
    return pd.DataFrame(rows)


def contracts_chart(sets, folder):
    fig, ax = plt.subplots(figsize=(7, 3))
    for i, k in enumerate(sets):
        t = sets[k][1.0]["trades"]
        o = t[t["action"] == "open"]
        q = o.groupby(pd.to_datetime(o["date"]).dt.year)["qty"].mean()
        ax.plot(q.index, q.values, "o-", ms=3, color=report.color(i, k), label=k)
    ax.set(title="Average contracts per entry by year, 1x", ylabel="contracts", ylim=(0, None))
    ax.legend(fontsize=7, frameon=False, ncol=4)
    return report.save(fig, folder / "contracts.png")


def crash_chart(win, folder):
    fig, axes = plt.subplots(1, 2, figsize=(7.5, 3))
    one = win[win["mult"] == 1.0]
    axes[0].bar(one["book"], one["contracts"], color=[report.color(i, k) for i, k in enumerate(one["book"])])
    axes[0].set(title="Contracts sold, 15 Feb-30 Apr 2020", ylabel="contracts")
    for j, mult in enumerate(sorted(win["mult"].unique())):
        w = win[win["mult"] == mult]
        x = np.arange(len(w)) + (j - 0.5) * 0.4
        axes[1].bar(x, w["net"], 0.4, label=f"{mult:g}x", alpha=1 if j == 0 else 0.6,
                    color=[report.color(i, k) for i, k in enumerate(w["book"])])
    axes[1].set_xticks(np.arange(len(one)), one["book"])
    axes[1].axhline(0, color="k", lw=0.6)
    axes[1].set(title="Net P&L of those round trips (left 1x, right 2x)", ylabel="USD")
    for ax in axes:
        ax.tick_params(axis="x", labelsize=7)
    return report.save(fig, folder / "march2020.png")


def extra(cfg, sets, folder):
    # sizing by entry IV and March 2020
    show(folder, "iv_buckets", iv_buckets(sets))
    win = crash_window(sets)
    show(folder, "march2020", win)
    return [contracts_chart(sets, folder), crash_chart(win, folder)]


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
