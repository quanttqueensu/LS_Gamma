import argparse

from lsgamma.core.Algos import broker
from lsgamma.core.Algos.Hedging import delta_hedge
from lsgamma.pipeline import store
from lsgamma.trading import config, selection


def wait(ib, trade, label, cfg):
    if trade is None:
        print(f"{label}: no order needed")
        return 0
    status = broker.wait_for_fill(ib, trade, cfg["execution"]["fill_timeout"])
    print(f"{label}: {broker.status(trade)}")
    if status != "Filled":
        ib.cancelOrder(trade.order)
        print(f"{label}: cancelled")
        return 0
    sign = 1 if trade.order.action == "BUY" else -1
    return sign * int(trade.orderStatus.filled)


def run(ib, cfg):
    chain = store.load("chain")
    slip = cfg["execution"]["slippage"]
    trades = [selection.trade_for(side, chain, cfg) for side in ("long", "short")]

    for t in trades:
        wait(ib, t["algo"].open_position(ib, t["expiry"], t["strike"], 1, slip), f"open {t['side']}", cfg)
    shares = wait(ib, delta_hedge.hedge(ib), "hedge", cfg)

    for t in trades:
        wait(ib, t["algo"].close_position(ib, t["expiry"], t["strike"], 1, slip), f"close {t['side']}", cfg)
    if shares:
        wait(ib, broker.submit_stock(ib, -shares), "unwind hedge", cfg)


def main():
    p = argparse.ArgumentParser(description="Open, hedge and close 1 call + 1 put on paper")
    p.add_argument("--yes", action="store_true", help="really place paper orders")
    a = p.parse_args()
    if not a.yes:
        raise SystemExit("places real paper orders; rerun with --yes")
    cfg = config.load()
    with broker.connect(paper=True, gateway=cfg["execution"]["gateway"]) as ib:
        run(ib, cfg)


if __name__ == "__main__":
    main()
