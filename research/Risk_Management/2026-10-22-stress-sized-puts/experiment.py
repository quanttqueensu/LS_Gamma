import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from lsgamma.backtest import config, engine, report, run, sim
from lsgamma.pipeline import store
from lsgamma.trading.pnl import SIGN

NAME = "2026-10-22-stress-sized-puts"  # matches configs/experiments/<NAME>.toml
FIGS = Path(__file__).resolve().parent / "figures"
REF = "2026-10-17-always-short/always25"  # reused, not rerun
MULTS = (1.0, 2.0)
RULES = {
    "higher": lambda v, r, x: v > r,
    "less_severe": lambda v, r, x: abs(v) < abs(r),
    "abs_within": lambda v, r, x: abs(v) <= x * abs(r),
    "not_below": lambda v, r, x: v >= r - x,
    "above": lambda v, r, x: v > x,  # absolute
    "at_most": lambda v, r, x: v <= x,  # absolute
}
FIXED = (0.005, 1.00)  # IBKR Pro Fixed: per share, minimum
TIERED = (0.0035, 0.35, 0.0032)  # Tiered: per share, minimum, exchange + clearing
RECENT = ("2023-01-01", "2025-01-01")  # SPY nearest today's level


def load_sets(cfg, holdout=False):
    # baseline first so it is drawn grey
    ref = report.baseline(config.load(), holdout)
    labels = [cfg["pass"]["primary"]] if holdout else list(cfg["variants"])
    ours = {v: report.runs(f"{NAME}/{v}", holdout) for v in labels}
    return {"baseline": ref, **({} if holdout else {"always25": report.runs(REF)}), **ours}


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


def budget(cfg):
    v = cfg["variants"][cfg["pass"]["primary"]]["backtest"]["stress_budget"]
    return v * cfg["size"]["capital"]


def books(sets):
    return [k for k in sets if k not in ("baseline", "always25")]


def cum_pnl(sets, path):
    fig, ax = plt.subplots(figsize=(7, 3.4))
    for i, (label, by_mult) in enumerate(sets.items()):
        for mult, out in sorted(by_mult.items()):
            d = report.daily(out).cumsum()
            ax.plot(d.index, d.values, report.STYLE.get(mult, ":"), color=report.color(i, label),
                    lw=1.1, label=f"{label} {mult:g}x")
    ax.axhline(0, color="k", lw=0.6)
    ax.set(title="Cumulative net P&L (baseline and always25: 1 contract)", ylabel="USD")
    ax.legend(fontsize=7, ncol=2, frameon=False)
    return report.save(fig, path)


def drawdown(sets, path, limit):
    fig, axes = plt.subplots(2, 1, figsize=(7, 4), sharex=True)
    for ax, mult in zip(axes, MULTS):
        for i, (label, by_mult) in enumerate(sets.items()):
            if mult in by_mult:
                eq = report.daily(by_mult[mult]).cumsum()
                ax.plot(eq.index, (eq - eq.cummax().clip(lower=0)).values,
                        color=report.color(i, label), lw=1, label=label)
        ax.axhline(-limit, color="tab:red", lw=0.8, ls=":")
        ax.set(title=f"Drawdown, {mult:g}x spreads (dotted: stress budget)", ylabel="USD")
    axes[0].legend(fontsize=7, frameon=False, ncol=3)
    return report.save(fig, path)


def contracts(sets, path):
    fig, ax = plt.subplots(figsize=(7, 2.8))
    for i, k in enumerate(books(sets)):
        t = sets[k][1.0]["trades"]
        o = t[t["action"] == "open"]
        q = o.groupby(pd.to_datetime(o["date"]).dt.year)["qty"].mean()
        ax.plot(q.index, q.values, ["o-", "s--", "^:"][i % 3], color=report.color(i + 2, k),
                label=k)
    ax.set(title="Average contracts per entry (1x)", ylabel="contracts", ylim=(0, None))
    ax.legend(fontsize=7, frameon=False)
    return report.save(fig, path)


def fee(shares, plan):
    n = shares.abs()
    if plan == "fixed":
        return (n * FIXED[0]).clip(lower=FIXED[1])
    return (n * TIERED[0]).clip(lower=TIERED[1]) + n * TIERED[2]


def plans(sets):
    rows = []
    for k in books(sets):
        for m in MULTS:
            h = sets[k][m]["hedges"]
            for period, lo, hi in (("all", None, None), ("2023-2024", *RECENT)):
                x = report.between(h, "date", lo, hi) if len(h) else h
                n = x["shares"] if len(x) else pd.Series(dtype=float)
                rows.append({"book": k, "mult": m, "period": period, "orders": len(n),
                             "median_shares": float(n.abs().median()) if len(n) else 0.0,
                             "under_149": float((n.abs() < 149).mean()) if len(n) else 0.0,
                             "fixed": float(fee(n, "fixed").sum()),
                             "tiered": float(fee(n, "tiered").sum())})
    return pd.DataFrame(rows)


def tiered(sets, path):
    fig, ax = plt.subplots(figsize=(7, 2.8))
    for i, k in enumerate(books(sets)):
        h = sets[k][1.0]["hedges"]
        if h.empty:
            continue
        yr = pd.to_datetime(h["date"]).dt.year
        for plan, ls in (("fixed", "-"), ("tiered", "--")):
            y = fee(h["shares"], plan).groupby(yr).sum()
            ax.plot(y.index, y.values, ls, color=report.color(i + 2, k), label=f"{k} {plan}")
    ax.set(title="Hedge commissions by year, Fixed vs Tiered (1x)", ylabel="USD", ylim=(0, None))
    ax.legend(fontsize=7, frameon=False, ncol=2)
    return report.save(fig, path)


def held(out):
    # position open after each step: entry ts, exit ts
    rt = out["trades"]
    o = rt[rt["action"] == "open"]
    c = rt[rt["action"] == "close"].set_index("entry_ts")["ts"]
    return [(r.ts, c.get(r.ts, "9999"), r) for r in o.itertuples()]


def delta_pnl(out, root):
    # P&L of holding the book's option delta in SPY
    eq = out["equity"].drop_duplicates("ts", keep="last").reset_index(drop=True)
    spans, rows = held(out), []
    for i in range(len(eq) - 1):
        ts = eq["ts"].iloc[i]
        pos = next((p for a, b, p in spans if a <= ts < b), None)
        if pos is None:
            continue
        chain = pd.read_parquet(store.folder(pd.Timestamp(ts), root) / "chain.parquet")
        r = sim.row(chain, pos.expiry, pos.strike, pos.right)
        if r is None:
            continue
        shares = SIGN[pos.side] * float(r["delta"]) * pos.qty * 100
        rows.append({"date": eq["date"].iloc[i],
                     "delta_pnl": shares * (eq["spot"].iloc[i + 1] - eq["spot"].iloc[i])})
    return pd.DataFrame(rows)


def beta(sets, folder, root):
    rows, yearly = [], {}
    for m in MULTS:
        out = sets["unhedged"][m]
        d = delta_pnl(out, root)
        net = report.daily(out)
        rows.append({"mult": m, "net": float(net.sum()), "delta_pnl": float(d["delta_pnl"].sum()),
                     "rest": float(net.sum() - d["delta_pnl"].sum())})
        if m == 1.0:
            yr = pd.to_datetime(d["date"]).dt.year
            yearly = pd.DataFrame({"net": net.groupby(net.index.year).sum(),
                                   "delta": d["delta_pnl"].groupby(yr).sum()}).fillna(0)
    fig, ax = plt.subplots(figsize=(7, 2.8))
    w = 0.4
    ax.bar(yearly.index - w / 2, yearly["net"], w, color=report.color(4, "unhedged"),
           label="unhedged net P&L")
    ax.bar(yearly.index + w / 2, yearly["delta"], w, color="0.6", label="P&L of its delta in SPY")
    ax.axhline(0, color="k", lw=0.6)
    ax.set(title="Unhedged book: net P&L vs the P&L of its delta (1x)", ylabel="USD")
    ax.legend(fontsize=7, frameon=False)
    return pd.DataFrame(rows), report.save(fig, folder / "beta.png")


def tails(sets):
    rows = []
    for k in books(sets):
        for m in MULTS:
            d = report.daily(sets[k][m])
            eq = d.cumsum()
            dd = eq - eq.cummax().clip(lower=0)
            rows.append({"book": k, "mult": m, "worst_day": float(d.min()),
                         "worst_date": str(d.idxmin().date()), "dd_trough": str(dd.idxmin().date()),
                         "max_contracts": int(sets[k][m]["trades"]["qty"].max())})
    return pd.DataFrame(rows)


def extra(cfg, sets, folder):
    # sizing, Tiered re-pricing, beta split, tails
    root = engine.snapshots(config.load())
    p, t = plans(sets), tails(sets)
    split, beta_png = beta(sets, folder, root)
    for name, df in (("plans", p), ("tails", t), ("beta", split)):
        df.to_csv(folder / f"{name}.csv", index=False)
        print(f"\n{name}\n{df.round(2).to_string(index=False)}")
    return [contracts(sets, folder / "contracts.png"), tiered(sets, folder / "tiered.png"), beta_png]


def standard(sets, folder, limit):
    return [cum_pnl(sets, folder / "cum_pnl.png"), drawdown(sets, folder / "drawdown.png", limit),
            report.yearly(sets, folder / "yearly.png"), report.by_reason(sets, folder / "by_reason.png"),
            report.fees(sets, folder / "fees.png")]


def build(cfg, holdout=False):
    sets = load_sets(cfg, holdout)
    folder = FIGS / "holdout" if holdout else FIGS
    tab = report.table(sets)
    folder.mkdir(parents=True, exist_ok=True)
    tab.to_csv(folder / "table.csv", index=False)
    paths = [cum_pnl(sets, folder / "cum_pnl.png")] if holdout else (
        standard(sets, folder, budget(cfg)) + extra(cfg, sets, folder))
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
