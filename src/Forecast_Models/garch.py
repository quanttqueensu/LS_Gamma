import numpy as np
import pandas as pd
from scipy.optimize import minimize

TRADING_DAYS = 252.0
SCALE = 100.0


def _recursion(r2, omega, alpha, beta, h0):
    n = r2.size
    h = np.empty(n + 1)
    h[0] = h0
    for i in range(n):
        h[i + 1] = omega + alpha * r2[i] + beta * h[i]
    return h


def _nll(params, r2, target):
    alpha, beta = params
    if alpha <= 0 or beta <= 0 or alpha + beta >= 0.999:
        return 1e10
    omega = target * (1.0 - alpha - beta)
    h = _recursion(r2, omega, alpha, beta, target)[:-1]
    return 0.5 * np.sum(np.log(h) + r2 / h)


class Garch11:
    name = "garch"
    requires_fit = True
    min_history = 250

    def __init__(self, max_fit_window=1500, alpha0=0.08, beta0=0.90):
        self.max_fit_window = max_fit_window
        self.alpha0 = alpha0
        self.beta0 = beta0
        self.alpha = alpha0
        self.beta = beta0
        self.target = None
        self._n = 0
        self._h = None

    def fit(self, returns):
        r = np.asarray(returns, dtype=float) * SCALE
        r = r[np.isfinite(r)]
        if r.size < self.min_history:
            return
        if self.max_fit_window and r.size > self.max_fit_window:
            r = r[-self.max_fit_window:]

        target = float(np.mean(r * r))
        res = minimize(
            _nll, [self.alpha0, self.beta0], args=(r * r, target),
            method="Nelder-Mead",
            options={"xatol": 1e-4, "fatol": 1e-4, "maxiter": 400},
        )
        alpha, beta = res.x
        if not res.success or alpha <= 0 or beta <= 0 or alpha + beta >= 0.999:
            alpha, beta = self.alpha0, self.beta0

        self.alpha, self.beta, self.target = float(alpha), float(beta), target
        self._n, self._h = 0, None

    def _current_var(self, r2):
        omega = self.target * (1.0 - self.alpha - self.beta)
        if self._h is not None and r2.size >= self._n:
            tail = r2[self._n:]
            h = _recursion(tail, omega, self.alpha, self.beta, self._h)[-1]
        else:
            h = _recursion(r2, omega, self.alpha, self.beta, self.target)[-1]
        self._n, self._h = r2.size, h
        return omega, h

    def predict(self, returns, horizon):
        r = np.asarray(returns, dtype=float) * SCALE
        r = r[np.isfinite(r)]
        if r.size < self.min_history:
            return np.nan
        if self.target is None:
            self.fit(returns)
            if self.target is None:
                return np.nan

        omega, h_next = self._current_var(r * r)
        p = self.alpha + self.beta
        gap = h_next - self.target
        H = int(horizon)

        if abs(1.0 - p) < 1e-8:
            mean_var = h_next
        else:
            mean_var = self.target + gap * (1.0 - p ** H) / (H * (1.0 - p))

        return float(np.sqrt(TRADING_DAYS * mean_var) / SCALE)

    def describe(self):
        return {"name": self.name, "alpha": round(self.alpha, 4),
                "beta": round(self.beta, 4),
                "persistence": round(self.alpha + self.beta, 4)}


def load_returns(path="data/reference/spy_daily.parquet"):
    df = pd.read_parquet(path, columns=["date", "ret_ex_div"]).sort_values("date")
    return df["date"].to_numpy(), np.log1p(df["ret_ex_div"].to_numpy(float))


def forecast_series(dates, returns, horizon, model=None, refit_every=21):
    model = model or Garch11()
    n = len(returns)
    out = np.full(n, np.nan)
    last_fit = -10 ** 9

    for i in range(n):
        history = returns[:i]
        if history.size < model.min_history:
            continue
        if i - last_fit >= refit_every:
            model.fit(history)
            last_fit = i
        out[i] = model.predict(history, horizon)

    return pd.Series(out, index=dates, name="rv_forecast")