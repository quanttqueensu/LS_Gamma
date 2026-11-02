import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from lsgamma.backtest import config, metrics, report, run

NAME = "2026-11-02-lower-delta"  # matches configs/experiments/<NAME>.toml
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
    axes[0].legend(fontsize=7, frameon=False, loc="lower left")
    return report.save(fig, path)


def standard(sets, folder):
    return [cum_pnl(sets, folder / "cum_pnl.png"), drawdown(sets, folder / "drawdown.png"),
            yearly(sets, folder / "yearly.png"), report.by_reason(sets, folder / "by_reason.png"),
            report.fees(sets, folder / "fees.png")]


def show(folder, name, df):
    df.to_csv(folder / f"{name}.csv", index=False)
    print(f"\n{name}\n{df.round(3).to_string(index=False)}")


DELTA = {"hedged": 0.25, "put20": 0.20, "put15": 0.15}


def events(out, kind):
    # round_trip: closed positions
    return len(report.round_trips(out))


def per_trip(out):
    # each round trip with contracts and net per contract
    lg = legs(out)
    return pd.DataFrame({"year": pd.to_datetime(lg["date"]).dt.year, "qty": lg["open_qty"],
                         "net": lg["pnl_net"], "per": lg["pnl_net"] / lg["open_qty"],
                         "credit": lg["open_price"] * 100, "reason": lg["reason"]})


def trips(sets):
    rows = []
    for k, by_mult in sets.items():
        r = per_trip(by_mult[1.0])
        rows.append({"book": k, "delta": DELTA[k], "round_trips": len(r),
                     "mean_qty": r["qty"].mean(), "median_qty": r["qty"].median(),
                     "max_qty": int(r["qty"].max()), "mean_credit_per_contract": r["credit"].mean(),
                     "net_per_contract": r["net"].sum() / r["qty"].sum(),
                     "mean_net_per_contract": r["per"].mean(),
                     "se_per_contract": r["per"].std() / np.sqrt(len(r)),
                     "stops": int((r["reason"] == "stop").sum()),
                     "profits": int((r["reason"] == "profit").sum())})
    return pd.DataFrame(rows)


def per_contract(df, path):
    fig, ax = plt.subplots(figsize=(6, 3))
    x = np.arange(len(df))
    ax.bar(x, df["mean_net_per_contract"], 0.6, yerr=df["se_per_contract"], capsize=4,
           color=[report.color(i, b) for i, b in enumerate(df["book"])])
    ax.set_xticks(x, [f"{b} ({d:g} delta)" for b, d in zip(df["book"], df["delta"])])
    ax.axhline(0, color="k", lw=0.6)
    ax.set(title="Net P&L per contract per round trip, 1x (mean, 1 s.e.)", ylabel="USD")
    return report.save(fig, path)


def contracts(sets, path):
    fig, ax = plt.subplots(figsize=(7, 3))
    for i, (k, by_mult) in enumerate(sets.items()):
        y = per_trip(by_mult[1.0]).groupby("year")["qty"].median()
        ax.plot(y.index, y.values, "o-", color=report.color(i, k), lw=1.1, ms=3, label=k)
    ax.set(title="Median contracts per entry, by exit year", ylabel="contracts")
    ax.legend(fontsize=7, frameon=False)
    return report.save(fig, path)


def costs(sets):
    rows = []
    for k, by_mult in sets.items():
        s1, s2 = (report.stats(by_mult[m]) for m in MULTS)
        rows.append({"book": k, "commissions": s1["option_fees"] + s1["hedge_fees"],
                     "spread_1x": s1["pnl"] - s2["pnl"] + (s1["option_fees"] + s1["hedge_fees"]
                                                           - s2["option_fees"] - s2["hedge_fees"])})
    return pd.DataFrame(rows)


def cost_chart(df, path):
    fig, ax = plt.subplots(figsize=(6, 3))
    x = np.arange(len(df))
    ax.bar(x - 0.2, df["commissions"], 0.4, label="commissions, 1x", color="tab:gray")
    ax.bar(x + 0.2, df["spread_1x"], 0.4, label="spread paid at 1x (2x minus 1x P&L)",
           color="tab:orange")
    ax.set_xticks(x, df["book"])
    ax.set(title="Trading costs, 2014-06 to 2024-12", ylabel="USD")
    ax.legend(fontsize=7, frameon=False)
    return report.save(fig, path)


def extra(cfg, sets, folder):
    # per-contract P&L, size and costs by delta
    df = trips(sets)
    show(folder, "trips", df)
    c = costs(sets)
    show(folder, "costs", c)
    return [per_contract(df, folder / "per_contract.png"),
            contracts(sets, folder / "contracts.png"), cost_chart(c, folder / "costs.png")]


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
