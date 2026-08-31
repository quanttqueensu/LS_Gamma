from pathlib import Path

import pandas as pd

import features as F
from Classification import LG_THRESHOLD, SG_THRESHOLD, classify_frame

DATA = F.DATA
TENOR = F.PRIMARY_TENOR
FORECAST = "garch"
OUT = DATA / "signals" / "regimes.parquet"

# carried through from stage 4 unchanged; the strategy and Execute.py read these
PASSTHROUGH = ["target_dte", "spot_close", "iv_atm", "iv_strangle",
               "iv_put_wing", "iv_call_wing", "term_slope", "skew",
               "vix", "data_quality"]

DERIVED = ["rv_trailing", "rv_forecast", "forecast_model",
           "spread_atm", "spread_strangle", "regime"]
COLUMNS = ["date"] + PASSTHROUGH + DERIVED


def build(data_dir=DATA, tenor=TENOR, forecast=FORECAST,
          lg_threshold=LG_THRESHOLD, sg_threshold=SG_THRESHOLD):
    ctx = F.Context(data_dir, tenor)
    col = f"rv_forecast_{forecast}"
    f = F.features(ctx=ctx, names=["rv_trailing", col])

    out = ctx.signal[PASSTHROUGH].copy()
    out["rv_trailing"] = f["rv_trailing"]
    out["rv_forecast"] = f[col]
    out["forecast_model"] = forecast
    # both spreads come from the one forecast named above, so the file can
    # never mix two models' spreads the way the previous build did
    out["spread_atm"] = out["rv_forecast"] - out["iv_atm"]
    out["spread_strangle"] = out["rv_forecast"] - out["iv_strangle"]

    out = classify_frame(out, lg_threshold=lg_threshold,
                         sg_threshold=sg_threshold)
    return out.rename_axis("date").reset_index()[COLUMNS]


def summarise(out):
    lines = [
        f"{out['date'].min().date()} to {out['date'].max().date()}  "
        f"({len(out)} days, forecast={out['forecast_model'].iloc[0]})",
        "",
        out["regime"].value_counts().to_string(),
        "",
        out[["spread_atm", "spread_strangle"]].describe().round(4).to_string(),
    ]
    return "\n".join(lines)


def main(argv=None):
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=str(DATA))
    ap.add_argument("--tenor", type=int, default=TENOR)
    ap.add_argument("--forecast", default=FORECAST,
                    choices=["garch", "ewma"])
    ap.add_argument("--lg-threshold", type=float, default=LG_THRESHOLD)
    ap.add_argument("--sg-threshold", type=float, default=SG_THRESHOLD)
    ap.add_argument("--out", default=None)
    a = ap.parse_args(argv)

    out = build(Path(a.data), a.tenor, a.forecast,
                a.lg_threshold, a.sg_threshold)
    path = Path(a.out) if a.out else OUT
    path.parent.mkdir(parents=True, exist_ok=True)
    out.to_parquet(path, index=False)

    print(summarise(out))
    print(f"\nwrote {path}")
    return out


if __name__ == "__main__":
    main()
