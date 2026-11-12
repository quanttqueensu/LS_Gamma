import json
import math
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

from lsgamma import experiments
from lsgamma.backtest import sim
from lsgamma.core.Algos.broker import MULTIPLIER
from lsgamma.history import marks
from lsgamma.pipeline import store
from lsgamma.trading import exits, pnl, runner, selection

DATA = Path(__file__).resolve().parents[3] / "data" / "backtest"
OUTPUTS = ["signals", "trades", "hedges", "equity", "events"]
LIVE_SRC = "live_quote"
TREND_DAYS = 10  # efficiency-ratio lookback, trading days


def day(s):
    return s if isinstance(s, date) else date.fromisoformat(str(s))


def check_window(cfg, start, end, holdout):
    last, hold = day(cfg["history"]["last_day"]), day(cfg["backtest"]["holdout_start"])
    if start < day(cfg["backtest"]["first_day"]):
        raise SystemExit(f"start {start} is before the first day of data "
                         f"({cfg['backtest']['first_day']}); refused")
    if end > last:
        raise SystemExit(f"end {end} is after the last day of data ({last}); refused")
    if end >= hold and not holdout:
        raise SystemExit(f"end {end} reaches the hold-out (from {hold}); "
                         "pass --holdout only for the final run")
    if start > end:
        raise SystemExit(f"start {start} is after end {end}")


def times(cfg):
    s = cfg["schedule"]
    every = sorted(set(s["signal"]) | set(s["hedge"]))
    off = [t for t in every if t not in cfg["history"]["grid"]]
    if off:
        raise SystemExit(f"schedule times {off} are not on the [history] grid")
    return [(t, t in s["signal"]) for t in every]


def at(d, hhmm):
    return pd.Timestamp(f"{d} {hhmm}", tz=store.TZ)


def window(feats, asof, years):
    # live fits on yfinance period=5y
    return feats[feats.index >= pd.Timestamp(asof.date()) - pd.DateOffset(years=years)]


def cached(cache, years):
    def rv_for(feats, cfg, asof, dte):
        key = (asof.date(), dte)
        if key not in cache:
            cache[key] = runner.forecast(window(feats, asof, years), cfg, asof, dte)
        return cache[key]
    return rv_for


def read(folder, name):
    path = folder / f"{name}.parquet"
    return pd.read_parquet(path) if path.exists() else None


def state(cfg, feats, root, holdout, cache):
    hold = pd.Timestamp(cfg["backtest"]["holdout_start"])
    sched = times(cfg)
    return {"cfg": cfg, "feats": feats, "root": root, "holdout": holdout, "times": sched,
            "rv_for": cached(cache, cfg["backtest"]["fit_years"]), "book": sim.book(),
            "picks": picks(cfg),
            "no_entry": hold.date() - timedelta(days=cfg["entry"]["max_dte"]),
            "last_dev": feats.index[feats.index < hold].max().date(),
            "keep": (cfg["exit"]["flat_days"] + 1) * sum(sig for _, sig in sched),
            "last_spot": (math.nan, ""), "last_stop": None, "reset": True, "live": None,
            **{k: [] for k in OUTPUTS}}


def log(s, asof, event, detail=""):
    s["events"].append({"date": str(asof.date()), "ts": runner.stamp(asof),
                        "event": event, "detail": detail})


def embargo_close(s, asof):
    return (not s["holdout"] and asof.date() == s["last_dev"]
            and f"{asof:%H:%M}" == s["times"][-1][0])


def embargoed(s, asof):
    return not s["holdout"] and asof.date() >= s["no_entry"]


def held_mark(s, pos, chain, asof, note=False):
    m = selection.mark(chain, pos["expiry"], pos["strike"], pos["right"])
    if not math.isnan(m):
        pos["mark"] = m
        return m
    if note:
        log(s, asof, "no_mark", f"{pos['right']} {pos['strike']} {pos['expiry']}")
    return sim.conservative(pos, pos["mark"], runner.spot(chain))


def exit_for(s, pos, chain, asof, d, hist):
    if date.fromisoformat(pos["expiry"]) < asof.date():
        return "expired"
    total = pnl.combined_pnl(pos, held_mark(s, pos, chain, asof, note=True), runner.spot(chain))
    signal, hist = (d["signal"], hist) if d else (None, [])
    if pos.get("crash"):
        reason = crash_exit(s, pos, asof)
    else:
        reason = exits.exit_reason(pos, asof.date(), total, signal, hist, s["cfg"])
    return reason or ("embargo" if embargo_close(s, asof) else None)


def crash_exit(s, pos, asof):
    # research only: crash calls exit on holding days
    held = pd.bdate_range(pos["entry_date"], asof.date()).size - 1
    return "crash_time" if held >= s["cfg"]["backtest"]["crash_days"] else None


def view(s, folder, chain):
    # live books fill at the quoted bid/ask
    return read(folder, "fill") if s["live"] is None else chain.assign(src=LIVE_SRC)


def snaps(s, d):
    # (asof, folder) on day d, latest first
    if s["live"] is not None:
        return [s["live"][d]] if d in s["live"] else []
    grid = reversed(s["cfg"]["history"]["grid"])
    return [(at(d, h), store.folder(at(d, h), s["root"])) for h in grid]


def expiry_spot(s, expiry):
    # last snapshot on expiry day, fill view first
    for asof, folder in snaps(s, expiry):
        chain = read(folder, "chain")
        if chain is None:
            continue
        spot = sim.und_price(view(s, folder, chain))
        if not math.isnan(spot):
            return spot, f"fill {runner.stamp(asof)}"
        return runner.spot(chain), f"decide {runner.stamp(asof)}"
    return s["last_spot"]


def close(s, pos, reason, chain, fill, asof):
    b, bt = s["book"], s["cfg"]["backtest"]
    if reason == "expired":
        spot, ts = expiry_spot(s, date.fromisoformat(pos["expiry"]))
        price, cost, src = sim.intrinsic(pos, spot), 0.0, "expiry"
        log(s, asof, "expired", f"settled {price:.2f} at spot {spot:.2f} from {ts}")
    else:
        spot = runner.spot(chain)
        price, src = sim.option_fill(fill, pos["side"], pos["expiry"], pos["strike"],
                                     pos["right"], "close", bt["spread_mult"])
        cost = sim.fee(bt["commission_contract"], pos["qty"], bt["min_per_order"])
    if math.isnan(price):
        return log(s, asof, "no_fill", f"close {reason}")
    total = pnl.combined_pnl(pos, price, spot)
    cost = sim.close_option(b, pos, price, cost)
    if reason == "stop":
        s["last_stop"], s["reset"] = (pos["side"], str(asof.date())), False
    s["trades"].append({"date": str(asof.date()), "ts": runner.stamp(asof), "action": "close",
                        "side": pos["side"], "right": pos["right"], "strike": pos["strike"],
                        "expiry": pos["expiry"], "qty": pos["qty"], "price": price,
                        "reason": reason, "pnl": total, "commission": cost,
                        "pnl_net": total - pos["fees"], "src": src,
                        "entry_ts": pos["entry_ts"]})


def picks(cfg):
    # research only: ranker's daily put deltas
    name = cfg["backtest"].get("put_picks", "")
    if not name:
        return None
    df = pd.read_parquet(experiments.ROOT / name)
    return dict(zip(df["date"].astype(str), df["delta"].astype(float)))


def put_target(s, asof):
    # research only: day's pick, else put_delta
    p, d = s["picks"], str(asof.date())
    return p[d] if p is not None and d in p else s["cfg"]["backtest"].get("put_delta", 0.0)


def pick_skip(s, side, asof):
    # research only: pick 0 means no short
    return side == "short" and s["picks"] is not None and s["picks"].get(str(asof.date())) == 0.0


def put_strike(t, chain, target):
    # research only: put strike by delta target
    if not target or t["right"] != "P":
        return t["strike"]
    rows = chain[(chain["expiry"] == selection.to_date(t["expiry"])) & (chain["right"] == "P")]
    rows = rows.dropna(subset=["mid", "delta"])
    return float(rows.loc[(rows["delta"].abs() - target).abs().idxmin(), "strike"])


def band(cfg, gamma):
    # research only: Whalley-Wilmott band on book gamma
    k, floor = cfg["backtest"].get("ww_band", 0.0), cfg["hedge"]["min_shares"]
    return max(floor, k * math.sqrt(gamma)) if k and not math.isnan(gamma) else floor


def trending(s, asof):
    # research only: 10-day trend efficiency of SPY
    bt = s["cfg"]["backtest"]
    if not bt.get("trend_er", 0.0):
        return True
    px = (1 + runner.completed(s["feats"], asof)["ret"].tail(TREND_DAYS)).cumprod()
    if len(px) < 2:
        return False
    path = px.diff().abs().sum() + abs(px.iloc[0] - 1)
    return path > 0 and abs(px.iloc[-1] - 1) / path >= bt["trend_er"]


def long_band(s, asof):
    # research only: wider band for long gamma
    k, held = s["cfg"]["backtest"].get("long_hedge_band", 0), s["book"]["open"]
    if not k or not held or any(p["side"] != "long" for p in held):
        return 0
    return k if trending(s, asof) else 0


def book_gamma(b, chain):
    rows = [(sim.row(chain, p["expiry"], p["strike"], p["right"]), p) for p in b["open"]]
    return sum((abs(float(r["gamma"])) * p["qty"] * MULTIPLIER if r is not None else math.nan
                for r, p in rows), 0.0)


def shock_vol(bt, iv):
    # research only: stress IV floor or IV multiple
    return max(bt["stress_vol"], max(bt.get("stress_vol_mult", 0.0), 1.0) * iv)


def stress_qty(cfg, r, spot, years, budget, hedged=True):
    # research only: most puts within the stress budget
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


def tilt(s, asof):
    # research only: budget scale from 1y percentile
    bt = s["cfg"]["backtest"]
    col, k = bt.get("size_by", ""), bt.get("size_tilt", 0.0)
    if not col or not k:
        return 1.0
    x = runner.completed(s["feats"], asof)[col].dropna().iloc[-252:]
    t = 1.0 if x.empty else 1.0 + k * (2 * float(x.rank(pct=True).iloc[-1]) - 1)
    cap = bt.get("size_cap", 0.0)
    return min(t, cap) if cap else t


def unhedge(s, vrp):
    # research only: no hedge above this VRP
    cut = s["cfg"]["backtest"].get("vrp_unhedge", 0.0)
    return bool(cut) and not math.isnan(vrp) and vrp > cut


def hedge_ratio(s, vrp):
    # research only: partial hedge above this VRP
    bt = s["cfg"]["backtest"]
    cut = bt.get("vrp_hedge_cut", 0.0)
    if cut and not math.isnan(vrp) and vrp > cut:
        return bt.get("vrp_hedge_ratio", 0.0)
    return None


def beta(s, asof):
    # research only: VIX points per unit return, 1y
    cache = s.setdefault("beta", {})
    if asof.date() not in cache:
        f = runner.completed(s["feats"], asof)[["ret", "vix"]].iloc[-253:]
        f = f.assign(dv=f["vix"].diff()).dropna()
        cache[asof.date()] = float(f["ret"].cov(f["dv"]) / f["ret"].var()) if len(f) > 20 else 0.0
    return cache[asof.date()]


def mv_shares(s, p, chain, asof):
    # research only: Hull-White vega term, spot-vol beta
    k = s["cfg"]["backtest"].get("mv_hedge", 0.0)
    if not k:
        return 0.0
    r = sim.row(chain, p["expiry"], p["strike"], p["right"])
    vega = math.nan if r is None else float(r["vega"])
    return -k * vega * beta(s, asof) / runner.spot(chain) * p["qty"] * MULTIPLIER * pnl.SIGN[p["side"]]


def target(s, p, chain, asof):
    if p.get("unhedged"):
        return 0.0
    return p.get("hedge_ratio", 1.0) * (sim.target_shares(p, chain) + mv_shares(s, p, chain, asof))


def crash_cfg(cfg):
    lo, mid, hi = cfg["backtest"]["crash_dte"]
    return {**cfg, "entry": {**cfg["entry"], "min_dte": lo, "target_dte": mid, "max_dte": hi}}


def crash_qty(s, price):
    # research only: calls bought with a premium budget
    cfg = s["cfg"]
    return int(cfg["backtest"]["crash_premium"] * cfg["size"]["capital"] // (price * MULTIPLIER))


def crash_due(s, asof):
    # research only: long call when VIX/VIX3M >= gate
    gate = s["cfg"]["backtest"].get("crash_gate", 0.0)
    if not gate or any(p.get("crash") for p in s["book"]["open"]) or embargoed(s, asof):
        return False
    return float(runner.completed(s["feats"], asof)["vix_vix3m"].iloc[-1]) >= gate


def size(s, signal, t, chain, asof, hedged=True):
    # research only: short puts sized to stress budget
    cfg = s["cfg"]
    budget = cfg["backtest"].get("stress_budget", 0.0) * cfg["size"]["capital"] * tilt(s, asof)
    if not budget or signal != "short":
        return cfg["size"]["quantity"]
    r = sim.row(chain, t["expiry"], t["strike"], t["right"])
    years = float(marks.years(asof, [t["expiry"]])[0])
    return 0 if r is None else stress_qty(cfg, r, runner.spot(chain), years, budget, hedged)


def enter(s, signal, chain, fill, asof, vrp=math.nan, crash=False):
    cfg, bt = s["cfg"], s["cfg"]["backtest"]
    try:
        t = selection.trade_for(signal, chain, crash_cfg(cfg) if crash else cfg)
    except ValueError as e:
        return log(s, asof, "no_entry", str(e))
    t = {**t, "strike": put_strike(t, chain, put_target(s, asof))}
    price, src = sim.option_fill(fill, signal, t["expiry"], t["strike"], t["right"], "open",
                                 bt["spread_mult"])
    if math.isnan(price):
        return log(s, asof, "no_fill", f"open {signal}")
    bare, ratio = unhedge(s, vrp), hedge_ratio(s, vrp)
    qty = crash_qty(s, price) if crash else size(s, signal, t, chain, asof, not bare)
    if not qty:
        return log(s, asof, "no_entry", "crash premium below one contract" if crash
                   else "stress budget below one contract")
    pos = {"side": signal, "right": t["right"], "expiry": str(t["expiry"]),
           "strike": t["strike"], "qty": qty, "entry_price": price,
           "entry_date": str(asof.date()), "entry_ts": runner.stamp(asof),
           **({"unhedged": True} if bare else {}),
           **({"hedge_ratio": ratio} if ratio is not None else {}),
           **({"crash": True} if crash else {}),
           "hedges": carry(s["book"], chain, asof)}
    cost = sim.open_option(s["book"], pos, sim.fee(bt["commission_contract"], qty,
                                                   bt["min_per_order"]))
    s["trades"].append({**{k: v for k, v in pos.items() if k not in ("hedges", "mark", "fees")},
                        "date": str(asof.date()), "ts": runner.stamp(asof), "action": "open",
                        "price": price, "commission": cost, "src": src})


def carry(b, chain, asof):
    # orphan shares join the new position
    left = sim.unallocated(b)
    if not left:
        return []
    return [{"date": str(asof.date()), "ts": runner.stamp(asof), "shares": left,
             "price": runner.spot(chain)}]


def attach(b, targets, chain, asof):
    # orphan shares split over open positions
    rows = carry(b, chain, asof)
    if rows and b["open"]:
        for p, part in zip(b["open"], sim.split(rows[0]["shares"], targets)):
            p["hedges"].append({**rows[0], "shares": part})


def hedge(s, chain, fill, asof):
    b, bt = s["book"], s["cfg"]["backtest"]
    targets = [target(s, p, chain, asof) for p in b["open"]]
    if any(math.isnan(t) for t in targets):
        return log(s, asof, "no_delta", "hedge skipped")
    attach(b, targets, chain, asof)
    gaps = [t - sim.held(p) for t, p in zip(targets, b["open"])]
    shares = round(sum(targets, 0.0) - b["shares"])
    if abs(shares) < band(s["cfg"], book_gamma(b, chain)):
        return
    if abs(shares) < long_band(s, asof):
        return log(s, asof, "trend_hold", f"hedge {shares} held")
    price = sim.share_price(fill, shares, bt["share_half_spread"] * bt["spread_mult"])
    if math.isnan(price):
        return log(s, asof, "no_fill", f"hedge {shares}")
    row = {"date": str(asof.date()), "ts": runner.stamp(asof), "shares": shares, "price": price}
    cost = sim.trade_shares(b, shares, price, sim.fee(bt["commission_share"], abs(shares),
                                                      bt["min_per_order"]))
    s["hedges"].append({**row, "commission": cost})
    parts = sim.allot(gaps, shares) if gaps else []
    for p, part in zip(b["open"], parts):
        p["hedges"].append({**row, "shares": part})
        p["fees"] += cost if len(parts) == 1 else cost * abs(part) / sum(map(abs, parts))


def mark(s, chain, asof):
    b = s["book"]
    marks = [held_mark(s, p, chain, asof) for p in b["open"]]
    spot = runner.spot(chain)
    s["last_spot"] = (spot, runner.stamp(asof))
    s["equity"].append({"date": str(asof.date()), "ts": runner.stamp(asof),
                        **sim.equity(b, marks, spot)})


def decide(s, folder, chain, asof):
    d = runner.decide(s["feats"], chain, read(folder, "atm_iv"), s["cfg"], asof, s["rv_for"])
    s["signals"].append(d)
    log_ = pd.DataFrame(s["signals"][-s["keep"]:])
    return d, runner.recent(log_, asof.date(), d["signal"], s["cfg"]["exit"]["flat_days"])


def step(s, asof, signal_time, folder=None):
    folder = folder or store.folder(asof, s["root"])
    chain = read(folder, "chain")
    if chain is None:
        return log(s, asof, "skipped", "no snapshot")
    try:
        runner.check(chain)
        d, hist = decide(s, folder, chain, asof) if signal_time else (None, [])
    except (runner.BadSnapshot, ValueError, IndexError) as e:
        return log(s, asof, "skipped", str(e))
    act(s, chain, view(s, folder, chain), asof, d, hist)


def note_reset(s, d):
    if d and s["last_stop"] and d["signal"] != s["last_stop"][0]:
        s["reset"] = True


def waiting(s, side):
    # research only: wait for signal to leave side
    stop = s["last_stop"]
    return (s["cfg"]["backtest"].get("stop_reset", False) and stop is not None
            and stop[0] == side and not s["reset"])


def room(s, side):
    # research only: ladder same-side positions
    held = [p for p in s["book"]["open"] if not p.get("crash")]
    return (len(held) < s["cfg"]["backtest"].get("max_positions", 1)
            and all(p["side"] == side for p in held))


def gated(s, side, asof):
    # research only: skip shorts on inverted VIX curve
    gate = s["cfg"]["backtest"].get("short_gate", 0.0)
    if side != "short" or gate <= 0:
        return None
    ratio = float(runner.completed(s["feats"], asof)["vix_vix3m"].iloc[-1])
    return ratio if ratio >= gate else None


def off_day(s, asof):
    # research only: entries on these weekdays only
    days = s["cfg"]["backtest"].get("entry_weekdays", [])
    return bool(days) and asof.weekday() not in days


def act(s, chain, fill, asof, d, hist):
    # decisions read chain; fill only prices them
    if fill is None:
        log(s, asof, "no_fill_view", "")
    for pos in list(s["book"]["open"]):
        reason = exit_for(s, pos, chain, asof, d, hist)
        if reason:
            close(s, pos, reason, chain, fill, asof)
    note_reset(s, d)
    if d and room(s, d["signal"]) and d["signal"] != "flat" and not embargoed(s, asof):
        if exits.cooling(d["signal"], s["last_stop"], asof.date(),
                         s["cfg"]["exit"]["stop_cooloff_days"]):
            log(s, asof, "cooloff", f"no {d['signal']} entry after stop")
        elif waiting(s, d["signal"]):
            log(s, asof, "reset_wait", f"no {d['signal']} entry until signal resets")
        elif (ratio := gated(s, d["signal"], asof)) is not None:
            log(s, asof, "gate", f"no short entry, VIX/VIX3M {ratio:.3f}")
        elif off_day(s, asof):
            log(s, asof, "weekday", f"no {d['signal']} entry on {asof:%A}")
        elif pick_skip(s, d["signal"], asof):
            log(s, asof, "pick_skip", "ranker picked no trade")
        else:
            enter(s, d["signal"], chain, fill, asof, d["vrp"])
    if d and crash_due(s, asof):
        enter(s, "long", chain, fill, asof, crash=True)
    hedge(s, chain, fill, asof)
    mark(s, chain, asof)


def trading_days(feats, start, end):
    idx = feats.index[(feats.index >= pd.Timestamp(start)) & (feats.index <= pd.Timestamp(end))]
    return [d.date() for d in idx]


def snapshots(cfg, root=None):
    return root or DATA / cfg["history"]["version"]


def manifest(root):
    path = root / "manifest.json"
    if not path.exists():
        return {"config_hash": None, "features_end": None}
    m = json.loads(path.read_text())
    builds = m.get("builds") or [{}]
    return {"config_hash": m.get("config_hash"), "features_end": builds[-1].get("features_end")}


def backtest(cfg, start, end, holdout=False, root=None, cache=None):
    start, end = day(start), day(end)
    check_window(cfg, start, end, holdout)
    root = snapshots(cfg, root)
    if not (root / "features.parquet").exists():
        raise SystemExit(f"no snapshots in {root}; run python -m lsgamma.history.build")
    feats = pd.read_parquet(root / "features.parquet")
    s = state(cfg, feats, root, holdout, {} if cache is None else cache)
    run_days = trading_days(feats, start, end)
    for d in run_days:
        for hhmm, signal_time in s["times"]:
            step(s, at(d, hhmm), signal_time)
    span = {"first_day": str(run_days[0]) if run_days else None,
            "last_day": str(run_days[-1]) if run_days else None, "days": len(run_days)}
    return {**{k: pd.DataFrame(s[k]) for k in OUTPUTS}, "span": pd.DataFrame([span])}


def live(cfg, plan, cache=None):
    # shadow books: live snapshots, no embargo
    runner.check_schedule(cfg)
    s = state(cfg, read(plan[0][1], "features"), None, True, {} if cache is None else cache)
    s["live"] = {asof.date(): (asof, folder) for asof, folder in plan}
    for asof, folder in plan:
        s["feats"] = read(folder, "features")
        step(s, asof, True, folder)
    return {**{k: pd.DataFrame(s[k]) for k in OUTPUTS}, "open": s["book"]["open"]}
