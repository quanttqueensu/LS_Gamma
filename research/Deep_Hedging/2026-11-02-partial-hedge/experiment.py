import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from lsgamma.backtest import config, engine, metrics, report, run
from lsgamma.pipeline import store
from lsgamma.trading import runner

NAME = "2026-11-02-partial-hedge"  # matches configs/experiments/<NAME>.toml
FIGS = Path(__file__).resolve().parent / "figures"
REF = "2026-10-22-stress-sized-puts/hedged"  # reused, not rerun
CONTEXT = ["2026-11-02-vrp-hedge/vrp2"]  # shown in charts only
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


def partial(rt):
    col = rt["open_hedge_ratio"] if "open_hedge_ratio" in rt else pd.Series(np.nan, index=rt.index)
    return col.notna()


def events(out, kind):
    # partial: round trips entered with a partial hedge
    if kind == "round_trip":
        return len(report.round_trips(out))
    return int(partial(legs(out)).sum())


def with_vrp(out):
    sig = out["signals"][["ts", "vrp"]].rename(columns={"ts": "open_ts"})
    return legs(out).merge(sig, on="open_ts", how="left")


def split(cfg, sets):
    rows = []
    for k in cfg["variants"]:
        rt = legs(sets[k][1.0])
        for flag, g in rt.groupby(partial(rt)):
            rows.append({"book": k, "hedge": "partial" if flag else "full", "trips": len(g),
                         "contracts": g["open_qty"].mean(), "net": g["pnl_net"].sum(),
                         "per_contract": (g["pnl_net"] / g["open_qty"]).mean(),
                         "pooled": g["pnl_net"].sum() / g["open_qty"].sum()})
    return pd.DataFrame(rows)


BUCKETS = [-np.inf, 0.0, 0.01, 0.02, 0.04, np.inf]
NAMES = ["<= 0", "0-1", "1-2", "2-4", "> 4"]


def by_vrp(cfg, sets):
    # net per contract by VRP at entry
    rows = []
    for k in ("hedged", cfg["pass"]["primary"]):
        rt = with_vrp(sets[k][1.0])
        b = pd.cut(rt["vrp"], BUCKETS, labels=NAMES)
        for name, g in rt.groupby(b, observed=True):
            rows.append({"book": k, "vrp_pts": name, "trips": len(g), "net": g["pnl_net"].sum(),
                         "pooled": g["pnl_net"].sum() / g["open_qty"].sum()})
    return pd.DataFrame(rows)


def decisions(out):
    return sorted(out["signals"]["ts"].unique())


def chain_at(ts):
    asof = pd.Timestamp(ts)
    p = store.folder(asof, engine.DATA / "v1") / "chain.parquet"
    return pd.read_parquet(p) if p.exists() else None


def put_delta(chain, r):
    if chain is None:
        return np.nan
    row = chain[(chain["expiry"].astype(str) == r["open_expiry"])
                & (chain["strike"] == r["open_strike"]) & (chain["right"] == "P")]
    return np.nan if row.empty else float(row["delta"].iloc[0])


def delta_legs(out):
    # snapshot delta x spot change to next decision
    rt, ts = legs(out), decisions(out)
    chains = {t: chain_at(t) for t in ts}
    spots = {t: runner.spot(c) if c is not None else np.nan for t, c in chains.items()}
    nxt = dict(zip(ts, ts[1:]))
    rows = []
    for _, r in rt.iterrows():
        ratio = r.get("open_hedge_ratio", np.nan)
        ratio = 1.0 if pd.isna(ratio) else float(ratio)
        held = [t for t in ts if r["open_ts"] <= t < r["ts"] and t in nxt]
        pnl = dollars = 0.0
        for a in held:
            d = -put_delta(chains[a], r) * r["open_qty"] * 100  # short put: long delta
            move = spots[nxt[a]] - spots[a]
            if np.isnan(d) or np.isnan(move):
                continue
            pnl += d * move
            dollars += d * spots[a]
        rows.append({"open_ts": r["open_ts"], "partial": ratio < 1.0, "ratio": ratio,
                     "days": len(held), "delta_pnl": pnl, "kept_pnl": (1 - ratio) * pnl,
                     "delta_dollar_days": dollars})
    return pd.DataFrame(rows)


def delta_table(cfg, sets):
    out = sets[cfg["pass"]["primary"]][1.0]
    df = delta_legs(out)
    rows = []
    for flag, g in df.groupby("partial"):
        dd = g["delta_dollar_days"].sum()
        rows.append({"puts": "partial" if flag else "full", "trips": len(g),
                     "position_days": int(g["days"].sum()), "delta_pnl": g["delta_pnl"].sum(),
                     "kept_pnl": g["kept_pnl"].sum(),
                     "per_dollar_year": g["delta_pnl"].sum() / dd * 252 if dd else np.nan})
    return df, pd.DataFrame(rows)


def mech_chart(cfg, sets, vrp, dt, folder):
    p = cfg["pass"]["primary"]
    fig, axes = plt.subplots(1, 3, figsize=(8, 3))
    piv = vrp.pivot(index="vrp_pts", columns="book", values="pooled").reindex(NAMES)
    piv.plot.bar(ax=axes[0], color=["tab:blue", "tab:orange"], width=0.7)
    axes[0].axhline(0, color="k", lw=0.6)
    axes[0].set(title="Net per contract\nby VRP at entry, 1x", ylabel="USD", xlabel="VRP (vol pts)")
    axes[0].tick_params(axis="x", rotation=0, labelsize=7)
    axes[0].legend(fontsize=7, frameon=False)
    axes[1].bar(dt["puts"], dt["delta_pnl"] / 1e3, color="tab:gray", label="option delta")
    axes[1].bar(dt["puts"], dt["kept_pnl"] / 1e3, color="tab:green", width=0.5, label="kept (unhedged)")
    axes[1].axhline(0, color="k", lw=0.6)
    axes[1].set(title=f"Delta-leg P&L, {p} 1x", ylabel="USD thousands")
    axes[1].legend(fontsize=7, frameon=False)
    rt = legs(sets[p][1.0])
    n = rt[partial(rt)].groupby(pd.to_datetime(rt["open_date"]).dt.year).size()
    axes[2].bar(n.index, n.values, color="tab:green")
    axes[2].set(title=f"Partly hedged entries\nper year ({p}, 1x)", ylabel="entries")
    axes[2].tick_params(axis="x", labelsize=7, rotation=45)
    return report.save(fig, folder / "mechanism.png")


def extra(cfg, sets, folder):
    # hedge split, VRP buckets, delta leg
    show(folder, "split", split(cfg, sets))
    vrp = by_vrp(cfg, sets)
    show(folder, "by_vrp", vrp)
    _, dt = delta_table(cfg, sets)
    show(folder, "delta_leg", dt)
    return [mech_chart(cfg, sets, vrp, dt, folder)]


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
