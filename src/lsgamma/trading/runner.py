import argparse
from datetime import date

import pandas as pd

from lsgamma.core.Algos import broker
from lsgamma.core.Algos.Hedging import delta_hedge, portfolio
from lsgamma.forecasting import FORECASTERS
from lsgamma.hub import desk
from lsgamma.pipeline import store
from lsgamma.signals import SIGNALS
from lsgamma.trading import config, exits, ledger, pnl, selection, sizing

TRADING_DAYS = 252
MIN_IV_COVERAGE = 0.5  # delayed greeks vanish after the close
CANCEL_WAIT = 5  # seconds for a cancel to confirm
LIVE_FLAGS = {"put_delta", "stress_budget", "stress_drop", "stress_vol"}  # live trades these
SIM_ONLY = {"first_day", "start", "end", "holdout_start", "spread_mult", "stress_mult",
            "commission_contract", "commission_share", "min_per_order", "share_half_spread"}


class BadSnapshot(RuntimeError):
    pass


def stamp(asof):
    return asof.isoformat(timespec="seconds")


def check_schedule(cfg):
    s = cfg["schedule"]
    if len(s["signal"]) != 1 or s["hedge"] != s["signal"]:
        raise SystemExit("live runner supports one run a day; intraday schedules are backtest-only")


def check_book(cfg):
    # refuse research flags live lacks
    base = config.backtest_defaults()
    off = sorted(k for k, v in cfg.get("backtest", {}).items()
                 if k not in LIVE_FLAGS | SIM_ONLY and v != base.get(k))
    if off:
        raise SystemExit(f"live runner does not implement [backtest] {', '.join(off)}; refused")


def horizon(dte):
    return max(1, round(dte * TRADING_DAYS / 365))


def spot(chain):
    return float(chain["und_price"].median())


def check(chain):
    coverage = chain["iv"].notna().mean()
    if coverage < MIN_IV_COVERAGE:
        raise BadSnapshot(f"only {coverage:.0%} of options have IV; run during market hours")


def completed(feats, asof):
    # forecasts use completed days only
    return feats[feats.index < pd.Timestamp(asof.date())]


def forecast(feats, cfg, asof, dte):
    model = FORECASTERS[cfg["signal"]["forecaster"]]().fit(completed(feats, asof)["ret"])
    return model.predict(horizon(dte))


def decide(feats, chain, atm, cfg, asof, rv_for=forecast):
    expiry = selection.pick_expiry(chain, cfg)
    row = atm[atm["expiry"] == expiry].iloc[0]
    if pd.isna(row["atm_iv"]):
        raise BadSnapshot(f"no IV at the ATM strike for {expiry}; run during market hours")
    rv = rv_for(feats, cfg, asof, int(row["dte"]))
    iv = float(row["atm_iv"])
    signal = SIGNALS[cfg["signal"]["model"]](rv, iv, cfg)
    return {"date": str(asof.date()), "ts": stamp(asof), "expiry": str(expiry),
            "dte": int(row["dte"]), "rv_forecast": rv, "iv": iv, "vrp": iv - rv, "signal": signal}


def history(today, signal, n):
    return recent(ledger.read_log("signals"), today, signal, n)


def recent(log, today, signal, n):
    # flat exit counts days: last signal per day
    past = []
    if len(log):
        log = log.drop_duplicates("date", keep="last")
        past = log.loc[log["date"] != str(today), "signal"].tolist()
    return (past + [signal])[-n:]


def fill(ib, trade, cfg):
    # (avg price, filled qty); None if nothing filled
    if trade is None:
        return None
    if broker.wait_for_fill(ib, trade, cfg["execution"]["fill_timeout"]) != "Filled":
        ib.cancelOrder(trade.order)
        broker.wait_for_fill(ib, trade, CANCEL_WAIT)  # late fills land first
        print(f"  not filled, cancelled: {broker.status(trade)}")
        if not trade.isDone():
            print("  WARNING: cancel not confirmed; check IBKR")
    else:
        print(f"  filled: {broker.status(trade)}")
    n = int(trade.orderStatus.filled)
    return (trade.orderStatus.avgFillPrice, n) if n else None


def close(ib, pos, chain, signal, hist, cfg, asof, dry):
    mark = selection.mark(chain, pos["expiry"], pos["strike"], pos["right"])
    total = pnl.combined_pnl(pos, mark, spot(chain))
    reason = exits.exit_reason(pos, asof.date(), total, signal, hist, cfg)
    print(f"position {pos['side']} {pos['right']} {pos['strike']} {pos['expiry']}"
          f"  mark {mark:.2f}  pnl {total:.2f}  exit {reason}")
    if reason is None:
        return pos
    if dry:
        print(f"  would close ({reason})")
        return None

    algo = selection.ALGOS[pos["side"]]
    expiry = date.fromisoformat(pos["expiry"])
    trade = algo.close_position(ib, expiry, pos["strike"], pos["qty"],
                                cfg["execution"]["slippage"])
    got = fill(ib, trade, cfg)
    if got is None:
        return pos
    price, n = got
    part = n < pos["qty"]
    done = {**pos, "qty": n}
    total = pnl.option_pnl(done, price) if part else pnl.combined_pnl(pos, price, spot(chain))
    ledger.log("trades", {"date": str(asof.date()), "ts": stamp(asof), "action": "close",
                          "side": pos["side"], "right": pos["right"], "strike": pos["strike"],
                          "expiry": pos["expiry"], "qty": n, "price": price,
                          "reason": reason, "pnl": total})
    if part:
        # rest stays open with the hedges
        print(f"  partial close {n} of {pos['qty']}; the rest stays open")
        rest = {**pos, "qty": pos["qty"] - n}
        ledger.save_position(rest)
        return rest
    ledger.clear_position()
    return None


def carried(shares, chain, asof):
    # shares left from the last position
    if not shares:
        return []
    return [{"date": str(asof.date()), "ts": stamp(asof), "shares": int(shares),
             "price": spot(chain)}]


def last_stop():
    t = ledger.read_log("trades")
    if t.empty or "reason" not in t:
        return None
    stops = t[(t["action"] == "close") & (t["reason"] == "stop")]
    return None if stops.empty else (stops["side"].iloc[-1], stops["date"].iloc[-1])


def pick(signal, chain, cfg, asof):
    # strike and size, same rules as backtests
    t = selection.trade_for(signal, chain, cfg)
    t = {**t, "strike": sizing.put_strike(t, chain, sizing.flag(cfg, "put_delta"))}
    return t, sizing.contracts(cfg, signal, t, chain, asof)


def enter(ib, signal, chain, cfg, asof, dry):
    t, qty = pick(signal, chain, cfg, asof)
    print(f"enter {signal}: {t['algo'].__name__.split('.')[-1]} {t['right']} "
          f"{t['strike']} {t['expiry']} x{qty}")
    if not qty:
        print(f"no {signal} entry: stress budget below one contract")
        return None
    if dry:
        return None

    trade = t["algo"].open_position(ib, t["expiry"], t["strike"], qty,
                                    cfg["execution"]["slippage"])
    got = fill(ib, trade, cfg)
    if got is None:
        return None
    price, n = got
    if n < qty:
        print(f"  partial fill {n} of {qty}")
    pos = {"side": signal, "right": t["right"], "expiry": str(t["expiry"]),
           "strike": t["strike"], "qty": n, "entry_price": price,
           "entry_date": str(asof.date()), "entry_ts": stamp(asof),
           "hedges": carried(portfolio.stock_position(ib), chain, asof)}
    ledger.save_position(pos)
    ledger.log("trades", {**{k: v for k, v in pos.items() if k != "hedges"},
                          "date": str(asof.date()), "ts": stamp(asof), "action": "open",
                          "price": price})
    return pos


def hedge(ib, pos, cfg, asof, ref):
    trade = delta_hedge.hedge(ib, ref, min_shares=cfg["hedge"]["min_shares"],
                              pad=cfg["execution"]["stock_pad"])
    if trade is None:
        print("hedge: no trade needed")
        return
    got = fill(ib, trade, cfg)
    if got is None:
        return
    price, n = got
    sign = 1 if trade.order.action == "BUY" else -1
    row = {"date": str(asof.date()), "ts": stamp(asof), "shares": sign * n, "price": price}
    ledger.log("hedges", row)
    if pos:
        pos["hedges"].append(row)
        ledger.save_position(pos)


def reconcile(ib, pos):
    # IBKR vs ledger: expiry, strike, right, qty
    held = sorted((c.lastTradeDateOrContractMonth, float(c.strike), c.right, int(q))
                  for c, q in portfolio.option_positions(ib))
    want = [(pos["expiry"].replace("-", ""), float(pos["strike"]), pos["right"],
             pnl.SIGN[pos["side"]] * pos["qty"])] if pos else []
    if held != want:
        print(f"WARNING: IBKR holds {held or 'no SPY options'}, ledger has {want or 'none'}")


def run(ib, cfg, asof, dry=False):
    feats, chain, atm = (store.load(n, asof) for n in ("features", "chain", "atm_iv"))
    check(chain)
    d = decide(feats, chain, atm, cfg, asof)
    print(f"{d['date']}  rv {d['rv_forecast']:.3f}  iv {d['iv']:.3f}  "
          f"vrp {d['vrp']:+.3f}  signal {d['signal']}  ({d['expiry']}, {d['dte']} DTE)")
    hist = history(asof.date(), d["signal"], cfg["exit"]["flat_days"])
    if not dry:
        ledger.log("signals", d)
        reconcile(ib, ledger.load_position())

    pos = ledger.load_position()
    if pos:
        pos = close(ib, pos, chain, d["signal"], hist, cfg, asof, dry)
    if pos is None and d["signal"] != "flat":
        if exits.cooling(d["signal"], last_stop(), asof.date(), cfg["exit"]["stop_cooloff_days"]):
            print(f"no {d['signal']} entry: stop cool-off ({cfg['exit']['stop_cooloff_days']} days)")
        else:
            pos = enter(ib, d["signal"], chain, cfg, asof, dry)
    if not dry:
        hedge(ib, pos, cfg, asof, spot(chain))
        publish(chain, cfg)
    return d


def publish(chain, cfg):
    # hub snapshot; never blocks trading
    try:
        print(f"desk snapshot -> {desk.write(chain, cfg)}")
    except (OSError, KeyError, ValueError) as e:
        print(f"WARNING: desk snapshot not written ({e})")
    try:
        from lsgamma.trading import shadow  # engine imports runner
        print(f"shadow books -> {shadow.write()}")
    except (Exception, SystemExit) as e:
        print(f"WARNING: shadow books not written ({e})")


def main():
    p = argparse.ArgumentParser(description="Daily paper trading run")
    p.add_argument("--config", default=None)
    p.add_argument("--dry-run", action="store_true", help="print decisions, place nothing")
    p.add_argument("--skip-pipeline", action="store_true", help="use the latest snapshot")
    a = p.parse_args()
    cfg = config.load(a.config)
    check_schedule(cfg)
    check_book(cfg)
    if config.pointer(cfg):
        print(f"live book: {config.pointer(cfg)}")
    gateway = cfg["execution"]["gateway"]

    if not a.skip_pipeline:
        from lsgamma.pipeline.build import build
        build(gateway=gateway)
    try:
        if a.dry_run:
            run(None, cfg, store.now(), dry=True)
            return
        with broker.connect(paper=True, gateway=gateway) as ib:
            run(ib, cfg, store.now())
    except BadSnapshot as e:
        raise SystemExit(f"SKIPPED, nothing traded or logged: {e}")


if __name__ == "__main__":
    main()
