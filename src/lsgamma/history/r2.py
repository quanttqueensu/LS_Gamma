import sys
from pathlib import Path

import boto3
import duckdb
import pandas as pd
import yfinance as yf

ROOT = Path(__file__).resolve().parents[3]
CACHE = ROOT / "data" / "r2"
OPTIONS = CACHE / "options" / "SPY"
DAILY = CACHE / "daily"
BUCKET = "quantt-historical-market-data"
PREFIX = "options/SPY/tick/"
TZ = "America/New_York"
SPY_PERMNO = 84398
CRSP_COLS = ["dlycaldt", "dlyopen", "dlyhigh", "dlylow", "dlyclose",
             "dlyvol", "dlyret", "dlyretx", "dlyorddivamt"]
RAW_DAILY = {"cboe": "wrds/cboe_all/cboe.parquet",
             "ff": "wrds/ff_all/factors_daily.parquet"}
YF = {"^VIX9D": "vix9d", "^VIX3M": "vix3m", "^VVIX": "vvix"}
YF_END = "2026-08-01"  # exclusive; frozen through 2026-07-31


def _env():
    out = {}
    for line in (ROOT / ".env").read_text().splitlines():
        k, sep, v = line.partition("=")
        if sep and not k.strip().startswith("#"):
            out[k.strip()] = v.strip().strip("'\"")
    return out


def _client(env):
    return boto3.client(
        "s3", endpoint_url=f"https://{env['R2_ACCOUNT_ID']}.r2.cloudflarestorage.com",
        aws_access_key_id=env["R2_ACCESS_KEY_ID"],
        aws_secret_access_key=env["R2_SECRET_ACCESS_KEY"], region_name="auto")


def connect():
    env = _env()
    con = duckdb.connect()
    con.execute("INSTALL httpfs; LOAD httpfs")
    con.execute("SET s3_endpoint=?", [f"{env['R2_ACCOUNT_ID']}.r2.cloudflarestorage.com"])
    con.execute("SET s3_access_key_id=?", [env["R2_ACCESS_KEY_ID"]])
    con.execute("SET s3_secret_access_key=?", [env["R2_SECRET_ACCESS_KEY"]])
    con.execute("SET s3_region='auto'; SET s3_url_style='path'")
    con.execute(f"SET TimeZone='{TZ}'")
    return con


def remote_files(client):
    objs = []
    for page in client.get_paginator("list_objects_v2").paginate(Bucket=BUCKET, Prefix=PREFIX):
        objs += page.get("Contents", [])
    return {o["Key"]: o["Size"] for o in objs if o["Key"].endswith(".parquet")}


def _download(client, key, path, size=None):
    if path.exists() and (size is None or path.stat().st_size == size):
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".part")
    client.download_file(BUCKET, key, str(tmp))
    tmp.rename(path)
    return True


def sync_options(client):
    files = remote_files(client)
    for i, (key, size) in enumerate(sorted(files.items()), 1):
        path = OPTIONS / Path(key).name
        new = _download(client, key, path, size)
        print(f"[{i}/{len(files)}] {path.name} {size / 1e6:.0f} MB "
              f"{'downloaded' if new else 'cached'}", flush=True)


def sync_crsp():
    path = DAILY / "crsp_spy.parquet"
    if path.exists():
        return
    DAILY.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".part")
    src = f"s3://{BUCKET}/wrds/crsp_a_stock/dsf_v2.parquet"
    connect().execute(
        f"COPY (SELECT {', '.join(CRSP_COLS)} FROM read_parquet('{src}') "
        f"WHERE permno = {SPY_PERMNO} ORDER BY dlycaldt) TO '{tmp}' (FORMAT parquet)")
    tmp.rename(path)


def sync():
    client = _client(_env())
    sync_options(client)
    for name, key in RAW_DAILY.items():
        _download(client, key, DAILY / f"{name}.parquet")
    print("cboe, ff cached", flush=True)
    sync_crsp()
    print("crsp_spy cached", flush=True)
    yf_indices()
    print("yf_indices cached", flush=True)


def yf_indices():
    path = DAILY / "yf_indices.parquet"
    if path.exists():
        return pd.read_parquet(path)
    df = yf.download(list(YF), start="1990-01-01", end=YF_END, interval="1d",
                     auto_adjust=True, progress=False)["Close"]
    df = df.rename(columns=YF)[list(YF.values())]
    df.columns.name = None
    df.index = pd.to_datetime(df.index).tz_localize(None).rename("date")
    df = df.dropna(how="all")
    DAILY.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path)
    return df


def trades(day):
    day = pd.Timestamp(day)
    path = OPTIONS / f"{day:%Y-%m}.parquet"
    start = (day.tz_convert(TZ) if day.tz else day.tz_localize(TZ)).normalize()
    con = duckdb.connect()
    con.execute(f"SET TimeZone='{TZ}'")
    df = con.execute(
        "SELECT ts, expiry, opt_type, strike, price, size, exchange, "
        "COALESCE(TRY_CAST(NULLIF(conditions, '') AS INTEGER), 0) AS conditions "
        "FROM read_parquet(?) WHERE ts >= ? AND ts < ? ORDER BY ts",
        [str(path), start.to_pydatetime(), (start + pd.DateOffset(days=1)).to_pydatetime()]).df()
    df["ts"] = df["ts"].dt.tz_convert(TZ)
    df["expiry"] = pd.to_datetime(df["expiry"]).dt.date
    return df


def daily_raw():
    return {"crsp": pd.read_parquet(DAILY / "crsp_spy.parquet"),
            "cboe": pd.read_parquet(DAILY / "cboe.parquet"),
            "ff": pd.read_parquet(DAILY / "ff.parquet"),
            "yf": yf_indices()}


if __name__ == "__main__":
    if sys.argv[1:] != ["sync"]:
        sys.exit("usage: python -m lsgamma.history.r2 sync")
    sync()
