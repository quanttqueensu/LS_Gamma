import numpy as np
import pandas as pd

# two opposite sign conventions exist in this project and must never be
# compared without negating one:
#   spread       = rv_forecast - iv   ex-ante  > 0 -> vol cheap  -> long gamma
#   vrp_realized = iv - rv_forward    ex-post  > 0 -> premium earned -> short won
# on the training data the two have opposite means, so a sign slip inverts
# every conclusion drawn from them.

LG_THRESHOLD = 0.05
SG_THRESHOLD = -0.02

LONG_GAMMA = "long_gamma"
SHORT_GAMMA = "short_gamma"
FLAT = "flat"
NO_DATA = "no_data"

REPORT_LABELS = {
    LONG_GAMMA:  "IV UNDER | Long Gamma  | BUY ATM straddle. ",
    SHORT_GAMMA: "IV OVER  | Short Gamma | SELL OTM strangle.",
    FLAT:        "IV FAIR  | No action.                      ",
    NO_DATA:     "NO DATA  | No action.                      ",
}


def spread(rv_forecast, iv):
    return rv_forecast - iv


def _finite(x):
    try:
        return bool(np.isfinite(float(x)))
    except (TypeError, ValueError):
        return False


# each side is judged against the IV it would actually trade: long gamma buys
# an ATM straddle, short gamma sells the wings. matches Data/pipeline/signal.py.
# spread_strangle defaults to spread_atm so a single fitted value classifies.
def classify(spread_atm, spread_strangle=None,
             lg_threshold=LG_THRESHOLD, sg_threshold=SG_THRESHOLD):
    ss = spread_atm if spread_strangle is None else spread_strangle
    ok_atm, ok_str = _finite(spread_atm), _finite(ss)

    if not ok_atm and not ok_str:
        return NO_DATA
    if ok_atm and spread_atm > lg_threshold:
        return LONG_GAMMA
    if ok_str and ss < sg_threshold:
        return SHORT_GAMMA
    return FLAT


def classify_frame(df, atm_col="spread_atm", strangle_col="spread_strangle",
                   lg_threshold=LG_THRESHOLD, sg_threshold=SG_THRESHOLD,
                   out_col="regime"):
    out = df.copy()
    sa = pd.to_numeric(out[atm_col], errors="coerce").to_numpy(dtype=float)
    if strangle_col and strangle_col in out.columns:
        ss = pd.to_numeric(out[strangle_col], errors="coerce").to_numpy(dtype=float)
    else:
        ss = sa

    fa, fs = np.isfinite(sa), np.isfinite(ss)
    # long is tested before short, as in classify()
    out[out_col] = np.select(
        [~fa & ~fs, fa & (sa > lg_threshold), fs & (ss < sg_threshold)],
        [NO_DATA, LONG_GAMMA, SHORT_GAMMA],
        default=FLAT,
    )
    return out


def report(timestamp, rv_forecast, iv, lg_threshold=LG_THRESHOLD,
           sg_threshold=SG_THRESHOLD):
    s = spread(rv_forecast, iv)
    regime = classify(s, None, lg_threshold, sg_threshold)
    tail = "" if regime == NO_DATA else f" | spread {s:+.4f}"
    print(f"{timestamp} | {REPORT_LABELS[regime]}{tail}")
    return regime
