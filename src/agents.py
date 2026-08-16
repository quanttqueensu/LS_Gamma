import json

import pandas as pd

import backtest as bt

AGENTS = {
    "agent0": dict(force_regime="short_gamma", structure="straddle",
                   hedge=False, use_stops=False),
    "agent1_switch": dict(hedge=False, use_stops=False),
    "agent2_hedge": dict(force_regime="short_gamma", structure="straddle",
                         hedge=True, use_stops=False),
    "agent3_stops": dict(force_regime="short_gamma", structure="straddle",
                         hedge=True, use_stops=True),
    "strategy": dict(),
}

FIELDS = ["total_pnl", "sharpe", "sortino", "max_drawdown", "trades",
          "win_rate", "avg_pnl", "pnl_from_options", "pnl_from_hedging",
          "total_costs", "stale_exits"]


def compare(data_dir, start=None, end=None, cost_mult=1.0, save=None, **kw):
    loaded = bt.load(data_dir)
    rows, detail = [], {}

    for name, cfg in AGENTS.items():
        trades, daily = bt.run(data_dir, start=start, end=end,
                               cost_mult=cost_mult, loaded=loaded, **{**cfg, **kw})
        if daily.empty:
            continue
        m = bt.metrics(daily, trades)
        detail[name] = m
        rows.append({"agent": name, **{f: m.get(f) for f in FIELDS}})
        if save:
            trades.to_parquet(f"{save}_{name}_trades.parquet", index=False)
            daily.to_parquet(f"{save}_{name}_daily.parquet", index=False)

    return pd.DataFrame(rows), detail


if __name__ == "__main__":
    import argparse
    from pathlib import Path

    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="Data/data")
    ap.add_argument("--start", default=None)
    ap.add_argument("--end", default=None)
    ap.add_argument("--cost-mult", type=float, default=1.0)
    ap.add_argument("--target-dte", type=int, default=bt.TARGET_DTE)
    ap.add_argument("--exit-dte", type=int, default=bt.EXIT_DTE)
    ap.add_argument("--save", default=None)
    ap.add_argument("--detail", action="store_true")
    a = ap.parse_args()

    if a.save:
        Path(a.save).parent.mkdir(parents=True, exist_ok=True)

    print(f"loading {a.data} ...")
    table, detail = compare(a.data, a.start, a.end, a.cost_mult, a.save,
                            target_dte=a.target_dte, exit_dte=a.exit_dte)

    pd.set_option("display.width", 220)
    pd.set_option("display.max_columns", None)
    print(f"\n{a.start or 'start'} to {a.end or 'end'}   cost_mult={a.cost_mult}")
    print()
    print(table.to_string(index=False))

    print("\nwhat each agent isolates")
    print("  agent0         always short ATM straddle, no hedge, no stops")
    print("  agent1_switch  regime switching, no hedge, no stops")
    print("  agent2_hedge   always short straddle, WITH hedge")
    print("  agent3_stops   always short straddle, hedge + stops")
    print("  strategy       full: switching + strangle wings + hedge + stops")

    if a.detail:
        print()
        print(json.dumps(detail, indent=2, default=str))