from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib import cm

DATA = Path("Data/data")
OUT = Path("results/figures")

plt.rcParams.update({
    "figure.dpi": 130, "savefig.dpi": 130, "font.size": 9,
    "axes.grid": True, "grid.alpha": 0.25,
    "axes.spines.top": False, "axes.spines.right": False,
    "figure.facecolor": "white",
})


def load_smiles(data_dir=DATA):
    df = pd.read_parquet(Path(data_dir) / "surface" / "smile_params.parquet")
    df["date"] = pd.to_datetime(df["date"])
    return df[df["fit_ok"]]


def evaluate(row, k):
    return row["p0"] + row["p1"] * k + row["p2"] * k * k


def day_grid(smiles, date, n_k=60, dte_max=120):
    day = smiles[(smiles["date"] == pd.Timestamp(date)) & (smiles["dte"] <= dte_max)]
    day = day.sort_values("dte")
    if day.empty:
        return None
    rows = []
    for _, r in day.iterrows():
        ks = np.linspace(r["k_min"], r["k_max"], n_k)
        rows.append(pd.DataFrame({"dte": r["dte"], "k": ks, "iv": evaluate(r, ks)}))
    return pd.concat(rows, ignore_index=True)


def plot_surface_3d(smiles, date, out=None, dte_max=120):
    g = day_grid(smiles, date, dte_max=dte_max)
    if g is None:
        print(f"no fits for {date}")
        return

    dtes = sorted(g["dte"].unique())
    kmin, kmax = g["k"].min(), g["k"].max()
    kk = np.linspace(kmin, kmax, 60)
    Z = np.full((len(dtes), len(kk)), np.nan)

    day = smiles[smiles["date"] == pd.Timestamp(date)]
    for i, d in enumerate(dtes):
        r = day[day["dte"] == d].iloc[0]
        m = (kk >= r["k_min"]) & (kk <= r["k_max"])
        Z[i, m] = evaluate(r, kk[m])

    K, D = np.meshgrid(kk, dtes)
    fig = plt.figure(figsize=(9, 6))
    ax = fig.add_subplot(111, projection="3d")
    ax.plot_surface(K * 100, D, Z * 100, cmap=cm.viridis,
                    linewidth=0, antialiased=True, alpha=0.9)
    ax.set_xlabel("moneyness (% from forward)")
    ax.set_ylabel("days to expiry")
    ax.set_zlabel("implied volatility (%)")
    ax.set_title(f"SPY implied volatility surface, {pd.Timestamp(date).date()}")
    ax.view_init(elev=22, azim=-125)
    fig.tight_layout()
    fig.savefig(out or OUT / "surface_3d.png")
    plt.close(fig)


def plot_smiles(smiles, date, out=None, tenors=(7, 14, 28, 60, 90)):
    day = smiles[smiles["date"] == pd.Timestamp(date)]
    if day.empty:
        print(f"no fits for {date}")
        return

    fig, ax = plt.subplots(figsize=(8, 4.6))
    colors = cm.viridis(np.linspace(0.1, 0.9, len(tenors)))
    for c, t in zip(colors, tenors):
        r = day.iloc[(day["dte"] - t).abs().argmin()]
        if abs(r["dte"] - t) > 10:
            continue
        ks = np.linspace(r["k_min"], r["k_max"], 80)
        ax.plot(ks * 100, evaluate(r, ks) * 100, color=c, lw=1.8,
                label=f"{int(r['dte'])} DTE")
    ax.axvline(0, color="black", lw=0.7, ls="--", alpha=0.5)
    ax.set_xlabel("moneyness (% from forward)")
    ax.set_ylabel("implied volatility (%)")
    ax.set_title(f"Volatility smile by expiry, {pd.Timestamp(date).date()}")
    ax.legend(frameon=False, fontsize=8)
    fig.tight_layout()
    fig.savefig(out or OUT / "smiles.png")
    plt.close(fig)


def plot_compare(smiles, dates, out=None, tenor=28):
    fig, ax = plt.subplots(figsize=(8, 4.6))
    colors = cm.plasma(np.linspace(0.15, 0.8, len(dates)))
    for c, d in zip(colors, dates):
        day = smiles[smiles["date"] == pd.Timestamp(d)]
        if day.empty:
            continue
        r = day.iloc[(day["dte"] - tenor).abs().argmin()]
        ks = np.linspace(r["k_min"], r["k_max"], 80)
        ax.plot(ks * 100, evaluate(r, ks) * 100, color=c, lw=2,
                label=f"{pd.Timestamp(d).date()}  (ATM {r['atm_iv']*100:.1f}%)")
    ax.axvline(0, color="black", lw=0.7, ls="--", alpha=0.5)
    ax.set_xlabel("moneyness (% from forward)")
    ax.set_ylabel("implied volatility (%)")
    ax.set_title(f"Volatility smile across market regimes, {tenor} DTE")
    ax.legend(frameon=False, fontsize=8)
    fig.tight_layout()
    fig.savefig(out or OUT / "smile_regimes.png")
    plt.close(fig)


def plot_term_history(data_dir=DATA, out=None):
    ts = pd.read_parquet(Path(data_dir) / "surface" / "term_structure.parquet")
    ts["date"] = pd.to_datetime(ts["date"])
    wide = ts.pivot_table(index="date", columns="target_dte", values="atm_iv")

    fig, axes = plt.subplots(2, 1, figsize=(10, 6.5), sharex=True,
                             gridspec_kw={"height_ratios": [2, 1]})
    colors = cm.viridis(np.linspace(0.1, 0.9, len(wide.columns)))
    for c, col in zip(colors, wide.columns):
        axes[0].plot(wide.index, wide[col] * 100, color=c, lw=0.8, label=f"{col}d")
    axes[0].set_ylabel("ATM implied volatility (%)")
    axes[0].set_title("Constant-maturity ATM implied volatility")
    axes[0].legend(frameon=False, fontsize=8, ncol=6)

    if 60 in wide.columns and 7 in wide.columns:
        slope = (wide[60] - wide[7]) * 100
        axes[1].fill_between(slope.index, 0, slope, where=slope >= 0,
                             color="#2f855a", alpha=0.6, label="contango")
        axes[1].fill_between(slope.index, 0, slope, where=slope < 0,
                             color="#9b2c2c", alpha=0.6, label="backwardation")
        axes[1].axhline(0, color="black", lw=0.7)
        axes[1].set_ylabel("60d $-$ 7d (vol pts)")
        axes[1].set_title("Term structure slope")
        axes[1].legend(frameon=False, fontsize=8)
    fig.tight_layout()
    fig.savefig(out or OUT / "term_history.png")
    plt.close(fig)


def plot_skew_history(smiles, out=None, tenor=28, window=21):
    near = smiles[(smiles["dte"] - tenor).abs() <= 6]
    daily = near.groupby("date").agg(skew=("skew_slope", "median"),
                                     atm=("atm_iv", "median"))
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(daily.index, daily["skew"].rolling(window).mean(),
            color="#2b6cb0", lw=1.1)
    ax.axhline(0, color="black", lw=0.7, ls="--", alpha=0.5)
    ax.set_ylabel("skew slope (d sigma / d k)")
    ax.set_title(f"Volatility skew, {tenor} DTE, {window}-day average")
    fig.tight_layout()
    fig.savefig(out or OUT / "skew_history.png")
    plt.close(fig)


def build(data_dir=DATA, date=None, compare=None, outdir=OUT):
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    smiles = load_smiles(data_dir)

    if date is None:
        date = smiles["date"].max()
    print(f"surface date: {pd.Timestamp(date).date()}")

    plot_surface_3d(smiles, date, outdir / "surface_3d.png")
    plot_smiles(smiles, date, outdir / "smiles.png")
    plot_term_history(data_dir, outdir / "term_history.png")
    plot_skew_history(smiles, outdir / "skew_history.png")

    if compare:
        plot_compare(smiles, compare, outdir / "smile_regimes.png")

    print(f"figures written to {outdir}/")


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=str(DATA))
    ap.add_argument("--date", default=None, help="date to plot, defaults to latest")
    ap.add_argument("--compare", nargs="*", default=["2017-06-15", "2020-03-16", "2022-06-15"])
    ap.add_argument("--out", default=str(OUT))
    a = ap.parse_args()
    build(a.data, a.date, a.compare, a.out)