import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from lsgamma.backtest import config, report, run

NAME = "2026-10-17-always-short"  # matches configs/experiments/<NAME>.toml
FIGS = Path(__file__).resolve().parent / "figures"
REF = "2026-10-17-otm-put/put25"  # reused, not rerun
MULTS = (1.0, 2.0)
RULES = {
    "higher": lambda v, r, x: v > r,
    "less_severe": lambda v, r, x: abs(v) < abs(r),
    "abs_within": lambda v, r, x: abs(v) <= x * abs(r),
    "not_below": lambda v, r, x: v >= r - x,
}


def load_sets(cfg, holdout=False):
    # baseline first so it is drawn grey
    ref = report.baseline(config.load(), holdout)
    labels = [cfg["pass"]["primary"]] if holdout else list(cfg["variants"])
    ours = {v: report.runs(f"{NAME}/{v}", holdout) for v in labels}
    return {"baseline": ref, **({} if holdout else {"put25": report.runs(REF)}), **ours}


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
            r = value(tab, "baseline" if holdout else p.get("against", "baseline"), m,
                      c["period"], c["metric"])
            ok = RULES[c["rule"]](v, r, c.get("value", 0.0))
            rows.append({"check": f"{c['metric']} {c['rule']} {c.get('value', '')} ({c['period']})",
                         "mult": m, "variant": v, "against": r, "pass": ok})
    return pd.DataFrame(rows)


def events(out, reason):
    t = out["trades"]
    if reason == "round_trip":
        return len(report.round_trips(out))
    return int(((t["action"] == "close") & (t["reason"] == reason)).sum()) if len(t) else 0


def verdict(cfg, sets, chk, holdout=False):
    p = cfg["pass"]
    if p.get("min_events", 0) and not holdout:
        n = events(sets[p.get("event_label", p["primary"])][1.0], p["event"])
        if n < p["min_events"]:
            return f"INCONCLUSIVE ({n} {p['event']} exits < {p['min_events']})"
    return "PASSED" if chk["pass"].all() else "FAILED"


WINDOWS = (("2014-06 to 2015-05", "2014-06-01", "2015-06-01"),
           ("2015-06 to 2021-12 (archive window)", "2015-06-01", "2022-01-01"),
           ("2022", "2022-01-01", "2023-01-01"), ("2023-2024", "2023-01-01", "2025-01-01"))


def books(sets):
    return [k for k in sets if k != "baseline"]


def windows(sets):
    rows = []
    for k in sets:
        for m in MULTS:
            d = report.daily(sets[k][m])
            rows.append({"book": k, "mult": m, **{w: float(d[lo:hi].sum()) for w, lo, hi in
                                                    [(w, lo, pd.Timestamp(hi) - pd.Timedelta(days=1))
                                                     for w, lo, hi in WINDOWS]}})
    return pd.DataFrame(rows)


def exposure(sets, path):
    labels = books(sets)
    fig, ax = plt.subplots(figsize=(7, 2.8))
    for i, k in enumerate(labels):
        e = sets[k][1.0]["equity"].drop_duplicates("date", keep="last")
        held = (e["option"] != 0).groupby(pd.to_datetime(e["date"]).dt.year).mean()
        ax.plot(held.index, held.values * 100, ["o-", "s--", "^:"][i % 3],
                color=report.color(i + 1, k), label=k)
    ax.set(title="Share of trading days holding a short put (1x)", ylabel="% of days")
    ax.legend(fontsize=7, frameon=False)
    return report.save(fig, path)


def exits(sets, path):
    labels = books(sets)
    rows = {k: report.round_trips(sets[k][1.0])["reason"].value_counts() for k in labels}
    df = pd.DataFrame(rows).fillna(0).T
    fig, ax = plt.subplots(figsize=(7, 2.8))
    df.plot.bar(ax=ax, stacked=True, rot=0)
    ax.set(title="Round trips by exit reason (1x)", ylabel="count",
           ylim=(0, df.sum(axis=1).max() * 1.3))
    ax.legend(fontsize=7, frameon=False, ncol=4, loc="upper center")
    return report.save(fig, path)


def window_chart(sets, path):
    w = windows(sets)
    fig, axes = plt.subplots(1, 2, figsize=(7.5, 3), sharey=True)
    names = [x[0] for x in WINDOWS]
    for ax, m in zip(axes, MULTS):
        sub = w[w["mult"] == m].set_index("book")[names]
        for i, k in enumerate(sub.index):
            ax.bar([j + (i - (len(sub) - 1) / 2) * 0.8 / len(sub) for j in range(len(names))],
                   sub.loc[k].values, 0.8 / len(sub), color=report.color(i, k), label=k)
        ax.set_xticks(range(len(names)), ["2014-15", "2015-21", "2022", "2023-24"])
        ax.axhline(0, color="k", lw=0.6)
        ax.set(title=f"Net P&L by window, {m:g}x", ylabel="USD")
    axes[0].legend(fontsize=7, frameon=False)
    return report.save(fig, path)


def extra(cfg, sets, folder):
    # exposure, exits and the archive window split
    windows(sets).to_csv(folder / "windows.csv", index=False)
    print(windows(sets).round(0).to_string(index=False))
    return [exposure(sets, folder / "exposure.png"), exits(sets, folder / "exits.png"),
            window_chart(sets, folder / "windows.png")]


def build(cfg, holdout=False):
    sets = load_sets(cfg, holdout)
    folder = FIGS / "holdout" if holdout else FIGS
    tab = report.table(sets)
    folder.mkdir(parents=True, exist_ok=True)
    tab.to_csv(folder / "table.csv", index=False)
    paths = [report.cum_pnl(sets, folder / "cum_pnl.png")] if holdout else (
        report.standard(sets, folder) + extra(cfg, sets, folder))
    chk = checks(cfg, tab, holdout)
    chk.to_csv(folder / "pass_bar.csv", index=False)
    cols = ["label", "mult", "period", "pnl", "sharpe", "max_dd", "es_5", "trades",
            "win_rate", "gross", "option_fees", "hedge_fees", "hedge_orders"]
    print(tab[cols].round(2).to_string(index=False))
    print("\npass bar" + (" (hold-out)" if holdout else ""))
    print(chk.round(2).to_string(index=False))
    print(f"\nverdict: {verdict(cfg, sets, chk, holdout)}")
    print(f"trials: {report.trials(NAME)} (+ baseline {report.trials('baseline')}; "
          f"reference {REF} reused, 2 trials, not rerun)")
    print("figures:", *[p.name for p in paths])


def main():
    p = argparse.ArgumentParser(description=NAME)
    p.add_argument("--report-only", action="store_true", help="rebuild from registered runs")
    p.add_argument("--holdout", action="store_true", help="final run: primary variant, once")
    a = p.parse_args()
    cfg = config.load(NAME)
    if a.holdout and not a.report_only:
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
