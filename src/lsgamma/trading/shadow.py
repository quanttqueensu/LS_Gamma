import json

import pandas as pd

from lsgamma import experiments
from lsgamma.backtest import config, engine, metrics
from lsgamma.hub import desk
from lsgamma.pipeline import store
from lsgamma.trading import ledger, runner

PATH = config.CONFIGS / "shadow.toml"
OUT = experiments.REPO / "research" / "shadow.json"
LIVE = store.ROOT
NEED = ["chain", "atm_iv", "features"]


def logged():
    # last live run per day
    s = ledger.read_log("signals")
    if s.empty or "ts" not in s:
        return {}
    s = s.dropna(subset=["ts"])
    return {d: pd.Timestamp(t) for d, t in zip(s["date"], s["ts"])}


def key(root, folder):
    return folder.relative_to(root).as_posix()


def quoted(chain):
    # snapshot quote time, ET
    t = pd.Timestamp(chain["asof"].max())
    return t.tz_localize(store.TZ) if t.tzinfo is None else t.tz_convert(store.TZ)


def folders(root, day):
    # date-only folder sorts before HHMM runs
    base = root / day
    found = [base, *sorted(p for p in base.iterdir() if p.is_dir())]
    return [f for f in found if all((f / f"{n}.parquet").exists() for n in NEED)]


def usable(folder, cfg):
    chain = engine.read(folder, "chain")
    try:
        runner.check(chain)
        runner.decide(None, chain, engine.read(folder, "atm_iv"), cfg, quoted(chain), lambda *a: 0.0)
        return True
    except (runner.BadSnapshot, ValueError, IndexError):
        return False


def pick(root, day, ts, cfg):
    # the folder the live run used, else first usable
    found = folders(root, day)
    if ts is not None:
        before = [f for f in found if key(root, f) <= store.key(ts)]
        if before:
            return before[-1]
    good = [f for f in found if usable(f, cfg)]
    return (good or found or [None])[0]


def plan(root, start, cfg):
    if not root.exists():
        return []
    runs, out = logged(), []
    for day in sorted(p.name for p in root.iterdir() if p.is_dir() and p.name >= start):
        folder = pick(root, day, runs.get(day), cfg)
        if folder is not None:
            out.append((quoted(engine.read(folder, "chain")), folder))
    return out


def book_cfg(b, capital):
    cfg = config.variant(b["exp"], b["variant"]) if b.get("exp") else config.load()
    return config.merge(cfg, {"size": {"capital": capital}})


def rules(cfg):
    bt = cfg["backtest"]
    out = {**desk.rules(cfg), "min_shares": cfg["hedge"]["min_shares"],
           "quantity": cfg["size"]["quantity"], "put_delta": bt.get("put_delta", 0.0),
           "stress_budget": bt.get("stress_budget", 0.0)}
    return {k: desk.clean(v) for k, v in out.items()}


def closes(out):
    t = out["trades"]
    return t[t["action"] == "close"] if len(t) else t


def daily(out):
    # one row per day, same shape as the desk book
    eq = out["equity"]
    if eq.empty:
        return []
    total = eq.groupby("date")["equity"].last()
    c = closes(out)
    done = c.groupby("date")["pnl_net"].sum() if len(c) else pd.Series(dtype=float)
    realized = done.reindex(total.index, fill_value=0.0).cumsum()
    return [{"date": d, "realized": desk.clean(r), "open": desk.clean(v - r), "total": desk.clean(v)}
            for d, v, r in zip(total.index, total, realized)]


def summarize(out, cfg):
    m, eq, t = metrics.summary(out, cfg), out["equity"], out["trades"]
    keep = ["pnl", "max_dd", "trades", "win_rate", *metrics.GAPS]
    return {**{k: desk.clean(m[k]) for k in keep},
            "opens": int((t["action"] == "open").sum()) if len(t) else 0,
            "hedges": len(out["hedges"]),
            "fees": desk.clean(float(eq["fees"].iloc[-1])) if len(eq) else 0.0,
            "days": int(eq["date"].nunique()) if len(eq) else 0}


def trade_rows(out):
    t = out["trades"]
    if t.empty:
        return []
    t = t.assign(pnl=t["pnl_net"]) if "pnl_net" in t else t
    return desk.rows(t, desk.TRADE_COLS + ["commission"])


def book(cfg, days, cache, chain):
    out = engine.live(cfg, days, cache)
    s, c = out["signals"], closes(out)
    return {"rules": rules(cfg), "summary": summarize(out, cfg), "book": daily(out),
            "trades": trade_rows(out), "realized": desk.clean(float(c["pnl_net"].sum()) if len(c) else 0.0),
            "position": desk.position(out["open"][0], chain, cfg) if out["open"] else None,
            "signal": s["signal"].iloc[-1] if len(s) else None}


def entry(b, sh, days, caches, chain):
    # one bad book never stops the others
    head = {"name": b["name"], "exp": b.get("exp"), "variant": b.get("variant"), "error": None}
    if b.get("placeholder"):
        return {**head, "placeholder": b["placeholder"]}
    try:
        cfg = book_cfg(b, sh["capital"])
        cache = caches.setdefault((cfg["signal"]["forecaster"], cfg["backtest"]["fit_years"]), {})
        return {**head, **book(cfg, days, cache, chain)}
    except (Exception, SystemExit) as e:
        return {**head, "error": str(e) or type(e).__name__}


def snapshot(path=None, root=None):
    spec = config.read(path or PATH)
    sh, root = spec["shadow"], root or LIVE
    days = plan(root, sh["start"], config.load())
    chain = engine.read(days[-1][1], "chain") if days else None
    caches = {}
    return {"asof": runner.stamp(days[-1][0]) if days else None, "start": sh["start"],
            "capital": sh["capital"], "min_days": sh["min_days"],
            "snapshots": [{"date": str(a.date()), "ts": runner.stamp(a), "folder": key(root, f)}
                          for a, f in days],
            "books": [entry(b, sh, days, caches, chain) for b in spec["book"]]}


def write(out=None, path=None, root=None):
    out = out or OUT
    snap = snapshot(path, root)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(snap, indent=1, allow_nan=False, default=str) + "\n")
    return out


def main():
    out = write()
    snap = json.loads(out.read_text())
    print(f"shadow books -> {out}  ({len(snap['snapshots'])} snapshot days from {snap['start']})")
    for b in snap["books"]:
        s = b.get("summary") or {}
        note = b.get("placeholder") or b.get("error") or (
            f"P&L {s['pnl']:+,.0f}  trades {s['trades']}  hedges {s['hedges']}  "
            f"position {(b['position'] or {}).get('side', 'flat')}")
        print(f"  {b['name']:<28} {note}")


if __name__ == "__main__":
    main()
