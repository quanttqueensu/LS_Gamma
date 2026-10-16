import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from lsgamma.backtest import config, report, run

NAME = "2026-10-16-short-only"
LABEL = "short_only"
FIGURES = Path(__file__).resolve().parent / "figures"
SLACK = 1.10  # tail and drawdown allowance vs baseline
COLS = ["pnl", "sharpe", "max_dd", "es_5", "trades", "win_rate", "gross",
        "option_fees", "hedge_fees", "hedge_orders"]


def backtest():
    cfg = config.load(NAME)
    rows = run.variants(NAME, cfg, cfg["variants"])
    for label, r in rows.items():
        print(f"\n{NAME}/{label}")
        print(run.table(r))


def baseline():
    # trial 1 of baseline at each mult
    reg = report.registry()
    first = reg[reg["experiment"] == "baseline"].groupby("spread_mult").head(1)
    return {float(r.spread_mult): report.load(r.run) for r in first.itertuples()}


def sets():
    return {"baseline": baseline(), LABEL: report.runs(f"{NAME}/{LABEL}")}


def side_pnl(out):
    rt = report.round_trips(out)
    g = rt.groupby("side")["pnl_net"].sum() if len(rt) else pd.Series(dtype=float)
    return pd.Series({s: float(g.get(s, 0.0)) for s in ("long", "short")})


def by_side(s, path):
    fig, axes = plt.subplots(1, 2, figsize=(7.5, 3), sharey=True)
    for ax, mult in zip(axes, (1.0, 2.0)):
        df = pd.DataFrame({label: side_pnl(by[mult]) for label, by in s.items() if mult in by})
        df.loc["total"] = df.sum()
        df.plot.bar(ax=ax, rot=0, width=0.8,
                    color=[report.color(i, c) for i, c in enumerate(df.columns)])
        ax.axhline(0, color="k", lw=0.6)
        ax.set(title=f"Net P&L by side, {mult:g}x", ylabel="USD, 1 contract")
        ax.legend(fontsize=7, frameon=False)
    return report.save(fig, path)


def get(tab, label, mult, period, col):
    row = tab[(tab["label"] == label) & (tab["mult"] == mult) & (tab["period"] == period)]
    return float(row[col].iloc[0])


def bars(tab, mult):
    v = lambda label, period, col: get(tab, label, mult, period, col)
    pnl = all(v(LABEL, p, "pnl") > v("baseline", p, "pnl")
              for p in ("all", "2014-2019", "2020-2024"))
    es = abs(v(LABEL, "all", "es_5")) <= SLACK * abs(v("baseline", "all", "es_5"))
    dd = v(LABEL, "all", "max_dd") <= SLACK * v("baseline", "all", "max_dd")
    return {"1 net P&L > baseline (all and both halves)": pnl,
            "2 |ES 5%| <= 1.10 x baseline": es,
            "3 max DD <= 1.10 x baseline": dd}


def evaluate(tab):
    passed = True
    for mult in (1.0, 2.0):
        print(f"\npass bar, {mult:g}x spreads")
        for bar, ok in bars(tab, mult).items():
            print(f"  {bar}: {'PASS' if ok else 'FAIL'}")
            passed &= ok
    print(f"\nverdict: {'PASS' if passed else 'FAIL'} (all three bars at 1x and 2x)")


def build():
    s = sets()
    report.standard(s, FIGURES)
    by_side(s, FIGURES / "by_side.png")
    tab = report.table(s)
    tab.to_csv(FIGURES / "table.csv", index=False)
    with pd.option_context("display.width", 160, "display.max_columns", 20):
        print(tab.set_index(["label", "mult", "period"])[COLS].round(3).to_string())
    evaluate(tab)


def main():
    p = argparse.ArgumentParser(description=f"{NAME}: short-only vs baseline")
    p.add_argument("--report-only", action="store_true", help="rebuild charts, no new trials")
    a = p.parse_args()
    if not a.report_only:
        backtest()
    build()


if __name__ == "__main__":
    main()
