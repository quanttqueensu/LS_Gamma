import argparse
import ast
import hashlib
import json
import shutil
import subprocess
import tomllib
from datetime import date, datetime
from multiprocessing import Pool
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

from lsgamma import experiments
from lsgamma.history import daily, marks, r2, spot, spread, trades
from lsgamma.pipeline import features, store

REPO = Path(__file__).resolve().parents[3]
CONFIG = REPO / "configs" / "backtest.toml"
DATA = REPO / "data" / "backtest"
FIRST_DAY = "2014-06-02"
OPEN = "09:30"
SOURCES = [f"history/{m}.py" for m in ["r2", "daily", "spread", "trades", "spot", "marks", "build"]]
SOURCES += ["pipeline/features.py", "pipeline/chain.py"]  # build output depends on these
PKG = Path(__file__).resolve().parents[1]
RECENT_DAYS = 5  # held contracts stay listed this long


class Skip(RuntimeError):
    pass


def load(path=CONFIG):
    with open(path, "rb") as f:
        return tomllib.load(f)["history"]


def third_friday(year, month):
    first = date(year, month, 1)
    return date(year, month, 1 + (4 - first.weekday()) % 7 + 14)


def projected(divs, day, n=2):
    # next ex-dates: third Friday each quarter, last amount
    past = divs[pd.to_datetime(divs.index) < pd.Timestamp(day)]
    if past.empty:
        return spot.NO_DIVS
    last = pd.Timestamp(past.index[-1])
    months = [last.year * 12 + last.month - 1 + 3 * i for i in range(1, n + 1)]
    ex = [third_friday(m // 12, m % 12 + 1) for m in months]
    return pd.Series(float(past.iloc[-1]), index=pd.Index(ex, dtype=object))


def rate(day, idx):
    irx = idx.loc[idx.index < pd.Timestamp(day), "irx"].dropna()
    return float(irx.iloc[-1]) / 100


def context(day, idx, divs, model, seen=None):
    return {"r": rate(day, idx), "dividends": projected(divs, day), "spread": model,
            "contracts": recent(seen, day)}


def seen_month(path, cfg):
    con = duckdb.connect()
    con.execute(f"SET TimeZone='{trades.TZ}'")
    codes = ", ".join(str(c) for c in cfg["conditions"])
    df = con.execute(
        "SELECT DISTINCT CAST(ts AS DATE) AS day, expiry, opt_type AS right, strike "
        "FROM read_parquet(?) WHERE price >= ? AND CAST(CAST(ts AS TIMESTAMP) AS TIME) > ? "
        f"AND COALESCE(TRY_CAST(NULLIF(conditions, '') AS INTEGER), 0) IN ({codes})",
        [str(path), cfg["min_price"], OPEN]).df()
    df["day"], df["expiry"] = df["day"].dt.date, df["expiry"].dt.date
    return df.assign(expiry=trades.fridays(df["expiry"]))


def recent(seen, day, n=RECENT_DAYS):
    if seen is None or seen.empty:
        return pd.DataFrame({"expiry": pd.Series(dtype=object), "strike": pd.Series(dtype=float),
                             "right": pd.Series(dtype=str)})
    past = sorted(d for d in seen["day"].unique() if d < day)[-n:]
    u = seen.loc[seen["day"].isin(past), ["expiry", "strike", "right"]]
    return u.drop_duplicates().reset_index(drop=True)


def contracts(tr):
    u = tr[["expiry", "strike", "opt_type"]].rename(columns={"opt_type": "right"})
    return u.drop_duplicates().reset_index(drop=True)


def rows(fw, cand, t, asof, cfg):
    dte = cand["expiry"].map(lambda e: (e - asof.date()).days)
    u = cand[dte.between(cfg["min_dte"], cfg["max_dte"])]
    fwd = spot.forward_at(fw, [t] * len(u), u["expiry"])
    keep = np.abs(np.log(u["strike"].to_numpy() / fwd)) <= cfg["hold_k"]
    return u[keep], fwd[keep]


def smile(fw, fit_on, expiries, r, cfg):
    fit_on = fit_on[fit_on["expiry"].isin(set(expiries))]
    ivs = marks.trade_ivs(fit_on, spot.forward_at(fw, fit_on["ts"], fit_on["expiry"]), r)
    return marks.smiles(ivs, cfg)


def candidates(day_trades, ctx, asof, cfg):
    # last days' contracts plus today's before the cutoff
    cut = asof - pd.Timedelta(cfg["lag"])
    tr = trades.window(day_trades, trades.at(asof.date(), OPEN), cut, cfg)
    return tr, pd.concat([ctx["contracts"], contracts(tr)]).drop_duplicates()


def decision(day_trades, ctx, asof, cfg):
    cut = asof - pd.Timedelta(cfg["lag"])
    tr, cand = candidates(day_trades, ctx, asof, cfg)
    fw = spot.forwards(tr, ctx["r"], ctx["dividends"], asof.date(), cfg)
    if fw is None:
        raise Skip("no parity forward")
    u, fwd = rows(fw, cand, cut, asof, cfg)
    recent = tr[tr["ts"] > cut - pd.Timedelta(cfg["lookback"])]
    sm = smile(fw, recent, u["expiry"], ctx["r"], cfg)
    ch = marks.chain(u, fwd, sm, asof, ctx["r"], spot.spot(fw, cut), ctx["spread"])
    return ch.dropna(subset=["mid"]).reset_index(drop=True), cand, sm


def decide(day_trades, ctx, asof, cfg):
    ch = decision(day_trades, ctx, asof, cfg)[0]
    if ch.empty:
        raise Skip("no smile")
    return ch


def fill_forward(day_trades, ctx, asof, end, cfg):
    # fill-window pairs, else carried from the open
    for start, need in [(asof, cfg["fill_min_pairs"]), (trades.at(asof.date(), OPEN), None)]:
        tr = trades.window(day_trades, start, end, cfg)
        fw = spot.forwards(tr, ctx["r"], ctx["dividends"], asof.date(), cfg, need)
        if fw is not None:
            return fw
    return None


def fill(day_trades, ctx, asof, cfg, backup=None):
    end = asof + pd.Timedelta(cfg["fill_window"])
    if backup is None:
        try:
            backup = decision(day_trades, ctx, asof, cfg)[1:]
        except Skip:
            backup = (candidates(day_trades, ctx, asof, cfg)[1], pd.DataFrame(columns=marks.SMILE))
    cand, decide_sm = backup
    fw = fill_forward(day_trades, ctx, asof, end, cfg)
    if fw is None:
        return pd.DataFrame(columns=marks.COLUMNS + ["src"])
    u, fwd = rows(fw, cand, end, asof, cfg)
    sm = smile(fw, trades.window(day_trades, asof, end, cfg), u["expiry"], ctx["r"], cfg)
    old = decide_sm.loc[~decide_sm.index.isin(sm.index)]
    ch = marks.chain(u, fwd, pd.concat([sm, old]), asof, ctx["r"], spot.spot(fw, end), ctx["spread"])
    src = np.where(ch["expiry"].isin(set(sm.index)), "fill_smile",
                   np.where(ch["expiry"].isin(set(old.index)), "decide_smile", None))
    return ch.assign(src=src)


def snapshot(day_trades, ctx, asof, cfg):
    ch, cand, sm = decision(day_trades, ctx, asof, cfg)
    if ch.empty:
        raise Skip("no smile")
    return {"chain": ch, "fill": fill(day_trades, ctx, asof, cfg, (cand, sm)),
            "atm_iv": features.atm_iv(ch)}


def build_day(day, ctx, cfg, root):
    tr = r2.trades(day)
    if tr.empty:
        return day, 0, [{"date": str(day), "time": "all", "why": "no_trades"}]
    tmp = root / ".tmp"
    shutil.rmtree(tmp / str(day), ignore_errors=True)
    n, skipped = 0, []
    for hhmm in cfg["grid"]:
        asof = trades.at(day, hhmm)
        try:
            snap = snapshot(tr, ctx, asof, cfg)
        except Skip as e:
            skipped.append({"date": str(day), "time": hhmm, "why": str(e)})
            continue
        for name, df in snap.items():
            store.save(df, name, asof, root=tmp)
        n += 1
    if n:
        shutil.rmtree(root / str(day), ignore_errors=True)
        (tmp / str(day)).rename(root / str(day))
    return day, n, skipped


def _job(args):
    return build_day(*args)


def sources(pkg=PKG):
    # ast dump ignores comments and whitespace
    h = hashlib.sha256()
    for rel in SOURCES:
        h.update(ast.dump(ast.parse((pkg / rel).read_text())).encode())
    return h.hexdigest()[:12]


def dirty():
    out = subprocess.run(["git", "status", "--porcelain", "--", "src", "configs"], cwd=REPO,
                         capture_output=True, text=True)
    return bool(out.stdout.strip())


def commit():
    return experiments.commit().removesuffix("-dirty") + ("-dirty" if dirty() else "")


def config_hash(cfg, model):
    blob = json.dumps({"history": cfg, "spread": model, "code": sources()},
                      sort_keys=True, default=str)
    return hashlib.sha256(blob.encode()).hexdigest()[:12]


def parity_closes(raw, idx, cfg):
    after = pd.Timestamp(raw["crsp"]["dlycaldt"].max())
    out = {}
    for day in pd.bdate_range(after + pd.Timedelta(days=1), cfg["last_day"]):
        if not (r2.OPTIONS / f"{day:%Y-%m}.parquet").exists():
            continue
        tr = r2.trades(day)
        if len(tr):
            out[day] = spot.parity_close(tr, day, rate(day, idx), cfg)
    return pd.Series(out, dtype=float).dropna()


def indices(raw, cfg):
    return daily.indices(raw["cboe"], raw["ff"], raw["yf"], cfg["last_day"])


def daily_data(raw, cfg, root, force=False):
    idx = indices(raw, cfg)
    path = root / "features.parquet"
    if force or not path.exists():
        closes = parity_closes(raw, idx, cfg)
        print(f"{len(closes)} parity closes after CRSP ends")
        feats = daily.features(daily.spy(raw["crsp"], closes), idx)
        path.parent.mkdir(parents=True, exist_ok=True)
        feats.to_parquet(path)
        print(f"saved {path}  ({len(feats)} rows)")
    return idx, pd.read_parquet(path).index.max().date()


def contracts_seen(start, end, cfg):
    months = pd.period_range(pd.Timestamp(start), pd.Timestamp(end), freq="M")
    paths = [r2.OPTIONS / f"{m}.parquet" for m in months]
    found = [seen_month(p, cfg) for p in paths if p.exists()]
    return pd.concat(found, ignore_index=True) if found else None


def missing_months(cfg):
    months = pd.period_range(FIRST_DAY, cfg["last_day"], freq="M")
    return [str(m) for m in months if not (r2.OPTIONS / f"{m}.parquet").exists()]


def days(crsp, start, end):
    # CRSP calendar, then weekdays with trades
    cal = pd.to_datetime(crsp["dlycaldt"])
    after = pd.bdate_range(cal.max() + pd.Timedelta(days=1), end)
    after = [d for d in after if (r2.OPTIONS / f"{d:%Y-%m}.parquet").exists()]
    out = [d.date() for d in [*cal, *after] if pd.Timestamp(start) <= d <= pd.Timestamp(end)]
    return sorted(set(out))


def manifest(root, cfg, h, run):
    path = root / "manifest.json"
    m = json.loads(path.read_text()) if path.exists() else {
        "version": cfg["version"], "config_hash": h, "config": cfg, "builds": []}
    m["builds"].append(run)
    path.write_text(json.dumps(m, indent=2, default=str))
    return path


def check_version(root, h):
    path = root / "manifest.json"
    if path.exists() and json.loads(path.read_text())["config_hash"] != h:
        raise SystemExit(f"{root.name} was built with other settings or code; use a new version")


def build(start, end, cfg, version=None, workers=1, force=False, resume=False):
    if pd.Timestamp(end) > pd.Timestamp(cfg["last_day"]):
        raise SystemExit(f"end {end} is after last_day {cfg['last_day']}; R2 ends there")
    real = (version or cfg["version"]) == cfg["version"]
    if real and dirty():
        raise SystemExit("src or configs has uncommitted changes; commit before building")
    missing = missing_months(cfg)
    if missing and real:
        raise SystemExit(f"{len(missing)} R2 months not synced (first {missing[0]}); run r2 sync")
    cfg = {**cfg, "version": version or cfg["version"]}
    root = DATA / cfg["version"]
    model = spread.load()
    h = config_hash({k: v for k, v in cfg.items() if k != "version"}, model)
    check_version(root, h)
    raw = r2.daily_raw()
    todo = days(raw["crsp"], start, end)
    done = [d for d in todo if (root / str(d)).exists()]
    if done and not (force or resume):
        raise SystemExit(f"{len(done)} days already built in {root}; use --resume or --force")
    if resume and not force:
        todo = [d for d in todo if d not in done]
    idx, feats_end = daily_data(raw, cfg, root, force)
    divs = daily.dividends(raw["crsp"])
    seen = contracts_seen(pd.Timestamp(start) - pd.Timedelta(days=15), end, cfg)
    jobs = [(d, context(d, idx, divs, model, seen), cfg, root) for d in todo]
    n, skipped, built = 0, [], 0
    with Pool(workers) as pool:
        for i, (d, k, s) in enumerate(pool.imap(_job, jobs), 1):
            n, skipped, built = n + k, skipped + s, built + (k > 0)
            print(f"[{i}/{len(jobs)}] {d}: {k} snapshots, {len(s)} skipped", flush=True)
    shutil.rmtree(root / ".tmp", ignore_errors=True)
    run = {"config_hash": h, "commit": commit(),
           "built_at": datetime.now().isoformat(timespec="seconds"), "start": str(start),
           "end": str(end), "features_end": str(feats_end), "missing_months": missing,
           "days": built, "snapshots": n, "skipped": skipped}
    print(f"{built} days, {n} snapshots, {len(skipped)} skipped; {manifest(root, cfg, h, run)}")
    return run


def main(argv=None):
    cfg = load()
    p = argparse.ArgumentParser(description="Replay R2 trades into backtest snapshots.")
    p.add_argument("--start", default=FIRST_DAY)
    p.add_argument("--end", default=cfg["last_day"])
    p.add_argument("--version", help="throwaway version; skips the full-sync check")
    p.add_argument("--workers", type=int, default=1)
    p.add_argument("--force", action="store_true", help="overwrite built days and features")
    p.add_argument("--resume", action="store_true", help="skip days already built")
    a = p.parse_args(argv)
    build(a.start, a.end, cfg, a.version, a.workers, a.force, a.resume)


if __name__ == "__main__":
    main()
