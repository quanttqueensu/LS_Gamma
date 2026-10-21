import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from lsgamma.backtest import config, report, run

NAME = "2026-10-21-signal-times"  # matches configs/experiments/<NAME>.toml
FIGS = Path(__file__).resolve().parent / "figures"
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
    return {"baseline": ref, **{v: report.runs(f"{NAME}/{v}", holdout) for v in labels}}


def value(tab, label, mult, period, metric):
    row = tab[(tab["label"] == label) & (tab["mult"] == mult) & (tab["period"] == period)]
    return float(row[metric].iloc[0])


def checks(cfg, tab, holdout=False, primary=None):
    p, rows = cfg["pass"], []
    primary = primary or p["primary"]
    for c in p["check"]:
        if holdout and c["period"] != "all":
            continue
        for m in MULTS:
            v = value(tab, primary, m, c["period"], c["metric"])
            r = value(tab, p.get("against", "baseline"), m, c["period"], c["metric"])
            ok = RULES[c["rule"]](v, r, c.get("value", 0.0))
            rows.append({"check": f"{c['metric']} {c['rule']} {c.get('value', '')} ({c['period']})",
                         "mult": m, "variant": v, "against": r, "pass": ok})
    return pd.DataFrame(rows)


def events(out, reason):
    t = out["trades"]
    return int(((t["action"] == "close") & (t["reason"] == reason)).sum()) if len(t) else 0


def verdict(cfg, sets, chk):
    p = cfg["pass"]
    if p.get("min_events", 0):
        n = events(sets[p.get("event_label", p["primary"])][1.0], p["event"])
        if n < p["min_events"]:
            return f"INCONCLUSIVE ({n} {p['event']} exits < {p['min_events']})"
    return "PASSED" if chk["pass"].all() else "FAILED"


def opens(out):
    t = out["trades"]
    return t[t["action"] == "open"] if len(t) else t


def per_year(sets, path):
    fig, ax = plt.subplots(figsize=(7, 2.8))
    n = len(sets)
    for i, (label, by_mult) in enumerate(sets.items()):
        y = pd.to_datetime(opens(by_mult[1.0])["date"]).dt.year.value_counts().sort_index()
        ax.bar(y.index + (i - (n - 1) / 2) * 0.8 / n, y.values, 0.8 / n,
               color=report.color(i, label), label=label)
    ax.set(title="Entries per year (1x)", ylabel="entries")
    ax.legend(fontsize=7, frameon=False, ncol=n)
    return report.save(fig, path)


def by_time(sets, path, label="hourly"):
    t = sets[label][1.0]["trades"]
    t = t.assign(hhmm=pd.to_datetime(t["ts"], utc=True).dt.tz_convert("America/New_York")
                 .dt.strftime("%H:%M"))
    df = t.groupby(["hhmm", "action"]).size().unstack(fill_value=0)
    fig, ax = plt.subplots(figsize=(7, 2.8))
    df.plot.bar(ax=ax, rot=0, color={"open": "tab:blue", "close": "tab:orange"})
    ax.set(title=f"Entries and exits by run time, {label} (1x)", xlabel="ET", ylabel="count")
    ax.legend(fontsize=7, frameon=False)
    return report.save(fig, path)


def exits(sets, path):
    rows = {k: report.round_trips(v[1.0])["reason"].value_counts() for k, v in sets.items()}
    df = pd.DataFrame(rows).fillna(0).T
    fig, ax = plt.subplots(figsize=(7, 2.8))
    df.plot.bar(ax=ax, stacked=True, rot=0)
    ax.set(title="Round trips by exit reason (1x)", ylabel="count",
           ylim=(0, df.sum(axis=1).max() * 1.3))
    ax.legend(fontsize=7, frameon=False, ncol=5, loc="upper center")
    return report.save(fig, path)


def extra(cfg, sets, folder):
    # entries by year, by time, exits
    return [per_year(sets, folder / "entries_year.png"), by_time(sets, folder / "by_time.png"),
            exits(sets, folder / "exits.png")]


def secondary(cfg, tab):
    # same bar on sensitivity variants, reported only
    for v in cfg["variants"]:
        if v != cfg["pass"]["primary"]:
            chk = checks(cfg, tab, primary=v)
            print(f"\nsecondary {v}: {'PASSED' if chk['pass'].all() else 'FAILED'}")
            print(chk.round(2).to_string(index=False))
            chk.to_csv(FIGS / f"pass_bar_{v}.csv", index=False)


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
    print(f"\nverdict: {verdict(cfg, sets, chk)}")
    if not holdout:
        secondary(cfg, tab)
    print(f"trials: {report.trials(NAME)} (+ baseline {report.trials('baseline')})")
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
