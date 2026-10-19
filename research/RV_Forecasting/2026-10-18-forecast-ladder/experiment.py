import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from lsgamma import experiments
from lsgamma.forecasting import FEATURE_FORECASTERS, FORECASTERS
from lsgamma.forecasting.HARX import target

NAME = "2026-10-18-forecast-ladder"
FIGS = Path(__file__).resolve().parent / "figures"
TRADING_DAYS = 252
COLORS = {"garch": "tab:grey", "har_gk": "tab:blue", "harx": "tab:orange", "rf": "tab:green"}

plt.rcParams.update({"figure.dpi": 150, "font.size": 9, "axes.grid": True,
                     "grid.alpha": 0.3, "axes.spines.top": False, "axes.spines.right": False})


def features(cfg):
    f = pd.read_parquet(experiments.REPO / cfg["data"]["features"])
    f = f[f.index < pd.Timestamp(cfg["data"]["holdout_start"])]
    return f.assign(true=target(f, cfg["model"]["horizon"]))


def window(f, end, years):
    # completed days before end, trailing years
    return f[(f.index < end) & (f.index >= end - pd.DateOffset(years=years))]


def dates(f, cfg):
    d = f[(f.index >= pd.Timestamp(cfg["data"]["start"]))].dropna(subset=["true", "vix"])
    return d.index


def garch(f, days, cfg):
    years, h = cfg["data"]["fit_years"], cfg["model"]["horizon"]
    model = FORECASTERS[cfg["model"]["reference"]]
    out = {}
    for t in days:
        r = window(f, t + pd.Timedelta(days=1), years)["ret"]
        out[t] = model().fit(r).predict(h)
    return pd.Series(out)


def monthly(f, days, name, cfg):
    # refit on the first day of each month
    years, h = cfg["data"]["fit_years"], cfg["model"]["horizon"]
    out, model, month = {}, None, None
    for t in days:
        if (t.year, t.month) != month:
            month = (t.year, t.month)
            model = FEATURE_FORECASTERS[name]().fit(window(f, t, years))
        out[t] = model.at(f.loc[:t].iloc[-30:]).predict(h)
    return pd.Series(out)


def run(cfg):
    f = features(cfg)
    days = dates(f, cfg)
    df = pd.DataFrame({"true": f.loc[days, "true"], "vix": f.loc[days, "vix"]})
    df["garch"] = garch(f, days, cfg)
    for name in cfg["model"]["candidates"]:
        df[name] = monthly(f, days, name, cfg)
        print(f"{name} done")
    return df


def qlike(true, vol):
    ratio = true / (vol ** 2 / TRADING_DAYS)
    return ratio - np.log(ratio) - 1


def bias(df, m):
    # forecast minus realized, vol points
    return 100 * (df[m] - np.sqrt(df["true"] * TRADING_DAYS))


def models(cfg):
    return [cfg["model"]["reference"], *cfg["model"]["candidates"]]


def nw_se(d, lags=22):
    # Newey-West standard error of the mean
    d = d.dropna().to_numpy()
    d = d - d.mean()
    n, v = len(d), (d @ d) / len(d)
    for k in range(1, lags + 1):
        v += 2 * (1 - k / (lags + 1)) * (d[k:] @ d[:-k]) / n
    return float(np.sqrt(v / n))


def scores(df, cfg):
    p, rows = cfg["pass"], []
    spans = [("all", df.index.min().year, df.index.max().year)] + [
        (f"{a}-{b}", int(a), int(b)) for a, b in p["periods"]]
    for label, a, b in spans:
        d = df[(df.index.year >= a) & (df.index.year <= b)]
        calm = d[d["vix"] < p["calm_vix"]]
        for m in models(cfg):
            gap = qlike(d["true"], d[m]) - qlike(d["true"], d["garch"])
            se = nw_se(gap)
            rows.append({"period": label, "model": m, "days": len(d), "calm_days": len(calm),
                         "qlike": qlike(d["true"], d[m]).mean(),
                         "calm_bias": bias(calm, m).median(), "bias": bias(d, m).median(),
                         "at_floor": int((d[m] <= 0.05 + 1e-9).sum()),
                         "nw_t": gap.mean() / se if se > 0 else np.nan})
    return pd.DataFrame(rows)


def checks(tab, cfg):
    p, ref, rows = cfg["pass"], cfg["model"]["reference"], []
    for a, b in p["periods"]:
        t = tab[tab["period"] == f"{a}-{b}"].set_index("model")
        for m in cfg["model"]["candidates"]:
            rows.append({"model": m, "period": f"{a}-{b}",
                         "qlike": t.loc[m, "qlike"], "qlike_garch": t.loc[ref, "qlike"],
                         "qlike_pass": t.loc[m, "qlike"] < t.loc[ref, "qlike"],
                         "calm_bias": t.loc[m, "calm_bias"], "calm_bias_garch": t.loc[ref, "calm_bias"],
                         "bias_pass": abs(t.loc[m, "calm_bias"]) < abs(t.loc[ref, "calm_bias"]),
                         "calm_days": t.loc[m, "calm_days"]})
    return pd.DataFrame(rows)


def verdicts(chk, cfg):
    out = {}
    for m, g in chk.groupby("model", sort=False):
        if (g["calm_days"] < cfg["pass"]["min_calm_days"]).any():
            out[m] = "INCONCLUSIVE"
        else:
            out[m] = "PASSED" if (g["qlike_pass"] & g["bias_pass"]).all() else "FAILED"
    return out


def yearly(df, cfg, path):
    fig, ax = plt.subplots(2, 1, figsize=(8, 4.6), sharex=True)
    for m in models(cfg):
        q = qlike(df["true"], df[m]).groupby(df.index.year).mean()
        ax[0].plot(q.index, q, marker="o", ms=3, color=COLORS[m], label=m)
        calm = df[df["vix"] < cfg["pass"]["calm_vix"]]
        b = bias(calm, m).groupby(calm.index.year).median()
        ax[1].plot(b.index, b, marker="o", ms=3, color=COLORS[m], label=m)
    ax[0].set(ylabel="mean QLIKE (lower is better)", title="Forecast loss by year")
    ax[1].axhline(0, color="black", lw=0.8)
    ax[1].set(ylabel="vol points", title="Median calm-day bias (forecast minus realized)")
    ax[0].legend(ncol=4, fontsize=8)
    return save(fig, path)


def levels(df, cfg, path):
    fig, ax = plt.subplots(figsize=(8, 3.5))
    real = np.sqrt(df["true"] * TRADING_DAYS) * 100
    ax.plot(real.groupby(df.index.year).median(), color="black", lw=2, label="realized")
    for m in models(cfg):
        ax.plot((df[m] * 100).groupby(df.index.year).median(), color=COLORS[m], label=m)
    ax.set(ylabel="annualized vol (%)", title="Median 22-day forecast and realized vol by year")
    ax.legend(ncol=5, fontsize=8)
    return save(fig, path)


def by_vix(df, cfg, path):
    edges = [0, 12, 15, 20, 25, 35, 100]
    band = pd.cut(df["vix"], edges)
    fig, ax = plt.subplots(figsize=(8, 3.5))
    w = 0.2
    for i, m in enumerate(models(cfg)):
        b = bias(df, m).groupby(band, observed=True).median()
        ax.bar(np.arange(len(b)) + (i - 1.5) * w, b, w, color=COLORS[m], label=m)
    ax.set_xticks(range(len(edges) - 1), [f"{a}-{b}" for a, b in zip(edges, edges[1:])])
    ax.axhline(0, color="black", lw=0.8)
    ax.set(xlabel="completed-day VIX", ylabel="vol points", title="Median bias by VIX level")
    ax.legend(ncol=4, fontsize=8)
    return save(fig, path)


def save(fig, path):
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)
    return path


def report(df, cfg):
    FIGS.mkdir(exist_ok=True)
    tab = scores(df, cfg)
    chk = checks(tab, cfg)
    tab.to_csv(FIGS / "scores.csv", index=False)
    chk.to_csv(FIGS / "pass_bar.csv", index=False)
    paths = [yearly(df, cfg, FIGS / "yearly.png"), levels(df, cfg, FIGS / "levels.png"),
             by_vix(df, cfg, FIGS / "by_vix.png")]
    print(tab.round(4).to_string(index=False))
    print("\npass bar")
    print(chk.round(4).to_string(index=False))
    print("\nverdicts:", verdicts(chk, cfg))
    print(f"{len(df)} forecast days; trials (runs): {len(experiments.trials(NAME))}")
    print("figures:", *[p.name for p in paths])


def main():
    p = argparse.ArgumentParser(description=NAME)
    p.add_argument("--report-only", action="store_true", help="rebuild from the saved run")
    a = p.parse_args()
    cfg = experiments.load_config(NAME)
    runs = experiments.trials(NAME)
    if a.report_only:
        df = pd.read_parquet(runs[-1] / "forecasts.parquet")
    else:
        if runs:
            raise SystemExit(f"{NAME} already has a run; use --report-only")
        run_dir = experiments.start_run(NAME, cfg)
        df = run(cfg)
        experiments.save(run_dir, df, "forecasts")
    report(df, cfg)


if __name__ == "__main__":
    main()
