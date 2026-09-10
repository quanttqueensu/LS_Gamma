import numpy as np
import pandas as pd

TARGET = "spread_realized_atm"
HORIZON = 19
MIN_TRAIN = 250
REFIT_EVERY = 21

# nested ladder: each spec adds one idea to the one above it
SPECS = {
    "m0_constant": [],
    "m1_iv": ["iv_atm"],
    "m2_garch": ["iv_atm", "rv_forecast_garch"],
    "m3_slope": ["iv_atm", "rv_forecast_garch", "term_slope"],
    "m3_ivz": ["iv_atm", "rv_forecast_garch", "iv_z"],
}


def design(df, names):
    cols = [np.ones(len(df))] + [df[n].to_numpy(dtype=float) for n in names]
    return np.column_stack(cols)


def fit(X, y):
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    return beta


# Newey-West with Bartlett weights. overlapping targets make naive OLS
# standard errors far too small, so lag must be at least the overlap.
def hac_cov(X, resid, lag):
    u = resid[:, None] * X
    S = u.T @ u
    for l in range(1, min(lag, len(u) - 1) + 1):
        G = u[l:].T @ u[:-l]
        S += (1.0 - l / (lag + 1.0)) * (G + G.T)
    XtX_inv = np.linalg.pinv(X.T @ X)
    return XtX_inv @ S @ XtX_inv


def summary(df, names, target=TARGET, lag=HORIZON):
    d = df[[target] + names].dropna()
    X, y = design(d, names), d[target].to_numpy(dtype=float)
    beta = fit(X, y)
    se = np.sqrt(np.diag(hac_cov(X, y - X @ beta, lag)))
    return pd.DataFrame({"coef": beta, "hac_se": se, "t": beta / se},
                        index=["const"] + names).round(4)


# a row s is usable for a fit made at row i only once its forward window has
# closed. s + win <= i is one day stricter than strictly necessary, which is
# the safe direction to err in.
def embargo_mask(n, i, win):
    return np.arange(n) + win <= i


def predict_pit(df, names, target=TARGET, win=HORIZON,
                min_train=MIN_TRAIN, refit_every=REFIT_EVERY,
                mask_fn=embargo_mask):
    X = design(df, names)
    y = df[target].to_numpy(dtype=float)
    fittable = np.isfinite(y) & np.isfinite(X).all(axis=1)
    predictable = np.isfinite(X).all(axis=1)

    out = np.full(len(df), np.nan)
    beta, last_fit = None, None

    for i in range(len(df)):
        if not predictable[i]:
            continue
        if beta is None or i - last_fit >= refit_every:
            usable = fittable & mask_fn(len(df), i, win)
            if usable.sum() >= min_train:
                beta, last_fit = fit(X[usable], y[usable]), i
        if beta is not None:
            out[i] = X[i] @ beta

    return pd.Series(out, index=df.index, name="vrp_hat")


def score(pred, actual, label=""):
    d = pd.concat([pred.rename("p"), actual.rename("a")], axis=1).dropna()
    if d.empty:
        return {"spec": label, "n": 0}
    err = d["p"] - d["a"]
    sst = ((d["a"] - d["a"].mean()) ** 2).sum()
    return {
        "spec": label,
        "n": len(d),
        "rmse": round(float(np.sqrt((err ** 2).mean())), 5),
        "r2": round(float(1 - (err ** 2).sum() / sst), 4) if sst > 0 else None,
        "ic": round(float(d["p"].corr(d["a"], method="spearman")), 4),
        "hit": round(float((np.sign(d["p"]) == np.sign(d["a"])).mean()), 4),
    }


def compare(df, specs=None, target=TARGET, start=None, end=None, **kw):
    specs = specs or SPECS
    rows = []
    for label, names in specs.items():
        pred = predict_pit(df, names, target, **kw)
        sl = slice(start, end)
        rows.append(score(pred[sl], df[target][sl], label))
    return pd.DataFrame(rows)


def main(argv=None):
    import argparse

    import features as F

    ap = argparse.ArgumentParser()
    ap.add_argument("--train-end", default="2021-12-31")
    ap.add_argument("--test-start", default="2022-01-01")
    ap.add_argument("--test-end", default="2023-12-31")
    ap.add_argument("--target", default=TARGET)
    ap.add_argument("--lag", type=int, default=HORIZON)
    a = ap.parse_args(argv)

    pd.set_option("display.width", 200)
    df = F.aligned()
    train = df[df.index <= a.train_end]
    eff = len(train.dropna(subset=[a.target])) // a.lag
    print(f"train {len(train)} rows, effective N ~ {eff}\n")

    for label, names in SPECS.items():
        print(f"--- {label}  {names}")
        print(summary(train, names, a.target, a.lag).to_string(), "\n")

    print(f"out-of-sample {a.test_start} to {a.test_end}")
    print(compare(df, target=a.target,
                  start=a.test_start, end=a.test_end).to_string(index=False))


if __name__ == "__main__":
    main()
