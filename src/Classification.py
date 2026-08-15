import numpy as np
import pandas as pd


LG_THRESHOLD_HIGH = 0.02
SG_THRESHOLD_LOW = -0.02

LONG_GAMMA = "long_gamma"
SHORT_GAMMA = "short_gamma"
FLAT = "flat"
NO_DATA = "no_data"


def vrp(realized_volatility_forecast, implied_volatility):
    return realized_volatility_forecast - implied_volatility


def classify(realized_volatility_forecast, implied_volatility,
             lg_threshold=LG_THRESHOLD_HIGH, sg_threshold=SG_THRESHOLD_LOW):
    spread = vrp(realized_volatility_forecast, implied_volatility)
    if not np.isfinite(spread):
        return NO_DATA
    if spread > lg_threshold:
        return LONG_GAMMA
    if spread < sg_threshold:
        return SHORT_GAMMA
    return FLAT


def report(timestamp, realized_volatility_forecast, implied_volatility,
           lg_threshold=LG_THRESHOLD_HIGH, sg_threshold=SG_THRESHOLD_LOW):
    regime = classify(realized_volatility_forecast, implied_volatility,
                      lg_threshold, sg_threshold)
    spread = vrp(realized_volatility_forecast, implied_volatility)

    if regime == LONG_GAMMA:
        print(f"{timestamp} | IV UNDER | Long Gamma  | BUY ATM straddle.  | vrp {spread:+.4f}")
    elif regime == SHORT_GAMMA:
        print(f"{timestamp} | IV OVER  | Short Gamma | SELL OTM strangle. | vrp {spread:+.4f}")
    elif regime == FLAT:
        print(f"{timestamp} | IV FAIR  | No action.                       | vrp {spread:+.4f}")
    else:
        print(f"{timestamp} | NO DATA  | No action.")
    print("------------------------------------------")
    return regime


def classify_frame(df, rv_col="rv_forecast", iv_col="iv_atm",
                   lg_threshold=LG_THRESHOLD_HIGH, sg_threshold=SG_THRESHOLD_LOW):
    out = df.copy()
    out["vrp"] = vrp(out[rv_col], out[iv_col])
    out["regime"] = np.select(
        [out["vrp"].isna(), out["vrp"] > lg_threshold, out["vrp"] < sg_threshold],
        [NO_DATA, LONG_GAMMA, SHORT_GAMMA],
        default=FLAT,
    )
    return out