import json
import math
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

from lsgamma.backtest import sim
from lsgamma.pipeline import store
from lsgamma.trading import exits, pnl, runner, selection

DATA = Path(__file__).resolve().parents[3] / "data" / "backtest"
OUTPUTS = ["signals", "trades", "hedges", "equity", "events"]


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
            "no_entry": hold.date() - timedelta(days=cfg["entry"]["max_dte"]),
            "last_dev": feats.index[feats.index < hold].max().date(),
            "keep": (cfg["exit"]["flat_days"] + 1) * sum(sig for _, sig in sched),
            "last_spot": (math.nan, ""), "last_stop": None, "reset": True,
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
    reason = exits.exit_reason(pos, asof.date(), total, signal, hist, s["cfg"])
    return reason or ("embargo" if embargo_close(s, asof) else None)


def expiry_spot(s, expiry):
    # last grid snapshot on expiry day, fill view first
    for hhmm in reversed(s["cfg"]["history"]["grid"]):
        asof = at(expiry, hhmm)
        folder = store.folder(asof, s["root"])
        chain = read(folder, "chain")
        if chain is None:
            continue
        spot = sim.und_price(read(folder, "fill"))
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


def put_strike(s, t, chain):
    # research only: put strike by delta target
    target = s["cfg"]["backtest"].get("put_delta", 0.0)
    if not target or t["right"] != "P":
        return t["strike"]
    rows = chain[(chain["expiry"] == selection.to_date(t["expiry"])) & (chain["right"] == "P")]
    rows = rows.dropna(subset=["mid", "delta"])
    return float(rows.loc[(rows["delta"].abs() - target).abs().idxmin(), "strike"])


def enter(s, signal, chain, fill, asof):
    cfg, bt = s["cfg"], s["cfg"]["backtest"]
    try:
        t = selection.trade_for(signal, chain, cfg)
    except ValueError as e:
        return log(s, asof, "no_entry", str(e))
    t = {**t, "strike": put_strike(s, t, chain)}
    price, src = sim.option_fill(fill, signal, t["expiry"], t["strike"], t["right"], "open",
                                 bt["spread_mult"])
    if math.isnan(price):
        return log(s, asof, "no_fill", f"open {signal}")
    qty = cfg["size"]["quantity"]
    pos = {"side": signal, "right": t["right"], "expiry": str(t["expiry"]),
           "strike": t["strike"], "qty": qty, "entry_price": price,
           "entry_date": str(asof.date()), "entry_ts": runner.stamp(asof),
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
    targets = [sim.target_shares(p, chain) for p in b["open"]]
    if any(math.isnan(t) for t in targets):
        return log(s, asof, "no_delta", "hedge skipped")
    attach(b, targets, chain, asof)
    gaps = [t - sim.held(p) for t, p in zip(targets, b["open"])]
    shares = round(sum(targets, 0.0) - b["shares"])
    if abs(shares) < s["cfg"]["hedge"]["min_shares"]:
        return
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


def step(s, asof, signal_time):
    folder = store.folder(asof, s["root"])
    chain = read(folder, "chain")
    if chain is None:
        return log(s, asof, "skipped", "no snapshot")
    try:
        runner.check(chain)
        d, hist = decide(s, folder, chain, asof) if signal_time else (None, [])
    except (runner.BadSnapshot, ValueError, IndexError) as e:
        return log(s, asof, "skipped", str(e))
    act(s, chain, read(folder, "fill"), asof, d, hist)


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
    held = s["book"]["open"]
    return (len(held) < s["cfg"]["backtest"].get("max_positions", 1)
            and all(p["side"] == side for p in held))


def gated(s, side, asof):
    # research only: skip shorts on inverted VIX curve
    gate = s["cfg"]["backtest"].get("short_gate", 0.0)
    if side != "short" or gate <= 0:
        return None
    ratio = float(runner.completed(s["feats"], asof)["vix_vix3m"].iloc[-1])
    return ratio if ratio >= gate else None


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
        else:
            enter(s, d["signal"], chain, fill, asof)
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
