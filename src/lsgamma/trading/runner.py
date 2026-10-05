import argparse
from datetime import date

import pandas as pd

from lsgamma.core.Algos import broker
from lsgamma.core.Algos.Hedging import delta_hedge, portfolio
from lsgamma.forecasting import FORECASTERS
from lsgamma.pipeline import store
from lsgamma.signals import SIGNALS
from lsgamma.trading import config, exits, ledger, pnl, selection

TRADING_DAYS = 252
MIN_IV_COVERAGE = 0.5  # delayed greeks vanish after the close


class BadSnapshot(RuntimeError):
    pass


def horizon(dte):
    return max(1, round(dte * TRADING_DAYS / 365))


def spot(chain):
    return float(chain["und_price"].median())


def check(chain):
    coverage = chain["iv"].notna().mean()
    if coverage < MIN_IV_COVERAGE:
        raise BadSnapshot(f"only {coverage:.0%} of options have IV; run during market hours")


def decide(feats, chain, atm, cfg, today):
    expiry = selection.pick_expiry(chain, cfg)
    row = atm[atm["expiry"] == expiry].iloc[0]
    if pd.isna(row["atm_iv"]):
        raise BadSnapshot(f"no IV at the ATM strike for {expiry}; run during market hours")
    model = FORECASTERS[cfg["signal"]["forecaster"]]().fit(feats["ret"])
    rv = model.predict(horizon(row["dte"]))
    iv = float(row["atm_iv"])
    signal = SIGNALS[cfg["signal"]["model"]](rv, iv, cfg)
    return {"date": str(today), "expiry": str(expiry), "dte": int(row["dte"]),
            "rv_forecast": rv, "iv": iv, "vrp": iv - rv, "signal": signal}


def history(today, signal, n):
    log = ledger.read_log("signals")
    past = []
    if len(log):
        log = log.drop_duplicates("date", keep="last")
        past = log.loc[log["date"] != str(today), "signal"].tolist()
    return (past + [signal])[-n:]


def fill(ib, trade, cfg):
    if trade is None:
        return None
    if broker.wait_for_fill(ib, trade, cfg["execution"]["fill_timeout"]) != "Filled":
        ib.cancelOrder(trade.order)
        print(f"  not filled, cancelled: {broker.status(trade)}")
        return None
    print(f"  filled: {broker.status(trade)}")
    return trade.orderStatus.avgFillPrice


def close(ib, pos, chain, signal, hist, cfg, today, dry):
    mark = selection.mark(chain, pos["expiry"], pos["strike"], pos["right"])
    total = pnl.combined_pnl(pos, mark, spot(chain))
    reason = exits.exit_reason(pos, today, total, signal, hist, cfg)
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
    price = fill(ib, trade, cfg)
    if price is None:
        return pos
    ledger.log("trades", {"date": str(today), "action": "close", "side": pos["side"],
                          "right": pos["right"], "strike": pos["strike"],
                          "expiry": pos["expiry"], "qty": pos["qty"], "price": price,
                          "reason": reason, "pnl": pnl.combined_pnl(pos, price, spot(chain))})
    ledger.clear_position()
    return None


def enter(ib, signal, chain, cfg, today, dry):
    t = selection.trade_for(signal, chain, cfg)
    qty = cfg["size"]["quantity"]
    print(f"enter {signal}: {t['algo'].__name__.split('.')[-1]} {t['right']} "
          f"{t['strike']} {t['expiry']} x{qty}")
    if dry:
        return None

    trade = t["algo"].open_position(ib, t["expiry"], t["strike"], qty,
                                    cfg["execution"]["slippage"])
    price = fill(ib, trade, cfg)
    if price is None:
        return None
    pos = {"side": signal, "right": t["right"], "expiry": str(t["expiry"]),
           "strike": t["strike"], "qty": qty, "entry_price": price,
           "entry_date": str(today), "hedges": []}
    ledger.save_position(pos)
    ledger.log("trades", {**{k: v for k, v in pos.items() if k != "hedges"},
                          "date": str(today), "action": "open", "price": price})
    return pos


def hedge(ib, pos, cfg, today):
    trade = delta_hedge.hedge(ib, min_shares=cfg["hedge"]["min_shares"])
    if trade is None:
        print("hedge: no trade needed")
        return
    price = fill(ib, trade, cfg)
    if price is None:
        return
    sign = 1 if trade.order.action == "BUY" else -1
    row = {"date": str(today), "shares": sign * int(trade.orderStatus.filled), "price": price}
    ledger.log("hedges", row)
    if pos:
        pos["hedges"].append(row)
        ledger.save_position(pos)


def reconcile(ib, pos):
    held = portfolio.option_positions(ib)
    if len(held) != (1 if pos else 0):
        print(f"WARNING: IBKR holds {len(held)} SPY options, ledger has "
              f"{'1 position' if pos else 'none'}")


def run(ib, cfg, today, dry=False):
    feats, chain, atm = store.load("features"), store.load("chain"), store.load("atm_iv")
    check(chain)
    d = decide(feats, chain, atm, cfg, today)
    print(f"{d['date']}  rv {d['rv_forecast']:.3f}  iv {d['iv']:.3f}  "
          f"vrp {d['vrp']:+.3f}  signal {d['signal']}  ({d['expiry']}, {d['dte']} DTE)")
    hist = history(today, d["signal"], cfg["exit"]["flat_days"])
    if not dry:
        ledger.log("signals", d)
        reconcile(ib, ledger.load_position())

    pos = ledger.load_position()
    if pos:
        pos = close(ib, pos, chain, d["signal"], hist, cfg, today, dry)
    if pos is None and d["signal"] != "flat":
        pos = enter(ib, d["signal"], chain, cfg, today, dry)
    if not dry:
        hedge(ib, pos, cfg, today)
    return d


def main():
    p = argparse.ArgumentParser(description="Daily paper trading run")
    p.add_argument("--config", default=None)
    p.add_argument("--dry-run", action="store_true", help="print decisions, place nothing")
    p.add_argument("--skip-pipeline", action="store_true", help="use the latest snapshot")
    a = p.parse_args()
    cfg = config.load(a.config)
    gateway = cfg["execution"]["gateway"]

    if not a.skip_pipeline:
        from lsgamma.pipeline.build import build
        build(gateway=gateway)
    try:
        if a.dry_run:
            run(None, cfg, date.today(), dry=True)
            return
        with broker.connect(paper=True, gateway=gateway) as ib:
            run(ib, cfg, date.today())
    except BadSnapshot as e:
        raise SystemExit(f"SKIPPED, nothing traded or logged: {e}")


if __name__ == "__main__":
    main()
