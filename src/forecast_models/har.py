"""
HAR-RV volatility forecast (Corsi 2009).
"""

import numpy as np
import pandas as pd

TRADING_DAYS = 252


def har_forecast(csv_path: str) -> float:
    rv = pd.read_csv(csv_path)['rv'].dropna().reset_index(drop=True)

    daily = rv
    weekly = rv.rolling(5).mean()
    monthly = rv.rolling(22).mean()

    df = pd.DataFrame({
        'y': rv.shift(-1),      
        'd': daily,
        'w': weekly,
        'm': monthly,
    }).dropna()

    X = np.column_stack([np.ones(len(df)), df['d'], df['w'], df['m']])
    beta, *_ = np.linalg.lstsq(X, df['y'].values, rcond=None)

    x_last = np.array([1.0, daily.iloc[-1], weekly.iloc[-1], monthly.iloc[-1]])
    rv_next = max(float(x_last @ beta), 0.0)  

    return float(np.sqrt(rv_next * TRADING_DAYS))


if __name__ == '__main__':
    import sys
    print(har_forecast(sys.argv[1]))