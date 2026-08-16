from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

AGENTS = ["agent0", "agent1_switch", "agent2_hedge", "agent3_stops", "strategy"]
LABELS = {
    "agent0": "Agent 0: naive short straddle",
    "agent1_switch": "Agent 1: + regime switching",
    "agent2_hedge": "Agent 2: + delta hedging",
    "agent3_stops": "Agent 3: + stop losses",
    "strategy": "Full strategy",
}
COLORS = {
    "agent0": "#2b6cb0", "agent1_switch": "#d69e2e", "agent2_hedge": "#2f855a",
    "agent3_stops": "#c05621", "strategy": "#9b2c2c",
}
CAPITAL = 50_000

plt.rcParams.update({
    "figure.dpi": 130, "savefig.dpi": 130, "font.size": 9,
    "axes.grid": True, "grid.alpha": 0.25, "axes.spines.top": False,
    "axes.spines.right": False, "figure.facecolor": "white",
})


def load(prefix):
    daily, trades = {}, {}
    for a in AGENTS:
        d = Path(f"{prefix}_{a}_daily.parquet")
        t = Path(f"{prefix}_{a}_trades.parquet")
        if d.exists():
            df = pd.read_parquet(d)
            df["date"] = pd.to_datetime(df["date"])
            daily[a] = df.sort_values("date")
        if t.exists():
            tf = pd.read_parquet(t)
            tf["net_pnl"] = tf["gross_pnl"] - tf["cost"]
            trades[a] = tf
    return daily, trades


def fig_equity(daily, out):
    fig, ax = plt.subplots(figsize=(9, 4.6))
    for a, d in daily.items():
        ax.plot(d["date"], d["equity"] - CAPITAL, label=LABELS[a],
                color=COLORS[a], lw=1.5 if a in ("agent0", "strategy") else 1.1)
    ax.axhline(0, color="black", lw=0.7, ls="--", alpha=0.5)
    ax.set_ylabel("cumulative P&L ($)")
    ax.set_title("Cumulative P&L by agent")
    ax.legend(frameon=False, fontsize=8, loc="upper left")
    ax.yaxis.set_major_formatter(lambda v, p: f"{v:,.0f}")
    fig.tight_layout()
    fig.savefig(out)
    plt.close(fig)


def fig_drawdown(daily, out):
    fig, ax = plt.subplots(figsize=(9, 3.6))
    for a, d in daily.items():
        eq = d["equity"]
        dd = (eq - eq.cummax()) / eq.cummax() * 100
        ax.plot(d["date"], dd, label=LABELS[a], color=COLORS[a],
                lw=1.5 if a in ("agent0", "strategy") else 1.1)
    ax.set_ylabel("drawdown (%)")
    ax.set_title("Drawdown from peak")
    ax.legend(frameon=False, fontsize=8, loc="lower left")
    fig.tight_layout()
    fig.savefig(out)
    plt.close(fig)


def fig_ablation(daily, out):
    tot = {a: d["pnl"].sum() for a, d in daily.items()}
    steps = [
        ("Agent 0\nbaseline", tot.get("agent0", 0), "#2b6cb0"),
        ("regime\nswitching", tot.get("agent1_switch", 0) - tot.get("agent0", 0), None),
        ("delta\nhedging", tot.get("agent2_hedge", 0) - tot.get("agent0", 0), None),
        ("stop\nlosses", tot.get("agent3_stops", 0) - tot.get("agent2_hedge", 0), None),
    ]
    fig, ax = plt.subplots(figsize=(7, 4))
    names = [s[0] for s in steps]
    vals = [s[1] for s in steps]
    cols = ["#2b6cb0"] + ["#2f855a" if v > 0 else "#9b2c2c" for v in vals[1:]]
    bars = ax.bar(names, vals, color=cols, width=0.6)
    for b, v in zip(bars, vals):
        ax.text(b.get_x() + b.get_width() / 2,
                v + (300 if v >= 0 else -900), f"{v:+,.0f}",
                ha="center", fontsize=9, fontweight="bold")
    ax.axhline(0, color="black", lw=0.8)
    ax.set_ylabel("P&L contribution ($)")
    ax.set_title("Component contribution to P&L")
    ax.yaxis.set_major_formatter(lambda v, p: f"{v:,.0f}")
    fig.tight_layout()
    fig.savefig(out)
    plt.close(fig)


def fig_attribution(daily, out):
    rows = []
    for a, d in daily.items():
        rows.append({"agent": a,
                     "options": d["pnl_option"].sum(),
                     "hedging": d["pnl_hedge"].sum(),
                     "costs": -d["cost"].sum()})
    df = pd.DataFrame(rows).set_index("agent").reindex([a for a in AGENTS if a in daily])

    fig, ax = plt.subplots(figsize=(8, 4))
    x = np.arange(len(df))
    w = 0.26
    ax.bar(x - w, df["options"], w, label="option leg", color="#2b6cb0")
    ax.bar(x, df["hedging"], w, label="hedging", color="#2f855a")
    ax.bar(x + w, df["costs"], w, label="costs", color="#9b2c2c")
    ax.set_xticks(x)
    ax.set_xticklabels([LABELS[a].split(":")[0] for a in df.index], fontsize=8)
    ax.axhline(0, color="black", lw=0.8)
    ax.set_ylabel("P&L ($)")
    ax.set_title("P&L attribution")
    ax.legend(frameon=False, fontsize=8)
    ax.yaxis.set_major_formatter(lambda v, p: f"{v:,.0f}")
    fig.tight_layout()
    fig.savefig(out)
    plt.close(fig)


def fig_trades(trades, out, agents=("agent0", "strategy")):
    have = [a for a in agents if a in trades]
    fig, axes = plt.subplots(1, len(have), figsize=(4.4 * len(have), 3.6), squeeze=False)
    for ax, a in zip(axes[0], have):
        v = trades[a]["net_pnl"]
        ax.hist(v, bins=25, color=COLORS[a], alpha=0.85, edgecolor="white")
        ax.axvline(0, color="black", lw=0.8, ls="--")
        ax.axvline(v.mean(), color="black", lw=1.2,
                   label=f"mean {v.mean():+,.0f}")
        ax.set_title(LABELS[a], fontsize=9)
        ax.set_xlabel("net P&L per trade ($)")
        ax.legend(frameon=False, fontsize=8)
    fig.tight_layout()
    fig.savefig(out)
    plt.close(fig)


def fig_frequency(monthly, weekly, out):
    fig, ax = plt.subplots(figsize=(7, 4))
    keys = [a for a in AGENTS if a in monthly and a in weekly]
    x = np.arange(len(keys))
    w = 0.36
    m = [monthly[a]["pnl"].sum() for a in keys]
    k = [weekly[a]["pnl"].sum() for a in keys]
    ax.bar(x - w / 2, m, w, label="28 DTE (monthly)", color="#2f855a")
    ax.bar(x + w / 2, k, w, label="7 DTE (weekly)", color="#9b2c2c")
    ax.set_xticks(x)
    ax.set_xticklabels([LABELS[a].split(":")[0] for a in keys], fontsize=8)
    ax.axhline(0, color="black", lw=0.8)
    ax.set_ylabel("net P&L ($)")
    ax.set_title("Net P&L by trade frequency")
    ax.legend(frameon=False, fontsize=8)
    ax.yaxis.set_major_formatter(lambda v, p: f"{v:,.0f}")
    fig.tight_layout()
    fig.savefig(out)
    plt.close(fig)


def fig_signal(data_dir, out, train_end="2021-12-31", tenor=28):
    data_dir = Path(data_dir)
    ev = pd.read_parquet(data_dir / "signals" / "realized_forward_EVALUATION_ONLY.parquet")
    ev = ev[ev["target_dte"] == tenor].copy()
    ev["date"] = pd.to_datetime(ev["date"])
    sig = pd.read_parquet(data_dir / "signals" / "regimes.parquet")
    sig["date"] = pd.to_datetime(sig["date"])

    j = sig[["date", "regime", "rv_forecast"]].merge(
        ev[["date", "rv_forward", "vrp_realized_atm"]], on="date").dropna()
    j = j[j["date"] <= train_end]
    j["err"] = j["rv_forecast"] - j["rv_forward"]

    order = ["flat", "long_gamma", "short_gamma"]
    order = [o for o in order if o in set(j["regime"])]
    hit = j.groupby("regime")["vrp_realized_atm"].apply(lambda s: (s < 0).mean())
    err = j.groupby("regime")["err"].mean()
    base = (j["vrp_realized_atm"] < 0).mean()

    fig, axes = plt.subplots(1, 2, figsize=(9.5, 3.8))
    c = ["#718096", "#9b2c2c", "#2f855a"]
    axes[0].bar(order, [hit[o] * 100 for o in order], color=c[:len(order)], width=0.55)
    axes[0].axhline(base * 100, color="black", ls="--", lw=1,
                    label=f"base rate {base*100:.1f}%")
    axes[0].set_ylabel("% of days realized beat implied")
    axes[0].set_title("Days realized exceeded implied, by regime")
    axes[0].legend(frameon=False, fontsize=8)

    axes[1].bar(order, [err[o] * 100 for o in order], color=c[:len(order)], width=0.55)
    axes[1].axhline(0, color="black", lw=0.8)
    axes[1].set_ylabel("mean forecast error (vol points)")
    axes[1].set_title("Mean forecast error by regime")
    fig.tight_layout()
    fig.savefig(out)
    plt.close(fig)


def summary_table(daily, trades):
    rows = []
    for a in AGENTS:
        if a not in daily:
            continue
        d = daily[a]
        r = d["pnl"] / CAPITAL
        eq = d["equity"]
        dd = ((eq - eq.cummax()) / eq.cummax()).min()
        down = r[r < 0].std()
        rows.append({
            "agent": a,
            "pnl": round(d["pnl"].sum(), 0),
            "sharpe": round(r.mean() / r.std() * np.sqrt(252), 3) if r.std() else None,
            "sortino": round(r.mean() / down * np.sqrt(252), 3) if down else None,
            "max_dd": round(dd, 4),
            "trades": len(trades.get(a, [])),
            "win_rate": round(float((trades[a]["net_pnl"] > 0).mean()), 3) if a in trades else None,
        })
    return pd.DataFrame(rows)


def build(prefix="results/agents28", weekly_prefix=None, data_dir="Data/data",
          outdir="results/figures"):
    out = Path(outdir)
    out.mkdir(parents=True, exist_ok=True)
    daily, trades = load(prefix)
    if not daily:
        raise SystemExit(f"no results found at {prefix}_*_daily.parquet")

    fig_equity(daily, out / "equity.png")
    fig_drawdown(daily, out / "drawdown.png")
    fig_ablation(daily, out / "ablation.png")
    fig_attribution(daily, out / "attribution.png")
    fig_trades(trades, out / "trades.png")

    if weekly_prefix:
        wd, _ = load(weekly_prefix)
        if wd:
            fig_frequency(daily, wd, out / "frequency.png")

    try:
        fig_signal(data_dir, out / "signal.png")
    except Exception as e:
        print(f"skipped signal figure: {e}")

    table = summary_table(daily, trades)
    table.to_csv(out / "summary.csv", index=False)
    print(table.to_string(index=False))
    print(f"\nfigures written to {out}/")
    return table


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--prefix", default="results/agents28")
    ap.add_argument("--weekly-prefix", default=None)
    ap.add_argument("--data", default="Data/data")
    ap.add_argument("--out", default="results/figures")
    a = ap.parse_args()
    build(a.prefix, a.weekly_prefix, a.data, a.out)