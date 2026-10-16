import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.patches import Patch

from lsgamma.backtest import config, report, run

NAME = "2026-10-16-short-band-4"  # matches configs/experiments/<NAME>.toml
REF = "2026-10-16-short-only/short_only"  # registered reference, not rerun
FIGS = Path(__file__).resolve().parent / "figures"
MULTS = (1.0, 2.0)
RULES = {
    "higher": lambda v, r, x: v > r,
    "less_severe": lambda v, r, x: abs(v) < abs(r),
    "abs_within": lambda v, r, x: abs(v) <= x * abs(r),
    "not_below": lambda v, r, x: v >= r - x,
}


def bands(cfg):
    # variants ordered by short band
    v = cfg["variants"]
    return sorted(v, key=lambda k: v[k]["signal"]["short_band"])


def load_sets(cfg, holdout=False):
    # baseline first so it is drawn grey
    ref = report.baseline(config.load(), holdout)
    if holdout:
        p = cfg["pass"]["primary"]
        return {"baseline": ref, p: report.runs(f"{NAME}/{p}", True)}
    return {"baseline": ref, "short_only": report.runs(REF),
            **{v: report.runs(f"{NAME}/{v}") for v in bands(cfg)}}


def value(tab, label, mult, period, metric):
    row = tab[(tab["label"] == label) & (tab["mult"] == mult) & (tab["period"] == period)]
    return float(row[metric].iloc[0])


def checks(cfg, tab, holdout=False):
    p, rows = cfg["pass"], []
    against = "baseline" if holdout else p.get("against", "baseline")
    for c in p["check"]:
        if holdout and c["period"] != "all":
            continue
        for m in MULTS:
            v = value(tab, p["primary"], m, c["period"], c["metric"])
            r = value(tab, against, m, c["period"], c["metric"])
            ok = RULES[c["rule"]](v, r, c.get("value", 0.0))
            rows.append({"check": f"{c['metric']} {c['rule']} {c.get('value', '')} ({c['period']})",
                         "mult": m, "variant": v, "against": r, "pass": ok})
    return pd.DataFrame(rows)


def events(out, reason):
    # "round_trip" counts every close
    t = out["trades"]
    if t.empty:
        return 0
    close = t["action"] == "close"
    return int(close.sum() if reason == "round_trip" else (close & (t["reason"] == reason)).sum())


def verdict(cfg, sets, chk):
    p = cfg["pass"]
    if p.get("min_events", 0):
        n = events(sets[p.get("event_label", p["primary"])][1.0], p["event"])
        if n < p["min_events"]:
            return f"INCONCLUSIVE ({n} {p['event']} events < {p['min_events']})"
    return "PASSED" if chk["pass"].all() else "FAILED"


def per_trip(out):
    rt = report.round_trips(out)
    return len(rt), float(rt["pnl_net"].mean()) if len(rt) else 0.0


def entry_vrp(out):
    # vrp on the signal row of each entry
    t, s = out["trades"], out["signals"]
    opens = t[t["action"] == "open"]["ts"] if len(t) else pd.Series(dtype=str)
    return s.set_index("ts")["vrp"].reindex(opens).dropna() * 100


def short_days(out):
    s = out["signals"]
    s = s[s["signal"] == "short"]
    return s.groupby(pd.to_datetime(s["date"]).dt.year).size()


def edge(cfg, sets, path):
    labels = list(sets)
    cols = [report.color(i, k) for i, k in enumerate(labels)]
    fig, axes = plt.subplots(1, 2, figsize=(7.5, 2.8))
    axes[0].bar(labels, [per_trip(sets[k][1.0])[0] for k in labels], color=cols)
    axes[0].set(title="Round trips, 2014-2024", ylabel="count")
    w, x = 0.38, range(len(labels))
    for j, m in enumerate(MULTS):
        axes[1].bar([i + (j - 0.5) * w for i in x], [per_trip(sets[k][m])[1] for k in labels],
                    w, color=cols, alpha=1.0 if m == 1.0 else 0.5)
    axes[1].axhline(0, color="black", lw=0.6)
    axes[1].set(title="Net P&L per round trip", ylabel="USD, 1 contract",
                xticks=list(x), xticklabels=labels)
    keys = [Patch(color="0.3", alpha=a, label=f"{m:g}x") for m, a in zip(MULTS, (1.0, 0.5))]
    axes[1].legend(handles=keys, fontsize=7, frameon=False)
    for ax in axes:
        ax.tick_params(axis="x", labelsize=7)
    return report.save(fig, path)


def vrp_dist(cfg, sets, path):
    labels = [k for k in sets if k != "baseline"]
    fig, ax = plt.subplots(figsize=(7, 2.8))
    ax.boxplot([entry_vrp(sets[k][1.0]) for k in labels], tick_labels=labels,
               showfliers=False, whis=(5, 95))
    ax.set(title="VRP at entry (vol points, 1x; whiskers 5-95%)", ylabel="IV - RV forecast")
    return report.save(fig, path)


def days_per_year(cfg, sets, path):
    labels = [k for k in sets if k != "baseline"]
    years = pd.to_datetime(sets[labels[0]][1.0]["signals"]["date"]).dt.year.unique()
    df = pd.DataFrame({k: short_days(sets[k][1.0]) for k in labels}).reindex(years).fillna(0)
    fig, ax = plt.subplots(figsize=(7.5, 2.8))
    df.plot.bar(ax=ax, width=0.8, color=[report.color(i + 1, k) for i, k in enumerate(labels)])
    ax.set(title="Short-signal days per year (10:15 ET signal)", xlabel="", ylabel="days")
    ax.tick_params(axis="x", labelrotation=0)
    ax.legend(fontsize=7, frameon=False)
    return report.save(fig, path)


def mechanism(sets):
    rows = []
    for k, by in sets.items():
        for m, out in sorted(by.items()):
            n, avg = per_trip(out)
            v = entry_vrp(out)
            rows.append({"label": k, "mult": m, "trips": n, "net_per_trip": avg,
                         "vrp_med": v.median(), "short_days": int(short_days(out).sum())})
    print(pd.DataFrame(rows).round(2).to_string(index=False))


def extra(cfg, sets, folder):
    # edge per trade vs trade count
    return [edge(cfg, sets, folder / "edge.png"), vrp_dist(cfg, sets, folder / "vrp_entry.png"),
            days_per_year(cfg, sets, folder / "short_days.png")]


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
    print()
    mechanism(sets)
    print("\npass bar" + (" (hold-out)" if holdout else ""))
    print(chk.round(2).to_string(index=False))
    print(f"\nverdict: {verdict(cfg, sets, chk)}")
    print(f"trials: {report.trials(NAME)} (+ reference {report.trials(REF)} reused, "
          f"baseline {report.trials('baseline')})")
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
