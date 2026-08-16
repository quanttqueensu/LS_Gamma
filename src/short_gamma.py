import numpy as np
from scipy.stats import norm

UNDERLYING = "SPY"
MULTIPLIER = 100
WING_DELTA = 0.25
STRIKE_TOLERANCE = 0.02
MAX_MARGIN_PCT = 0.25
STOP_LOSS_PCT = 0.30


def delta_strike(forward, iv, T, delta, is_put):
    target = 1.0 - delta if is_put else delta
    k = -norm.ppf(target) * iv * np.sqrt(T) + 0.5 * iv * iv * T
    return forward * np.exp(k)


def nearest_strike(chain, target, right, tolerance=STRIKE_TOLERANCE):
    listed = chain.loc[chain["opt_type"] == right, "strike"]
    if not len(listed) or not np.isfinite(target):
        return np.nan
    hit = float(listed.iloc[(listed - target).abs().argmin()])
    return hit if abs(hit / target - 1) <= tolerance else np.nan


def leg_price(chain, strike, right):
    row = chain[(chain["strike"] == strike) & (chain["opt_type"] == right)]
    return float(row["vwap"].iloc[0]) if len(row) else np.nan


def margin_per_contract(spot, put_strike, call_strike, premium):
    if not np.isfinite(put_strike) or not np.isfinite(call_strike):
        return np.nan
    put_otm = max(spot - put_strike, 0.0)
    call_otm = max(call_strike - spot, 0.0)
    put_req = max(0.20 * spot - put_otm, 0.10 * spot)
    call_req = max(0.20 * spot - call_otm, 0.10 * spot)
    return (max(put_req, call_req) + premium) * MULTIPLIER


def size(margin, capital, max_pct=MAX_MARGIN_PCT):
    if not np.isfinite(margin) or margin <= 0:
        return 0
    return int(capital * max_pct // margin)


def build(chain, spot, forward, iv, expiry, dte, capital,
          wing_delta=WING_DELTA, max_pct=MAX_MARGIN_PCT):
    chain = chain[chain["expiry"] == expiry]
    T = dte / 365.0

    put_strike = nearest_strike(chain, delta_strike(forward, iv, T, wing_delta, True), "P")
    call_strike = nearest_strike(chain, delta_strike(forward, iv, T, wing_delta, False), "C")
    put = leg_price(chain, put_strike, "P")
    call = leg_price(chain, call_strike, "C")
    premium = put + call

    margin = margin_per_contract(spot, put_strike, call_strike, premium)
    qty = size(margin, capital, max_pct)

    return {
        "regime": "short_gamma",
        "structure": "strangle",
        "underlying": UNDERLYING,
        "expiry": expiry,
        "dte": int(dte),
        "spot": float(spot),
        "wing_delta": wing_delta,
        "legs": [
            {"right": "P", "strike": put_strike, "side": "SELL", "quantity": qty, "price": put},
            {"right": "C", "strike": call_strike, "side": "SELL", "quantity": qty, "price": call},
        ],
        "premium_per_contract": premium,
        "total_credit": premium * MULTIPLIER * qty,
        "margin_required": margin * qty,
        "max_profit": premium * MULTIPLIER * qty,
        "stop_loss_level": premium * (1 + STOP_LOSS_PCT),
        "valid": bool(qty > 0 and np.isfinite(premium)),
    }