import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from lsgamma.backtest import config, engine, metrics, report, run

NAME = "2026-11-02-mv-hedge"  # matches configs/experiments/<NAME>.toml
FIGS = Path(__file__).resolve().parent / "figures"
REF = "2026-10-22-stress-sized-puts/hedged"  # reused, not rerun
CONTEXT = []  # no context books
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


def events(out, kind):
    # round_trip: completed round trips
    return len(report.round_trips(out))


def betas(feats):
    # spot-vol beta the hedge used, each day
    s, days = {"feats": feats}, feats.index[feats.index >= "2014-06-02"]
    days = days[days <= "2024-12-31"]
    return pd.Series([engine.beta(s, engine.at(d.date(), "10:15")) for d in days], index=days)


def beta_chart(b, folder):
    fig, ax = plt.subplots(figsize=(7, 2.8))
    ax.plot(b.index, b.values, color="tab:purple", lw=1)
    ax.axhline(0, color="k", lw=0.6)
    ax.set(title="Spot-vol beta used by the hedge (VIX points per unit SPY return, 1y)",
           ylabel="beta")
    return report.save(fig, folder / "beta.png")


def per_contract(out):
    # hedge shares per open contract, each day
    rt = legs(out)
    eq = out["equity"].assign(date=pd.to_datetime(out["equity"]["date"]))
    n = pd.Series(0.0, index=eq["date"])
    for o, c, q in zip(pd.to_datetime(rt["open_date"]), pd.to_datetime(rt["date"]), rt["open_qty"]):
        n[(n.index >= o) & (n.index < c)] += q
    s = pd.Series(eq["shares"].to_numpy(), index=eq["date"])
    return (-s / n)[n > 0]


def shares_chart(sets, labels, folder):
    fig, ax = plt.subplots(figsize=(7, 2.8))
    rows = []
    for i, label in enumerate(labels):
        y = per_contract(sets[label][1.0]).groupby(lambda t: t.year).mean()
        ax.plot(y.index, y.values, "o-", color=report.color(i, label), lw=1, label=label)
        rows.append({"book": label, **{str(k): v for k, v in y.round(1).items()}})
    ax.set(title="Short shares held per open put contract, yearly mean (1x)", ylabel="shares")
    ax.legend(fontsize=7, frameon=False)
    return report.save(fig, folder / "shares.png"), pd.DataFrame(rows)


def tail(sets, labels):
    # worst-day statistics of daily net P&L
    rows = []
    for label in labels:
        for mult in MULTS:
            d = report.daily(sets[label][mult])
            q = d.quantile(0.05)
            rows.append({"book": label, "mult": mult, "worst": d.min(), "q5": q,
                         "es5": d[d <= q].mean(), "std": d.std(), "worst20": d.nsmallest(20).sum()})
    return pd.DataFrame(rows)


def tail_chart(sets, labels, folder):
    fig, ax = plt.subplots(figsize=(7, 3))
    for i, label in enumerate(labels):
        d = report.daily(sets[label][1.0]).sort_values().iloc[:40]
        ax.plot(range(1, len(d) + 1), d.values, "o-", ms=3, lw=1, color=report.color(i, label),
                label=label)
    ax.axhline(0, color="k", lw=0.6)
    ax.set(title="The 40 worst days of net P&L, sorted (1x)", xlabel="rank", ylabel="USD")
    ax.legend(fontsize=7, frameon=False)
    return report.save(fig, folder / "tail.png")


def matched(cfg, sets):
    # round trips opened at the same time as hedged
    ref = legs(sets["hedged"][1.0])
    rows = []
    for k in cfg["variants"]:
        rt = legs(sets[k][1.0])
        m = rt.merge(ref, on="open_ts", suffixes=("", "_ref"))
        rows.append({"book": k, "trips": len(rt), "ref_trips": len(ref), "matched": len(m),
                     "same_close": int((m["ts"] == m["ts_ref"]).sum()),
                     "matched_net": m["pnl_net"].sum(), "matched_ref_net": m["pnl_net_ref"].sum()})
    return pd.DataFrame(rows)


def extra(cfg, sets, folder):
    # beta, hedge size and worst days
    labels = ["hedged", *cfg["variants"]]
    b = betas(pd.read_parquet(engine.DATA / "v1" / "features.parquet"))
    show(folder, "beta", b.describe().to_frame("beta").reset_index())
    p2, df = shares_chart(sets, labels, folder)
    show(folder, "shares", df)
    show(folder, "tail", tail(sets, labels))
    show(folder, "matched", matched(cfg, sets))
    return [beta_chart(b, folder), p2, tail_chart(sets, labels, folder)]


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
