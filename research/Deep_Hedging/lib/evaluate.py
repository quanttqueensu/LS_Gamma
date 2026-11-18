"""Paired comparison statistics for two hedging policies on the same episodes.

Episodes start every trading day and overlap, so per-episode P&L differences are
strongly autocorrelated. The confidence interval for the mean improvement comes
from a moving-block bootstrap over calendar months (circular wrap), which keeps
the within-month and adjacent-month dependence intact.
"""
import math

import numpy as np
import pandas as pd


def _month_totals(diff, months):
    """Per-month sum and count of diff, months in calendar order."""
    s = pd.Series(np.asarray(diff, float)).groupby(np.asarray(months)).agg(["sum", "count"])
    s = s.sort_index()  # "YYYY-MM" labels sort chronologically
    return s["sum"].to_numpy(), s["count"].to_numpy()


def block_bootstrap(diff, months, n_boot=10000, block=3, seed=0, alpha=0.05):
    """Moving-block bootstrap of mean(diff) over calendar months.

    Blocks of `block` consecutive months start uniformly at random over all
    months and wrap circularly past the last month, so every month is equally
    likely to be drawn. Blocks are concatenated and cut to the original number
    of months; every episode in a drawn month is included (with repetition).
    The resampled mean is total diff / total episodes over the drawn months.
    """
    diff = np.asarray(diff, float)
    sums, counts = _month_totals(diff, months)
    m = len(sums)
    block = max(1, min(block, m))
    n_blocks = math.ceil(m / block)
    rng = np.random.default_rng(seed)
    starts = rng.integers(0, m, size=(n_boot, n_blocks))
    idx = (starts[:, :, None] + np.arange(block)).reshape(n_boot, -1)[:, :m] % m
    means = sums[idx].sum(1) / counts[idx].sum(1)
    lo, hi = np.quantile(means, [alpha / 2, 1 - alpha / 2])
    return {
        "mean": float(diff.mean()),
        "lo": float(lo),
        "hi": float(hi),
        "p_le0": float((means <= 0).mean()),
        "n": int(len(diff)),
        "n_months": int(m),
        "block": int(block),
        "n_boot": int(n_boot),
    }


def by_period(diff, dates, edges):
    """n, mean and sum of diff per period; edges = [(label, lo, hi_exclusive)]."""
    diff = np.asarray(diff, float)
    dates = np.asarray(dates)
    rows = []
    for label, lo, hi in edges:
        d = diff[(dates >= lo) & (dates < hi)]
        rows.append({"period": label, "n": len(d),
                     "mean": d.mean() if len(d) else np.nan, "sum": d.sum()})
    return pd.DataFrame(rows).set_index("period")


def share_positive_years(diff, dates):
    """Fraction of calendar years with positive mean diff, and per-year means."""
    years = [d.year for d in dates]
    per_year = pd.Series(np.asarray(diff, float)).groupby(years).mean()
    per_year.index.name = "year"
    return float((per_year > 0).mean()), per_year


def cvar(pnl, q=0.05):
    """Mean of the worst q share of episodes, as a positive loss."""
    pnl = np.sort(np.asarray(pnl, float))
    k = max(1, math.ceil(q * len(pnl)))
    return float(-pnl[:k].mean())


def summary(pnl_a, pnl_b, dates, **kw):
    """Flat dict comparing policy B against A, plus per-year mean of B - A.

    kw is passed to block_bootstrap (n_boot, block, seed, alpha).
    """
    a, b = np.asarray(pnl_a, float), np.asarray(pnl_b, float)
    diff = b - a
    months = [f"{d.year}-{d.month:02d}" for d in dates]
    boot = block_bootstrap(diff, months, **kw)
    share, per_year = share_positive_years(diff, dates)
    out = {
        "mean_a": float(a.mean()), "mean_b": float(b.mean()),
        "cvar95_a": cvar(a), "cvar95_b": cvar(b),
        "share_pos_years": share,
    }
    out.update({f"diff_{k}" if k in ("mean", "lo", "hi") else k: v for k, v in boot.items()})
    out["proved"] = bool(boot["lo"] > 0)
    return out, per_year
