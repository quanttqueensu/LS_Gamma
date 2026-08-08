
import math
import random
from datetime import datetime, timezone

from ib_async import IB, Stock, Option, MarketOrder

#configuration 
HOST, PORT, CLIENT_ID = '127.0.0.1', 4002, 1
UNDERLYING = 'SPY'
MIN_DTE, MAX_DTE = 7, 28
STRANGLE_OTM_PCT = 0.03      
CONTRACTS = 1

LG_THRESHOLD = 0.02          
SG_THRESHOLD = -0.05         


def rv_forecast():
    return random.uniform(0.3, 0.5)

def iv():
    return random.uniform(0.3, 0.5)

def vrp(realized_volatility_forecast, implied_volatility):
    return realized_volatility_forecast - implied_volatility


# ---------------- IBKR setup ----------------
ib = IB()
underlying = Stock(UNDERLYING, 'SMART', 'USD')
_strikes = []


def connect():
    ib.connect(HOST, PORT, clientId=CLIENT_ID)
    ib.reqMarketDataType(3)  # delayed data is fine for the MVP
    ib.qualifyContracts(underlying)
    print(f"Connected. Qualified {UNDERLYING}.")


def get_spot() -> float:
    ticker = ib.reqMktData(underlying)
    ib.sleep(2)
    px = ticker.marketPrice()
    if math.isnan(px):
        # fall back to last daily close (works when market is closed)
        bars = ib.reqHistoricalData(
            underlying, endDateTime='', durationStr='2 D',
            barSizeSetting='1 day', whatToShow='TRADES', useRTH=True)
        px = bars[-1].close
    return px


def pick_expiry() -> str:
    """Pick an expiration in the 7-28 DTE entry window."""
    global _strikes
    chains = ib.reqSecDefOptParams(
        underlying.symbol, '', underlying.secType, underlying.conId)
    chain = next(c for c in chains
                if c.exchange == 'SMART' and c.tradingClass == UNDERLYING)    
    today = datetime.now(timezone.utc).date()
    candidates = []
    for exp in sorted(chain.expirations):
        dte = (datetime.strptime(exp, '%Y%m%d').date() - today).days
        if MIN_DTE <= dte <= MAX_DTE:
            candidates.append((dte, exp))
    if not candidates:
        raise RuntimeError(f"No expiry in {MIN_DTE}-{MAX_DTE} DTE window")
    dte, exp = candidates[len(candidates) // 2]
    _strikes = sorted(chain.strikes)
    print(f"Selected expiry {exp} ({dte} DTE)")
    return exp


def nearest_strike(target: float) -> float:
    return min(_strikes, key=lambda s: abs(s - target))


def make_option(strike: float, right: str, expiry: str) -> Option:
    opt = Option(UNDERLYING, expiry, strike, right, 'SMART',
                 currency='USD', tradingClass=UNDERLYING)
    ib.qualifyContracts(opt)
    return opt


def execute_long_gamma_strategy(spot: float, expiry: str):

    k = nearest_strike(spot)
    call = make_option(k, 'C', expiry)
    put = make_option(k, 'P', expiry)
    t1 = ib.placeOrder(call, MarketOrder('BUY', CONTRACTS))
    t2 = ib.placeOrder(put, MarketOrder('BUY', CONTRACTS))
    print(f"LONG GAMMA → BUY straddle @ {k} x{CONTRACTS}")
    return t1, t2


def execute_short_gamma_strategy(spot: float, expiry: str):
    kc = nearest_strike(spot * (1 + STRANGLE_OTM_PCT))
    kp = nearest_strike(spot * (1 - STRANGLE_OTM_PCT))
    call = make_option(kc, 'C', expiry)
    put = make_option(kp, 'P', expiry)
    t1 = ib.placeOrder(call, MarketOrder('SELL', CONTRACTS))
    t2 = ib.placeOrder(put, MarketOrder('SELL', CONTRACTS))
    print(f"SHORT GAMMA → SELL strangle: {kp}P / {kc}C x{CONTRACTS}")
    return t1, t2

def main():
    connect()
    try:
        spot = get_spot()
        print(f"{UNDERLYING} spot: {spot:.2f}")
        expiry = pick_expiry()

        realized_volatility_forecast = rv_forecast()
        implied_volatility = iv()
        signal = vrp(realized_volatility_forecast, implied_volatility)
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"{timestamp} | RV: {realized_volatility_forecast:.4f} | "
              f"IV: {implied_volatility:.4f} | VRP: {signal:+.4f}")

        if signal > LG_THRESHOLD:
            print(f"{timestamp} | IV UNDER | Long Gamma  | BUY ATM straddle.")
            trades = execute_long_gamma_strategy(spot, expiry)
        elif signal < SG_THRESHOLD:
            print(f"{timestamp} | IV OVER  | Short Gamma | SELL OTM strangle.")
            trades = execute_short_gamma_strategy(spot, expiry)
        else:
            print(f"{timestamp} | IV FAIR  | No action.")
            trades = None

        # wait for order status updates
        if trades:
            ib.sleep(5)
            for t in trades:
                print(f"  {t.contract.right} {t.contract.strike}: "
                      f"{t.orderStatus.status}")

    finally:
        ib.disconnect()
        print("Disconnected.")


if __name__ == '__main__':
    main()