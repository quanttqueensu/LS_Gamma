import json
import math
from datetime import date

import pandas as pd

from lsgamma import experiments
from lsgamma.trading import config, ledger, pnl, selection

OUT = experiments.REPO / "research" / "desk.json"
SIGNAL_COLS = ["date", "expiry", "dte", "rv_forecast", "iv", "vrp", "signal"]
BOOK, BOOK_COLS = "book", ["date", "realized", "open", "total"]
TRADE_COLS = ["date", "action", "side", "right", "strike", "expiry", "qty", "price", "reason", "pnl"]


def clean(value):
    if hasattr(value, "item"):
        value = value.item()
    if isinstance(value, float) and not math.isfinite(value):
        return None  # JSON has no NaN or inf
    return round(value, 4) if isinstance(value, float) else value


def rows(df, cols):
    keep = [c for c in cols if c in df.columns]
    return [{c: clean(r[c]) for c in keep} for _, r in df[keep].iterrows()]


def rules(cfg):
    s, e, x, bt = cfg["signal"], cfg["entry"], cfg["exit"], cfg.get("backtest", {})
    out = {"forecaster": s["forecaster"], "short_band": s["short_band"], "long_band": s["long_band"],
           "target_dte": e["target_dte"], "exit_dte": x["exit_dte"], "short_stop_mult": x["short_stop_mult"],
           "long_stop_frac": x["long_stop_frac"], "short_profit_frac": x["short_profit_frac"],
           "min_shares": cfg["hedge"]["min_shares"], "quantity": cfg["size"]["quantity"],
           "put_delta": bt.get("put_delta", 0.0), "stress_budget": bt.get("stress_budget", 0.0)}
    return {k: clean(v) for k, v in out.items()}  # always-short bands are inf


def position(pos, chain, cfg):
    if not pos:
        return None
    x = cfg["exit"]
    mark = selection.mark(chain, pos["expiry"], pos["strike"], pos["right"]) if chain is not None else math.nan
    spot = float(chain["und_price"].median()) if chain is not None else math.nan
    prem = pnl.premium(pos)
    frac = x["short_stop_mult"] if pos["side"] == "short" else x["long_stop_frac"]
    out = {k: pos[k] for k in ("side", "right", "strike", "expiry", "qty", "entry_price", "entry_date")}
    out.update({
        "hedge_shares": sum(h["shares"] for h in pos["hedges"]),
        "dte": (date.fromisoformat(pos["expiry"]) - date.today()).days,
        "mark_ts": chain["asof"].max().isoformat(timespec="seconds") if chain is not None and "asof" in chain else None,
        "spot": clean(spot), "premium": clean(prem), "stop": clean(-frac * prem),
        "take": clean(x["short_profit_frac"] * prem) if pos["side"] == "short" else None,
        "option_pnl": clean(pnl.option_pnl(pos, mark)), "hedge_pnl": clean(pnl.hedge_pnl(pos, spot)),
        "pnl": clean(pnl.combined_pnl(pos, mark, spot)),
    })
    return out


def realized_by(trade_rows, day):
    return sum(t.get("pnl") or 0 for t in trade_rows if t.get("action") == "close" and t["date"] <= day)


def holding(trade_rows, day):
    # trades are logged in order; the last one up to `day` decides
    held = False
    for t in trade_rows:
        if t["date"] <= day:
            held = t.get("action") == "open"
    return held


def history(signal_rows, trade_rows, stored, today):
    # recorded daily marks; flat days before them count as realized only
    points = {r["date"]: r for r in stored}
    for s in signal_rows:
        d = s["date"]
        if d not in points and not holding(trade_rows, d):
            r = clean(realized_by(trade_rows, d))
            points[d] = {"date": d, "realized": r, "open": 0.0, "total": r}
    if today:
        points[today["date"]] = today
    return [points[d] for d in sorted(points)]


def snapshot(chain, cfg):
    signals, trades = ledger.read_log("signals"), ledger.read_log("trades")
    trade_rows = rows(trades, TRADE_COLS) if not trades.empty else []
    signal_rows = rows(signals, SIGNAL_COLS) if not signals.empty else []
    stamps = [s for df in (signals, trades, ledger.read_log("hedges")) if "ts" in df for s in df["ts"] if isinstance(s, str)]
    pos = position(ledger.load_position(), chain, cfg)
    if pos and pos["mark_ts"]:
        stamps.append(pos["mark_ts"])
    realized = clean(sum(t.get("pnl") or 0 for t in trade_rows if t.get("action") == "close"))
    day = str(chain["asof"].max().date()) if chain is not None and "asof" in chain else str(date.today())
    open_pnl = pos["pnl"] if pos else 0.0
    today = None if open_pnl is None else {"date": day, "realized": realized, "open": open_pnl,
                                           "total": clean(realized + open_pnl)}
    stored = rows(ledger.read_log(BOOK), BOOK_COLS) if not ledger.read_log(BOOK).empty else []
    snap = {"asof": max(stamps) if stamps else None, "rules": rules(cfg), "signals": signal_rows,
            "position": pos, "trades": trade_rows, "realized": realized,
            "book": history(signal_rows, trade_rows, stored, today)}
    return snap, today


def build(chain, cfg):
    return snapshot(chain, cfg)[0]


def record(today):
    # one book row per day, latest run wins
    book = ledger.read_log(BOOK)
    if not book.empty:
        book = book[book["date"] != today["date"]]
    ledger.ROOT.mkdir(parents=True, exist_ok=True)
    pd.concat([book, pd.DataFrame([today])], ignore_index=True).to_parquet(ledger.ROOT / f"{BOOK}.parquet")


def write(chain, cfg, path=None):
    path = path or OUT
    snap, today = snapshot(chain, cfg)
    if today:
        record(today)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(snap, indent=1, allow_nan=False, default=str) + "\n")
    return path


if __name__ == "__main__":
    from lsgamma.pipeline import store
    print(f"desk -> {write(store.load('chain'), config.load())}")
