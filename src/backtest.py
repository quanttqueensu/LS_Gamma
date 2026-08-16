from pathlib import Path

import numpy as np
import pandas as pd

CAPITAL = 50_000
CONTRACTS = 1
TARGET_DTE = 28
DTE_TOLERANCE = 5
EXIT_DTE = 3
MAX_HOLD_DTE = 40

WING_DELTA = 0.25
BAND_LONG = 0.10
BAND_SHORT = 0.15
STOP_LONG = 0.50
STOP_SHORT = 0.30

OPTION_SPREAD = 0.075
COMMISSION = 0.65
SHARE_SLIPPAGE = 0.01
MULTIPLIER = 100


def load(data_dir, max_dte=MAX_HOLD_DTE):
    data_dir = Path(data_dir)

    frames = []
    for p in sorted((data_dir / "iv" / "points").glob("*.parquet")):
        df = pd.read_parquet(p, columns=["date", "expiry", "dte", "strike", "opt_type",
                                         "vwap", "iv", "delta", "quality_flag"])
        frames.append(df[df["dte"] <= max_dte])
    points = pd.concat(frames, ignore_index=True)
    points["date"] = pd.to_datetime(points["date"])
    points["expiry"] = pd.to_datetime(points["expiry"])

    quotes = {
        (d, e, s, o): (v, iv, dl)
        for d, e, s, o, v, iv, dl in zip(
            points["date"], points["expiry"], points["strike"], points["opt_type"],
            points["vwap"], points["iv"], points["delta"])
    }

    spot = pd.read_parquet(data_dir / "reference" / "spy_daily.parquet",
                           columns=["date", "close"])
    spot["date"] = pd.to_datetime(spot["date"])
    spot = spot.set_index("date")["close"]

    sig = pd.read_parquet(data_dir / "signals" / "regimes.parquet")
    sig["date"] = pd.to_datetime(sig["date"])
    sig = sig.sort_values("date").set_index("date")

    return points, quotes, spot, sig


def pick_expiry(points, date, target=TARGET_DTE, tol=DTE_TOLERANCE):
    day = points[points["date"] == date]
    if day.empty:
        return None, None
    gaps = (day["dte"] - target).abs()
    row = day.loc[gaps.idxmin()]
    if abs(row["dte"] - target) > tol:
        return None, None
    return row["expiry"], int(row["dte"])


def pick_strikes(points, date, expiry, regime, spot_px, structure=None):
    day = points[(points["date"] == date) & (points["expiry"] == expiry)]
    if day.empty:
        return None

    sign = 1 if regime == "long_gamma" else -1
    kind = structure or ("straddle" if regime == "long_gamma" else "strangle")

    if kind == "straddle":
        calls = day[day["opt_type"] == "C"]
        if calls.empty:
            return None
        k = float(calls.loc[(calls["strike"] - spot_px).abs().idxmin(), "strike"])
        if abs(k / spot_px - 1) > 0.01:
            return None
        return [("C", k, sign), ("P", k, sign)]

    puts = day[(day["opt_type"] == "P") & day["delta"].notna()]
    calls = day[(day["opt_type"] == "C") & day["delta"].notna()]
    if puts.empty or calls.empty:
        return None
    kp = float(puts.loc[(puts["delta"].abs() - WING_DELTA).abs().idxmin(), "strike"])
    kc = float(calls.loc[(calls["delta"] - WING_DELTA).abs().idxmin(), "strike"])
    if kp >= spot_px or kc <= spot_px:
        return None
    return [("P", kp, sign), ("C", kc, sign)]


def mark(quotes, date, expiry, legs, last):
    prices, deltas, stale = [], [], False
    for right, strike, _ in legs:
        key = (date, expiry, strike, right)
        hit = quotes.get(key)
        if hit is None or not np.isfinite(hit[0]):
            prev = last.get((expiry, strike, right))
            if prev is None:
                return None, None, True
            price, dl = prev
            stale = True
        else:
            price, _, dl = hit
            if not np.isfinite(dl):
                dl = last.get((expiry, strike, right), (price, 0.0))[1]
            last[(expiry, strike, right)] = (price, dl)
        prices.append(price)
        deltas.append(dl)
    return np.array(prices), np.array(deltas), stale


def position_value(prices, legs, contracts=CONTRACTS):
    signs = np.array([s for _, _, s in legs])
    return float((signs * prices).sum() * contracts * MULTIPLIER)


def position_delta(deltas, legs, contracts=CONTRACTS):
    signs = np.array([s for _, _, s in legs])
    return float((signs * deltas).sum() * contracts * MULTIPLIER)


def option_cost(legs, contracts=CONTRACTS, mult=1.0):
    return len(legs) * contracts * (OPTION_SPREAD * MULTIPLIER + COMMISSION) * mult


def run(data_dir, start=None, end=None, cost_mult=1.0, hedge=True,
        contracts=CONTRACTS, capital=CAPITAL,
        band_long=BAND_LONG, band_short=BAND_SHORT, loaded=None,
        force_regime=None, structure=None, use_stops=True,
        target_dte=TARGET_DTE, exit_dte=EXIT_DTE):
    points, quotes, spot, sig = loaded if loaded is not None else load(data_dir)

    days = sorted(set(points["date"]) & set(spot.index) & set(sig.index))
    if start:
        days = [d for d in days if d >= pd.Timestamp(start)]
    if end:
        days = [d for d in days if d <= pd.Timestamp(end)]

    pos = None
    last = {}
    trades, daily = [], []
    equity = capital
    prev_regime = None

    for i, date in enumerate(days):
        spot_px = float(spot.loc[date])
        pnl_option = pnl_hedge = cost = 0.0
        action = ""

        if pos is not None:
            prices, deltas, stale = mark(quotes, date, pos["expiry"], pos["legs"], last)
            if prices is None:
                daily.append({"date": date, "pnl": 0.0, "equity": equity,
                              "in_position": True, "action": "no_mark"})
                continue

            value = position_value(prices, pos["legs"], contracts)
            pnl_option = value - pos["value"]
            pnl_hedge = pos["shares"] * (spot_px - pos["spot"])

            dte = (pos["expiry"] - date).days
            pnl_open = value - pos["entry_value"]
            stop_hit = (use_stops
                        and pnl_open < -pos["stop_pct"] * abs(pos["entry_value"]))

            if dte <= exit_dte or stop_hit:
                cost += option_cost(pos["legs"], contracts, cost_mult)
                cost += abs(pos["shares"]) * SHARE_SLIPPAGE * cost_mult
                action = "stop" if stop_hit else "expiry_exit"
                trades.append({
                    **{k: pos[k] for k in ("regime", "entry_date", "expiry",
                                           "entry_value", "entry_stale")},
                    "exit_date": date, "exit_value": value, "exit_stale": stale,
                    "days_held": (date - pos["entry_date"]).days,
                    "gross_pnl": value - pos["entry_value"] + pos["hedge_cum"] + pnl_hedge,
                    "hedge_pnl": pos["hedge_cum"] + pnl_hedge,
                    "cost": pos["cost_cum"] + cost,
                    "exit_reason": action,
                })
                pos = None
            else:
                target_shares = 0.0
                if hedge:
                    net = position_delta(deltas, pos["legs"], contracts)
                    band = band_long if pos["regime"] == "long_gamma" else band_short
                    if abs(net + pos["shares"]) > band * MULTIPLIER * contracts:
                        target_shares = -net
                        traded = target_shares - pos["shares"]
                        cost += abs(traded) * SHARE_SLIPPAGE * cost_mult
                        pos["shares"] = target_shares
                        action = "rehedge"
                pos["value"] = value
                pos["spot"] = spot_px
                pos["hedge_cum"] += pnl_hedge
                pos["cost_cum"] += cost

        if pos is None and i > 0:
            regime = force_regime or sig["regime"].get(days[i - 1])
            if regime in ("long_gamma", "short_gamma"):
                expiry, dte = pick_expiry(points, date, target_dte)
                legs = (pick_strikes(points, date, expiry, regime, spot_px, structure)
                        if expiry else None)
                if legs:
                    prices, deltas, stale = mark(quotes, date, expiry, legs, last)
                    if prices is not None:
                        value = position_value(prices, legs, contracts)
                        cost += option_cost(legs, contracts, cost_mult)
                        shares = 0.0
                        if hedge:
                            net = position_delta(deltas, legs, contracts)
                            shares = -net
                            cost += abs(shares) * SHARE_SLIPPAGE * cost_mult
                        pos = {
                            "regime": regime, "entry_date": date, "expiry": expiry,
                            "legs": legs, "entry_value": value, "value": value,
                            "spot": spot_px, "shares": shares, "hedge_cum": 0.0,
                            "cost_cum": cost, "entry_stale": stale,
                            "stop_pct": STOP_LONG if regime == "long_gamma" else STOP_SHORT,
                        }
                        action = "entry"

        pnl = pnl_option + pnl_hedge - cost
        equity += pnl
        daily.append({"date": date, "pnl": pnl, "pnl_option": pnl_option,
                      "pnl_hedge": pnl_hedge, "cost": cost, "equity": equity,
                      "in_position": pos is not None, "action": action})

    return pd.DataFrame(trades), pd.DataFrame(daily)


def metrics(daily, trades, capital=CAPITAL):
    d = daily.copy()
    d["ret"] = d["pnl"] / capital
    ann = 252
    mu, sd = d["ret"].mean(), d["ret"].std()
    downside = d.loc[d["ret"] < 0, "ret"].std()
    peak = d["equity"].cummax()
    dd = (d["equity"] - peak) / peak

    out = {
        "days": len(d),
        "total_pnl": round(float(d["pnl"].sum()), 2),
        "total_return": round(float(d["equity"].iloc[-1] / capital - 1), 4),
        "ann_return": round(float(mu * ann), 4),
        "ann_vol": round(float(sd * np.sqrt(ann)), 4),
        "sharpe": round(float(mu / sd * np.sqrt(ann)), 3) if sd > 0 else None,
        "sortino": round(float(mu / downside * np.sqrt(ann)), 3) if downside > 0 else None,
        "max_drawdown": round(float(dd.min()), 4),
        "time_in_market": round(float(d["in_position"].mean()), 3),
        "pnl_from_options": round(float(d["pnl_option"].sum()), 2),
        "pnl_from_hedging": round(float(d["pnl_hedge"].sum()), 2),
        "total_costs": round(float(d["cost"].sum()), 2),
    }

    if len(trades):
        t = trades.copy()
        t["net_pnl"] = t["gross_pnl"] - t["cost"]
        out.update({
            "trades": len(t),
            "win_rate": round(float((t["net_pnl"] > 0).mean()), 3),
            "avg_pnl": round(float(t["net_pnl"].mean()), 2),
            "avg_days_held": round(float(t["days_held"].mean()), 1),
            "stale_entries": int(t["entry_stale"].sum()),
            "stale_exits": int(t["exit_stale"].sum()),
            "by_regime": t.groupby("regime")["net_pnl"].agg(["count", "mean", "sum"]).round(2).to_dict(),
            "by_exit": t["exit_reason"].value_counts().to_dict(),
        })
    return out


if __name__ == "__main__":
    import argparse
    import json

    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="Data/data")
    ap.add_argument("--start", default=None)
    ap.add_argument("--end", default=None)
    ap.add_argument("--cost-mult", type=float, default=1.0)
    ap.add_argument("--band-long", type=float, default=BAND_LONG)
    ap.add_argument("--band-short", type=float, default=BAND_SHORT)
    ap.add_argument("--no-hedge", action="store_true")
    ap.add_argument("--save", default=None)
    a = ap.parse_args()

    print(f"loading {a.data} ...")
    loaded = load(a.data)
    print(f"{len(loaded[0]):,} option rows, {len(loaded[3]):,} signal days")

    trades, daily = run(a.data, start=a.start, end=a.end, cost_mult=a.cost_mult,
                        hedge=not a.no_hedge, band_long=a.band_long,
                        band_short=a.band_short, loaded=loaded)

    if daily.empty:
        print("no overlapping days; check the date range")
        raise SystemExit(1)

    print(f"\n{daily['date'].min().date()} to {daily['date'].max().date()}")
    print(json.dumps(metrics(daily, trades), indent=2, default=str))

    if len(trades):
        pd.set_option("display.width", 200)
        cols = ["entry_date", "exit_date", "regime", "days_held",
                "gross_pnl", "cost", "exit_reason"]
        print("\nlast 10 trades:")
        print(trades[cols].tail(10).to_string(index=False))

    if a.save:
        Path(a.save).parent.mkdir(parents=True, exist_ok=True)
        trades.to_parquet(f"{a.save}_trades.parquet", index=False)
        daily.to_parquet(f"{a.save}_daily.parquet", index=False)
        print(f"\nsaved {a.save}_trades.parquet and {a.save}_daily.parquet")