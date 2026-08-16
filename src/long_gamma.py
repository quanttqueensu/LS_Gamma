import numpy as np

UNDERLYING = "SPY"
MULTIPLIER = 100
MAX_CAPITAL_PCT = 0.10
STRIKE_TOLERANCE = 0.01
STOP_LOSS_PCT = 0.50


def atm_strike(chain, spot, tolerance=STRIKE_TOLERANCE):
    listed = chain["strike"]
    if not len(listed):
        return np.nan
    hit = float(listed.iloc[(listed - spot).abs().argmin()])
    return hit if abs(hit / spot - 1) <= tolerance else np.nan


def leg_price(chain, strike, right):
    row = chain[(chain["strike"] == strike) & (chain["opt_type"] == right)]
    return float(row["vwap"].iloc[0]) if len(row) else np.nan


def size(premium, capital, max_pct=MAX_CAPITAL_PCT):
    cost = premium * MULTIPLIER
    if not np.isfinite(cost) or cost <= 0:
        return 0
    return int(capital * max_pct // cost)


def build(chain, spot, expiry, dte, capital, max_pct=MAX_CAPITAL_PCT):
    chain = chain[chain["expiry"] == expiry]
    strike = atm_strike(chain, spot)
    call = leg_price(chain, strike, "C")
    put = leg_price(chain, strike, "P")
    premium = call + put
    qty = size(premium, capital, max_pct)

    return {
        "regime": "long_gamma",
        "structure": "straddle",
        "underlying": UNDERLYING,
        "expiry": expiry,
        "dte": int(dte),
        "spot": float(spot),
        "legs": [
            {"right": "C", "strike": strike, "side": "BUY", "quantity": qty, "price": call},
            {"right": "P", "strike": strike, "side": "BUY", "quantity": qty, "price": put},
        ],
        "premium_per_contract": premium,
        "total_cost": premium * MULTIPLIER * qty,
        "max_loss": premium * MULTIPLIER * qty,
        "stop_loss_level": premium * (1 - STOP_LOSS_PCT),
        "valid": bool(qty > 0 and np.isfinite(premium)),
    }