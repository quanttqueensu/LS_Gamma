"""Build today's data snapshot for paper trading.

Run once per day during market hours (IBKR delayed data lags ~15 min):
    python -m lsgamma.pipeline.build                 # everything (TWS must be running)
    python -m lsgamma.pipeline.build --no-chain      # yfinance only
    python -m lsgamma.pipeline.build --all-expiries  # every expiry, not just Fridays
"""

import argparse
import time

from lsgamma.pipeline import features, market, store


def build(chain=True, all_expiries=False, gateway=False):
    spy = market.spy_daily()
    idx = market.indices()
    feats = features.build_features(spy, idx)

    for name, df in [("spy_daily", spy), ("indices", idx), ("features", feats)]:
        print(f"saved {store.save(df, name)}  ({len(df)} rows)")

    if chain:
        # Imported here so --no-chain works without TWS
        from lsgamma.core.Algos import broker
        from lsgamma.pipeline.chain import option_chain

        start = time.time()
        with broker.connect(paper=True, gateway=gateway) as ib:
            ch = option_chain(ib, fridays_only=not all_expiries)
        atm = features.atm_iv(ch)
        for name, df in [("chain", ch), ("atm_iv", atm)]:
            print(f"saved {store.save(df, name)}  ({len(df)} rows)")
        print(f"chain pulled in {time.time() - start:.0f}s")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--no-chain", action="store_true", help="skip the IBKR option chain")
    p.add_argument("--all-expiries", action="store_true", help="include non-Friday expiries")
    p.add_argument("--gateway", action="store_true", help="connect to IB Gateway instead of TWS")
    a = p.parse_args()
    build(chain=not a.no_chain, all_expiries=a.all_expiries, gateway=a.gateway)


if __name__ == "__main__":
    main()
