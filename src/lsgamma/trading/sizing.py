import math

from lsgamma.backtest import sim
from lsgamma.core.Algos.broker import MULTIPLIER
from lsgamma.history import marks
from lsgamma.trading import selection


def flag(cfg, key):
    # research setting; bare paper.toml has none
    return cfg.get("backtest", {}).get(key, 0.0)


def put_strike(t, chain, target):
    # put strike by delta target
    if not target or t["right"] != "P":
        return t["strike"]
    rows = chain[(chain["expiry"] == selection.to_date(t["expiry"])) & (chain["right"] == "P")]
    rows = rows.dropna(subset=["mid", "delta"])
    return float(rows.loc[(rows["delta"].abs() - target).abs().idxmin(), "strike"])


def band(cfg, gamma):
    # Whalley-Wilmott band on book gamma
    k, floor = flag(cfg, "ww_band"), cfg["hedge"]["min_shares"]
    return max(floor, k * math.sqrt(gamma)) if k and not math.isnan(gamma) else floor


def shock_vol(bt, iv):
    # stress IV floor or IV multiple
    return max(bt["stress_vol"], max(bt.get("stress_vol_mult", 0.0), 1.0) * iv)


def stress_qty(cfg, r, spot, years, budget, hedged=True):
    # most puts within the stress budget
    bt = cfg["backtest"]
    drop, vol = bt["stress_drop"], shock_vol(bt, float(r["iv"]))
    crash = float(marks.price(spot * (1 - drop), r["strike"], years, 0.0, vol, False))
    delta, gamma = abs(float(r["delta"])) * MULTIPLIER, abs(float(r["gamma"])) * MULTIPLIER
    net = (crash - float(r["mid"])) * MULTIPLIER - delta * drop * spot
    n = int(budget // net) if net > 0 else 0
    def gap(n):
        return min(band(cfg, n * gamma), n * delta) if hedged else n * delta
    while n and n * net + gap(n) * drop * spot > budget:
        n -= 1
    return n


def contracts(cfg, signal, t, chain, asof, scale=1.0, hedged=True):
    # short puts sized to the stress budget
    budget = flag(cfg, "stress_budget") * cfg["size"]["capital"] * scale
    if not budget or signal != "short":
        return cfg["size"]["quantity"]
    r = sim.row(chain, t["expiry"], t["strike"], t["right"])
    years = float(marks.years(asof, [t["expiry"]])[0])
    return 0 if r is None else stress_qty(cfg, r, sim.und_price(chain), years, budget, hedged)
