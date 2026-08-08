

import numpy as np
import pandas as pd
from arch import arch_model

TRADING_DAYS = 252

# garch.py lives in src/forecast_models/ → up one level to src/, then into data/
DEFAULT_CSV = '/Users/gabe/LS_Gamma/src/data/returns.csv'


def garch_forecast(csv_path=DEFAULT_CSV, horizon: int = 1) -> float:
    """Fit GARCH(1,1) on daily log returns; return annualized vol forecast
    averaged over `horizon` days ahead."""
    ret = pd.read_csv(csv_path)['ret'].dropna()

    # arch is numerically happier with % returns; rescale back after
    model = arch_model(ret * 100, vol='GARCH', p=1, q=1, mean='Constant', dist='normal')
    res = model.fit(disp='off')

    fc = res.forecast(horizon=horizon, reindex=False)
    daily_var = fc.variance.values[-1] / 100**2          # de-scale
    daily_vol = np.sqrt(daily_var.mean())                # avg vol over horizon

    return float(daily_vol * np.sqrt(TRADING_DAYS))


if __name__ == '__main__':
    import sys

    args = sys.argv[1:]
    if args and args[0].isdigit():           # only horizon given
        csv_path, horizon = DEFAULT_CSV, int(args[0])
    elif args:                                # path given, maybe horizon too
        csv_path = args[0]
        horizon = int(args[1]) if len(args) > 1 else 1
    else:                                     # no args at all
        csv_path, horizon = DEFAULT_CSV, 1

    print(garch_forecast(csv_path, horizon=horizon))