import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from lsgamma.backtest import config, metrics, report, run

NAME = "2026-10-16-max-positions"  # matches configs/experiments/<NAME>.toml
FIGS = Path(__file__).resolve().parent / "figures"
MULTS = (1.0, 2.0)
PERIODS = ("all", "2014-2019", "2020-2024")


def label(n):
    return "baseline" if n == 1 else f"pos{n}"


def load_sets(cfg, holdout=False, labels=None):
    ref = report.baseline(config.load(), holdout)
    labels = labels or [label(n) for n in cfg["pass"]["grid"][1:]]
    return {"baseline": ref, **{v: report.runs(f"{NAME}/{v}", holdout) for v in labels}}


def curve(tab, cfg, mult, period, metric="pnl"):
    grid = cfg["pass"]["grid"]
    rows = tab[(tab["mult"] == mult) & (tab["period"] == period)].set_index("label")
    return pd.Series([float(rows.loc[label(n), metric]) for n in grid], index=grid)


def peak(tab, cfg, mult=1.0):
    return int(curve(tab, cfg, mult, "all").idxmax())


def ladder_entries(out):
    # opens while another position is open
    t = out["trades"]
    if t.empty:
        return 0
    o, c = metrics.pairs(t)
    spans = list(zip(o["ts"], c["ts"]))
    opens = t.loc[t["action"] == "open", "ts"]
    return int(sum(any(a < ts < b for a, b in spans) for ts in opens))


def checks(cfg, tab):
    p, grid, rows = cfg["pass"], cfg["pass"]["grid"], []
    ends = (grid[0], grid[-1])
    for m in MULTS:
        pnl = curve(tab, cfg, m, "all")
        top = int(pnl.idxmax())
        rows.append({"check": "peak N is interior (full window)", "mult": m,
                     "value": top, "pass": top not in ends})
        gap = min(pnl[top] - pnl[ends[0]], pnl[top] - pnl[ends[1]])
        rows.append({"check": f"peak clears both ends by >= ${p['margin']:.0f}", "mult": m,
                     "value": round(gap, 1), "pass": gap >= p["margin"]})
        for period in PERIODS[1:]:
            half = int(curve(tab, cfg, m, period).idxmax())
            rows.append({"check": f"peak N is interior ({period})", "mult": m,
                         "value": half, "pass": half not in ends})
    return pd.DataFrame(rows)


def verdict(cfg, sets, chk):
    n = ladder_entries(sets[label(cfg["pass"]["grid"][-1])][1.0])
    if n < cfg["pass"]["min_ladder"]:
        return f"INCONCLUSIVE ({n} ladder entries < {cfg['pass']['min_ladder']})"
    return "PASSED" if chk["pass"].all() else "FAILED"


def margin(out):
    # Reg-T estimate per run time, USD
    e = out["equity"]
    o, c = metrics.pairs(out["trades"]) if len(out["trades"]) else (pd.DataFrame(), pd.DataFrame())
    rows = []
    for ts, spot, shares in zip(e["ts"], e["spot"], e["shares"]):
        need = 0.5 * abs(shares) * spot
        if len(o):
            live = o[((o["ts"] <= ts) & (c["ts"].values > ts)).values]
            for r in live.itertuples():
                prem = r.price * 100 * r.qty
                otm = max(spot - r.strike, 0.0)
                naked = max(0.2 * spot - otm, 0.1 * r.strike) * 100 * r.qty + prem
                need += naked if r.side == "short" else prem
        rows.append({"ts": ts, "margin": need, "open": len(live) if len(o) else 0})
    return pd.DataFrame(rows)


def by_n(cfg, sets, fn):
    return {n: fn(sets[label(n)][1.0]) for n in cfg["pass"]["grid"]}


def pnl_vs_n(cfg, tab, path):
    fig, axes = plt.subplots(1, 2, figsize=(7.5, 3), sharey=True)
    for ax, m in zip(axes, MULTS):
        for period, style in zip(PERIODS, ("o-", "s--", "^:")):
            c = curve(tab, cfg, m, period)
            ax.plot(c.index, c.values, style, lw=1.2, label=period)
        ax.axhline(0, color="k", lw=0.6)
        ax.set(title=f"Net P&L vs max positions, {m:g}x", xlabel="max_positions", ylabel="USD")
        ax.set_xticks(cfg["pass"]["grid"])
    axes[0].legend(fontsize=7, frameon=False)
    return report.save(fig, path)


def risk_vs_n(cfg, tab, path):
    fig, axes = plt.subplots(1, 3, figsize=(7.5, 2.6))
    for ax, (metric, name) in zip(axes, (("sharpe", "Sharpe on $250k"), ("es_5", "ES 5% (daily, USD)"),
                                         ("max_dd", "Max drawdown (USD)"))):
        for m in MULTS:
            c = curve(tab, cfg, m, "all", metric)
            ax.plot(c.index, c.values, "o" + report.STYLE[m], lw=1.1, label=f"{m:g}x")
        ax.set(title=name, xlabel="max_positions")
        ax.set_xticks(cfg["pass"]["grid"])
    axes[0].legend(fontsize=7, frameon=False)
    return report.save(fig, path)


def margin_chart(cfg, mg, path):
    grid = cfg["pass"]["grid"]
    fig, axes = plt.subplots(1, 2, figsize=(7.5, 2.8))
    axes[0].bar([str(n) for n in grid], [mg[n]["margin"].max() / 1000 for n in grid],
                color="tab:blue")
    axes[0].axhline(cfg["pass"]["capital"] / 1000, color="tab:red", lw=1, label="capital $250k")
    axes[0].set(title="Peak estimated Reg-T margin", xlabel="max_positions", ylabel="USD thousands")
    axes[0].legend(fontsize=7, frameon=False)
    axes[1].bar([str(n) for n in grid], [mg[n]["open"].mean() for n in grid], color="tab:green")
    axes[1].set(title="Average open positions", xlabel="max_positions")
    return report.save(fig, path)


def extra(cfg, sets, tab, folder):
    mg = by_n(cfg, sets, margin)
    pd.DataFrame([{"n": n, "peak_margin": mg[n]["margin"].max(), "mean_open": mg[n]["open"].mean(),
                   "max_open": mg[n]["open"].max(), "ladder_entries": ladder_entries(sets[label(n)][1.0])}
                  for n in cfg["pass"]["grid"]]).to_csv(folder / "capacity.csv", index=False)
    return [pnl_vs_n(cfg, tab, folder / "pnl_vs_n.png"), risk_vs_n(cfg, tab, folder / "risk_vs_n.png"),
            margin_chart(cfg, mg, folder / "margin.png")]


def build(cfg):
    sets = load_sets(cfg)
    FIGS.mkdir(parents=True, exist_ok=True)
    tab = report.table(sets)
    tab.to_csv(FIGS / "table.csv", index=False)
    paths = report.standard(sets, FIGS) + extra(cfg, sets, tab, FIGS)
    chk = checks(cfg, tab)
    chk.to_csv(FIGS / "pass_bar.csv", index=False)
    cols = ["label", "mult", "period", "pnl", "sharpe", "max_dd", "es_5", "trades",
            "win_rate", "gross", "option_fees", "hedge_fees", "hedge_orders"]
    print(tab[cols].round(2).to_string(index=False))
    print("\ncapacity\n" + pd.read_csv(FIGS / "capacity.csv").round(1).to_string(index=False))
    print("\npass bar\n" + chk.to_string(index=False))
    print(f"\nverdict: {verdict(cfg, sets, chk)}  (dev peak N at 1x: {peak(tab, cfg)})")
    print(f"trials: {report.trials(NAME)} (+ baseline {report.trials('baseline')})")
    print("figures:", *[p.name for p in paths])


def holdout_report(cfg, top):
    sets = load_sets(cfg, True, [label(top)])
    folder = FIGS / "holdout"
    folder.mkdir(parents=True, exist_ok=True)
    tab = report.table(sets)
    tab.to_csv(folder / "table.csv", index=False)
    report.cum_pnl(sets, folder / "cum_pnl.png", title="Hold-out cumulative net P&L")
    ok = [value > base for value, base in
          ((curve_at(tab, label(top), m), curve_at(tab, "baseline", m)) for m in MULTS)]
    print(tab[tab["period"] == "all"].round(2).to_string(index=False))
    print(f"\nhold-out: {label(top)} net P&L > baseline at 1x and 2x: {all(ok)}")


def curve_at(tab, name, mult):
    rows = tab[(tab["label"] == name) & (tab["mult"] == mult) & (tab["period"] == "all")]
    return float(rows["pnl"].iloc[0])


def main():
    p = argparse.ArgumentParser(description=NAME)
    p.add_argument("--report-only", action="store_true", help="rebuild from registered runs")
    p.add_argument("--holdout", action="store_true", help="final run: dev peak N, once")
    a = p.parse_args()
    cfg = config.load(NAME)
    if a.holdout:
        top = peak(report.table(load_sets(cfg)), cfg)
        if not a.report_only:
            run.holdout(NAME, label(top), cfg, config.load())
        return holdout_report(cfg, top)
    if not a.report_only:
        if report.trials(NAME):
            raise SystemExit(f"{NAME} already has trials; use --report-only")
        for v, rows in run.variants(NAME, cfg, cfg["variants"]).items():
            print(f"\n{v}\n{run.table(rows)}")
    build(cfg)


if __name__ == "__main__":
    main()
