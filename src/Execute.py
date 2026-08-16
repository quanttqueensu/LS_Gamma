from pathlib import Path

import pandas as pd

import long_gamma
import short_gamma

DATA = Path(__file__).resolve().parent / "Data" / "data"
SIGNALS = DATA / "signals" / "regimes.parquet"
ORDERS = DATA / "orders"

TENOR = 28
CAPITAL = 50_000
DRY_RUN = True
PAPER = True
LIMIT_SLIPPAGE = 0.05


def occ_symbol(underlying, expiry, right, strike):
    return f"{underlying}{expiry:%y%m%d}{right}{int(round(strike * 1000)):08d}"


def load_signal(date=None):
    sig = pd.read_parquet(SIGNALS)
    sig["date"] = pd.to_datetime(sig["date"])
    if date is not None:
        sig = sig[sig["date"] == pd.Timestamp(date)]
    if sig.empty:
        raise ValueError(f"no signal for {date}")
    return sig.sort_values("date").iloc[-1]


def load_chain(date):
    path = DATA / "chain" / "daily" / f"{date:%Y-%m}.parquet"
    chain = pd.read_parquet(path)
    chain["date"] = pd.to_datetime(chain["date"])
    return chain[chain["date"] == date]


def load_forward(date, expiry):
    fwd = pd.read_parquet(DATA / "chain" / "forwards_daily.parquet")
    fwd["date"] = pd.to_datetime(fwd["date"])
    hit = fwd[(fwd["date"] == date) & (fwd["expiry"] == expiry)]
    return float(hit["forward"].iloc[0]) if len(hit) else float("nan")


def pick_expiry(chain, target_dte=TENOR):
    if chain.empty:
        return None, None
    row = chain.iloc[(chain["dte"] - target_dte).abs().argmin()]
    return row["expiry"], int(row["dte"])


def build_position(signal, chain, capital=CAPITAL):
    if signal["regime"] not in ("long_gamma", "short_gamma"):
        return None, f"regime is {signal['regime']}"

    expiry, dte = pick_expiry(chain)
    if expiry is None:
        return None, "no chain data for this date"

    if signal["regime"] == "long_gamma":
        return long_gamma.build(chain, signal["spot_close"], expiry, dte, capital), None

    forward = load_forward(signal["date"], expiry)
    return short_gamma.build(chain, signal["spot_close"], forward,
                             signal["iv_strangle"], expiry, dte, capital), None


def to_orders(position):
    if position is None or not position["valid"]:
        return []
    return [
        {
            "symbol": occ_symbol(position["underlying"], position["expiry"],
                                 leg["right"], leg["strike"]),
            "side": leg["side"],
            "quantity": leg["quantity"],
            "order_type": "LIMIT",
            "limit_price": round(leg["price"], 2),
            "time_in_force": "DAY",
        }
        for leg in position["legs"] if leg["quantity"] > 0
    ]


def submit(orders, dry_run=DRY_RUN):
    if not orders:
        print("no orders")
        return []
    for o in orders:
        tag = "DRY RUN" if dry_run else "SENDING"
        print(f"  {tag}  {o['side']:4s} {o['quantity']:>3} {o['symbol']} "
              f"@ {o['limit_price']:.2f}")
    return orders


def submit_ibkr(position, paper=PAPER, slippage=LIMIT_SLIPPAGE):
    import broker

    if position is None or not position["valid"]:
        print("nothing to send")
        return []

    with broker.connect(paper=paper, gateway=True) as ib:
        print(f"connected  account={ib.managedAccounts()}  "
              f"net_liq={broker.net_liquidation(ib):,.0f}")
        trades = broker.place(ib, position, limit_slippage=slippage)
        for row in broker.status(trades):
            print(f"  {row['status']:<12} {row['side']:4s} {row['quantity']:>3} "
                  f"{row['symbol']} @ {row['limit_price']:.2f}  "
                  f"filled={row['filled']}")
        return trades


def save(orders, date):
    if not orders:
        return None
    ORDERS.mkdir(parents=True, exist_ok=True)
    path = ORDERS / f"{date:%Y-%m-%d}.parquet"
    pd.DataFrame(orders).to_parquet(path, index=False)
    return path


def main(date=None, capital=CAPITAL, dry_run=DRY_RUN, send=False):
    signal = load_signal(date)
    chain = load_chain(signal["date"])
    position, reason = build_position(signal, chain, capital)

    print(f"{signal['date']:%Y-%m-%d}  regime={signal['regime']}  vrp={signal['vrp']:+.4f}")

    if position is None:
        print(f"no position: {reason}")
        return None

    print(f"{position['structure']}  expiry={position['expiry']} "
          f"dte={position['dte']}  valid={position['valid']}")

    orders = to_orders(position)
    submit(orders, dry_run)
    path = save(orders, signal["date"])
    if path:
        print(f"saved {path}")

    if send:
        submit_ibkr(position)

    return position


if __name__ == "__main__":
    import sys

    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    send = "--send" in sys.argv
    main(args[0] if args else None, dry_run=not send, send=send)