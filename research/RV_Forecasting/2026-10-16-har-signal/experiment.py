import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from lsgamma.backtest import config, report, run

NAME = "2026-10-16-har-signal"  # matches configs/experiments/<NAME>.toml
REF = "2026-10-16-short-only/short_only"  # registered reference, not rerun
FIGS = Path(__file__).resolve().parent / "figures"
MULTS = (1.0, 2.0)
FORECASTER = {"short_only": "GARCH (short_only)", "har": "HAR (har)"}
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
    short = {} if holdout else {"short_only": report.runs(REF)}
    return {"baseline": ref, **short,
            **{v: report.runs(f"{NAME}/{v}", holdout) for v in labels}}


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
            ref = "baseline" if holdout else p.get("against", "baseline")
            r = value(tab, ref, m, c["period"], c["metric"])
            ok = RULES[c["rule"]](v, r, c.get("value", 0.0))
            rows.append({"check": f"{c['metric']} {c['rule']} {c.get('value', '')} ({c['period']})",
                         "mult": m, "variant": v, "against": r, "pass": ok})
    return pd.DataFrame(rows)


def events(out, reason):
    # round_trip: every closed trade counts
    if reason == "round_trip":
        return len(report.round_trips(out))
    t = out["trades"]
    return int(((t["action"] == "close") & (t["reason"] == reason)).sum()) if len(t) else 0


def verdict(cfg, sets, chk):
    p = cfg["pass"]
    if p.get("min_events", 0):
        n = events(sets[p.get("event_label", p["primary"])][1.0], p["event"])
        if n < p["min_events"]:
            return f"INCONCLUSIVE ({n} {p['event']} exits < {p['min_events']})"
    return "PASSED" if chk["pass"].all() else "FAILED"


def signals(sets, label):
    # last decision per day, 1x
    s = sets[label][1.0]["signals"].drop_duplicates("date", keep="last").copy()
    s["date"] = pd.to_datetime(s["date"])
    return s.set_index("date")


def rv_path(cfg, sets, path):
    fig, ax = plt.subplots(figsize=(7, 3.2))
    for i, (k, name) in enumerate(FORECASTER.items()):
        m = signals(sets, k)["rv_forecast"].resample("ME").mean() * 100
        ax.plot(m.index, m.values, color=report.COLORS[i], lw=1.1, label=name)
    iv = signals(sets, "short_only")["iv"].resample("ME").mean() * 100
    ax.plot(iv.index, iv.values, color=report.BASE, lw=0.9, ls="--", label="ATM IV")
    top = signals(sets, "har")["rv_forecast"].resample("ME").mean() * 100
    if top.max() > 70:  # label the clipped peak
        ax.annotate(f"HAR {top.idxmax():%b %Y}: {top.max():.0f}", (top.idxmax(), 70),
                    xytext=(10, -12), textcoords="offset points", fontsize=7)
    ax.set(title="RV forecast vs ATM IV, monthly mean (axis capped at 70)",
           ylabel="vol points", ylim=(0, 70))
    ax.legend(fontsize=7, frameon=False)
    return report.save(fig, path)


def short_days(cfg, sets, path):
    df = pd.DataFrame({name: (signals(sets, k)["signal"] == "short").groupby(lambda t: t.year).sum()
                       for k, name in FORECASTER.items()})
    fig, ax = plt.subplots(figsize=(7, 2.8))
    df.plot.bar(ax=ax, color=report.COLORS[:2], width=0.8)
    ax.set(title="Short-signal days per year", ylabel="days", xlabel="")
    ax.tick_params(axis="x", rotation=0)
    ax.legend(fontsize=7, frameon=False)
    return report.save(fig, path)


def vrp_dist(cfg, sets, path):
    fig, ax = plt.subplots(figsize=(7, 2.8))
    for i, (k, name) in enumerate(FORECASTER.items()):
        v = signals(sets, k)["vrp"] * 100
        ax.hist(v.clip(-20, 20), bins=80, range=(-20, 20), histtype="step",
                color=report.COLORS[i], lw=1.2, label=name)
    ax.axvline(cfg["signal"]["short_band"] * 100, color="k", lw=0.8, ls=":",
               label="short band")
    ax.set(title="Daily VRP (IV minus RV forecast), clipped at ±20", xlabel="vol points",
           ylabel="days")
    ax.legend(fontsize=7, frameon=False)
    return report.save(fig, path)


def extra(cfg, sets, folder):
    # forecast path, short days, VRP: the mechanism
    return [rv_path(cfg, sets, folder / "rv_forecast.png"),
            short_days(cfg, sets, folder / "short_days.png"),
            vrp_dist(cfg, sets, folder / "vrp_dist.png")]


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
    print(f"trials: {report.trials(NAME)} (+ baseline {report.trials('baseline')}; "
          f"reference {REF} reused, {report.trials(REF)} trials, not rerun)")
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
