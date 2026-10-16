import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from lsgamma.backtest import config, report, run

NAME = "2026-10-16-stop-cooloff"
LABELS = ["cool0", "cool1", "cool5", "reset"]
REF = "cool1"  # live 1-day rule
CHALLENGERS = ["cool5", "reset"]
MULTS = [1.0, 2.0]
MIN_STOPS = 5  # fewer at 1x: inconclusive
AFTER = 10  # trading days after a stop
FIGS = Path(__file__).resolve().parent / "figures"
BLOCKS = ["cooloff", "reset_wait"]


def trips(out):
    rt = report.round_trips(out).reset_index(drop=True)
    if rt.empty:
        return pd.DataFrame(columns=["side", "entry_date", "exit_date", "reason", "pnl_net",
                                     "reentry", "after_stop"])
    stop = rt["reason"] == "stop"
    rt["reentry"] = stop.shift(fill_value=False) & (rt["side"] == rt["side"].shift())
    stops = rt.loc[stop, "exit_date"].astype(str).tolist()
    rt["after_stop"] = [near(str(e), stops) for e in rt["entry_date"]]
    return rt


def near(entry, stops):
    # opened 0..AFTER weekdays after an earlier stop
    return any(s <= entry and np.busday_count(s, entry) <= AFTER for s in stops)


def stop_stats(out):
    rt, ev = trips(out), out["events"]
    blocked = ev[ev["event"].isin(BLOCKS)]["date"].nunique() if len(ev) else 0
    flag = rt["after_stop"].astype(bool)
    after, other = rt[flag], rt[~flag]
    return {"stops": int((rt["reason"] == "stop").sum()), "blocked_days": int(blocked),
            "reentries": int(rt["reentry"].astype(bool).sum()),
            "after_n": len(after), "after_pnl": float(after["pnl_net"].sum()),
            "other_n": len(other), "other_pnl": float(other["pnl_net"].sum())}


def stop_table(sets):
    rows = [{"label": label, "mult": m, **stop_stats(out)}
            for label, by_mult in sets.items() for m, out in sorted(by_mult.items())]
    return pd.DataFrame(rows)


def row(t, label, mult, period):
    r = t[(t["label"] == label) & (t["mult"] == mult) & (t["period"] == period)]
    return r.iloc[0]


def checks(t, label, mult):
    ref = {p: row(t, REF, mult, p) for p in ("all", "2014-2019", "2020-2024")}
    var = {p: row(t, label, mult, p) for p in ref}
    c = {f"pnl_{p}": bool(var[p]["pnl"] > ref[p]["pnl"]) for p in ref}
    c["es_5_all"] = bool(var["all"]["es_5"] > ref["all"]["es_5"])  # less negative
    return c


def verdict(t, st):
    n = int(st[(st["label"] == REF) & (st["mult"] == 1.0)]["stops"].iloc[0])
    lines = [f"{REF} stop exits at 1x: {n} (minimum {MIN_STOPS})"]
    if n < MIN_STOPS:
        return lines + ["VERDICT: INCONCLUSIVE (too few events)"]
    winners = []
    for label in CHALLENGERS:
        ok = True
        for m in MULTS:
            c = checks(t, label, m)
            ok &= all(c.values())
            lines.append(f"{label} vs {REF} {m:g}x: {c} -> {'beats' if all(c.values()) else 'no'}")
        winners += [label] if ok else []
    if winners:
        return lines + [f"VERDICT: PASSED ({', '.join(winners)} beats {REF} at 1x and 2x)"]
    return lines + [f"VERDICT: FAILED (live {REF} rule stays)"]


def bars(ax, groups, series, colors, fmt="{:.0f}"):
    # grouped bars with value labels
    n, x = len(series), np.arange(len(groups))
    for i, (name, vals) in enumerate(series.items()):
        b = ax.bar(x + (i - (n - 1) / 2) * 0.8 / n, vals, 0.8 / n, color=colors[i], label=name)
        ax.bar_label(b, [fmt.format(v) for v in vals], fontsize=6, padding=1)
    ax.set_xticks(x, groups)
    ax.axhline(0, color="k", lw=0.6)


def stops_chart(st, path):
    fig, axes = plt.subplots(1, 2, figsize=(7.5, 3), sharey=True)
    for ax, m in zip(axes, MULTS):
        d = st[(st["mult"] == m) & st["label"].isin(LABELS)].set_index("label").loc[LABELS]
        bars(ax, LABELS, {"stops": d["stops"], "blocked days": d["blocked_days"],
                          "same-side re-entries": d["reentries"]},
             ["tab:red", report.BASE, "tab:blue"])
        ax.set(title=f"Stops and re-entries, {m:g}x", ylabel="count")
    axes[0].legend(fontsize=7, frameon=False)
    return report.save(fig, path)


def after_chart(st, path):
    fig, axes = plt.subplots(1, 2, figsize=(7.5, 3), sharey=True)
    for ax, m in zip(axes, MULTS):
        d = st[st["mult"] == m].set_index("label").loc[LABELS]
        bars(ax, [f"{lb}\nn={a}/{o}" for lb, a, o in zip(LABELS, d["after_n"], d["other_n"])],
             {f"opened <= {AFTER} trading days after a stop": d["after_pnl"],
              "all other trades": d["other_pnl"]}, ["tab:red", report.BASE])
        ax.set(title=f"Net P&L by entry timing, {m:g}x", ylabel="USD, 1 contract",
               xlabel="n = trades after a stop / other trades")
        ax.tick_params(axis="x", labelsize=7)
    axes[0].legend(fontsize=7, frameon=False)
    return report.save(fig, path)


def sets():
    return {"baseline": report.runs("baseline"),
            **{lb: report.runs(f"{NAME}/{lb}") for lb in LABELS}}


def build():
    s = sets()
    t, st = report.table(s), stop_table(s)
    FIGS.mkdir(parents=True, exist_ok=True)
    t.to_csv(FIGS / "table.csv", index=False)
    st.to_csv(FIGS / "stops.csv", index=False)
    report.standard(s, FIGS)
    stops_chart(st, FIGS / "stops.png")
    after_chart(st, FIGS / "after_stop.png")
    with pd.option_context("display.width", 200, "display.max_columns", 30):
        print(t.round(3).to_string(index=False))
        print("\nstops, blocks, re-entries, entry timing\n" + st.round(1).to_string(index=False))
    print("\n" + "\n".join(verdict(t, st)))
    print(f"trials: {report.trials(NAME)} (+2 baseline)")


def main():
    p = argparse.ArgumentParser(description="Stop cool-off: none vs 1 day vs 5 days vs reset")
    p.add_argument("--report-only", action="store_true", help="rebuild charts from latest runs")
    a = p.parse_args()
    if not a.report_only:
        cfg = config.load(NAME)
        for label, rows in run.variants(NAME, cfg, cfg["variants"]).items():
            print(f"\n{label}\n{run.table(rows)}")
    build()


if __name__ == "__main__":
    main()
