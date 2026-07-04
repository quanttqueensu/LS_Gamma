

import numpy as np
import pandas as pd
from arch import arch_model

TRADING_DAYS = 252


def garch_forecast(csv_path: str, horizon: int = 1) -> float:
    ret = pd.read_csv(csv_path)['ret'].dropna()

    model = arch_model(ret * 100, vol='GARCH', p=1, q=1, mean='Constant', dist='normal')
    res = model.fit(disp='off')

    fc = res.forecast(horizon=horizon, reindex=False)
    daily_var = fc.variance.values[-1] / 100**2         
    daily_vol = np.sqrt(daily_var.mean())                

    return float(daily_vol * np.sqrt(TRADING_DAYS))


if __name__ == '__main__':
    import sys
    print(garch_forecast(sys.argv[1], horizon=int(sys.argv[2]) if len(sys.argv) > 2 else 1))