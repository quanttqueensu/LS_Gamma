import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from lsgamma.backtest import config, metrics, report, run

NAME = "2026-11-02-vrp-hedge"  # matches configs/experiments/<NAME>.toml
FIGS = Path(__file__).resolve().parent / "figures"
REF = "2026-10-22-stress-sized-puts/hedged"  # reused, not rerun
CONTEXT = ["2026-10-22-stress-sized-puts/unhedged"]  # shown in charts only
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


def fees(sets, path):
    # report.fees, x labels clear of each other
    labels, opt, hed = [], [], []
    for label, by_mult in sets.items():
        for mult, out in sorted(by_mult.items()):
            s = report.stats(out)
            labels.append(f"{label} {mult:g}x")
            opt.append(s["option_fees"])
            hed.append(s["hedge_fees"])
    fig, ax = plt.subplots(figsize=(7, 3.2))
    ax.bar(labels, opt, color="tab:blue", label="option commissions")
    ax.bar(labels, hed, bottom=opt, color="tab:orange", label="hedge commissions")
    ax.set(title="Commissions paid", ylabel="USD", ylim=(0, max(map(sum, zip(opt, hed))) * 1.3))
    ax.tick_params(axis="x", labelsize=7, rotation=30)
    ax.legend(fontsize=7, frameon=False, ncol=2, loc="upper left")
    return report.save(fig, path)


def standard(sets, folder):
    return [cum_pnl(sets, folder / "cum_pnl.png"), drawdown(sets, folder / "drawdown.png"),
            yearly(sets, folder / "yearly.png"), report.by_reason(sets, folder / "by_reason.png"),
            fees(sets, folder / "fees.png")]


def show(folder, name, df):
    df.to_csv(folder / f"{name}.csv", index=False)
    print(f"\n{name}\n{df.round(3).to_string(index=False)}")


def bare(rt):
    col = rt["open_unhedged"] if "open_unhedged" in rt else pd.Series(False, index=rt.index)
    return col.fillna(False).astype(bool)


def events(out, kind):
    # unhedged: round trips entered without a hedge
    if kind == "round_trip":
        return len(report.round_trips(out))
    return int(bare(legs(out)).sum())


def split(cfg, sets):
    rows = []
    for k in cfg["variants"]:
        rt = legs(sets[k][1.0])
        for flag, g in rt.groupby(bare(rt)):
            rows.append({"book": k, "hedge": "none" if flag else "daily", "trips": len(g),
                         "contracts": g["open_qty"].mean(), "net": g["pnl_net"].sum(),
                         "per_contract": (g["pnl_net"] / g["open_qty"]).mean()})
    return pd.DataFrame(rows)


def by_vrp(cfg, sets):
    # reference books split by VRP at entry
    cut = cfg["variants"][cfg["pass"]["primary"]]["backtest"]["vrp_unhedge"]
    rows = []
    for k in ("hedged", "unhedged_ref"):
        out = sets[k][1.0]
        sig = out["signals"][["ts", "vrp"]].rename(columns={"ts": "open_ts"})
        rt = legs(out).merge(sig, on="open_ts", how="left")
        for flag, g in rt.groupby(rt["vrp"] > cut):
            rows.append({"book": k, "vrp": f"> {cut:g}" if flag else f"<= {cut:g}",
                         "trips": len(g), "net": g["pnl_net"].sum(),
                         "per_contract": (g["pnl_net"] / g["open_qty"]).mean()})
    return pd.DataFrame(rows)


def vrp_chart(cfg, sets, df, folder):
    p = cfg["pass"]["primary"]
    fig, axes = plt.subplots(1, 2, figsize=(7.5, 3))
    piv = df.pivot(index="vrp", columns="book", values="per_contract")
    piv.plot.bar(ax=axes[0], color=["tab:blue", "tab:orange"], width=0.7)
    axes[0].axhline(0, color="k", lw=0.6)
    axes[0].set(title="Reference books: net per contract\nby VRP at entry, 1x", ylabel="USD",
                xlabel="VRP at entry")
    axes[0].tick_params(axis="x", rotation=0)
    axes[0].legend(fontsize=7, frameon=False)
    rt = legs(sets[p][1.0])
    n = rt[bare(rt)].groupby(pd.to_datetime(rt["open_date"]).dt.year).size()
    axes[1].bar(n.index, n.values, color="tab:green")
    axes[1].set(title=f"Unhedged entries per year ({p}, 1x)", ylabel="entries")
    return report.save(fig, folder / "vrp_split.png")


def extra(cfg, sets, folder):
    # hedge split and VRP mechanism check
    show(folder, "split", split(cfg, sets))
    df = by_vrp(cfg, sets)
    show(folder, "by_vrp", df)
    return [vrp_chart(cfg, sets, df, folder)]


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
