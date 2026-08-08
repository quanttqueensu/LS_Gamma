# QUANTT R2 Data Reference

**Bucket:** `quantt-historical-market-data`
**Access:** Cloudflare R2 (S3-compatible), read-only API token
**Last verified:** 2026-08-08

---

## 1. Mental model

Cloudflare R2 is object storage — effectively a hard drive on the internet. It
implements the **S3 API**, which means every tool built for Amazon S3 works
against it unchanged: `boto3`, `duckdb`, `polars`, `pyarrow`, the AWS CLI.

Three concepts:

| Term | Meaning |
| --- | --- |
| **Bucket** | The top-level container. There is exactly one: `quantt-historical-market-data` |
| **Key** | An object's full path, e.g. `options/SPY/tick/2024-03.parquet` |
| **Prefix** | The leading part of a key. Slashes are a naming convention, not real folders — but tools present them as folders |

There are no real directories. `options/SPY/tick/2024-03.parquet` is a single
flat key that happens to contain slashes. This matters because listing "folders"
requires an explicit `Delimiter="/"` argument — otherwise the API returns every
key it can find.

---

## 2. Credentials

Cloudflare issues four values. Only three are used.

| Value | Used for | In `.env` as |
| --- | --- | --- |
| Account ID | Building the endpoint URL | `R2_ACCOUNT_ID` |
| Access Key ID | S3 username | `R2_ACCESS_KEY_ID` |
| Secret Access Key | S3 password | `R2_SECRET_ACCESS_KEY` |
| Token value (`cfat_...`) | Cloudflare's own REST API — **not used here** | — |

The account ID is the subdomain of the endpoint URL:

```
https://<account_id>.r2.cloudflarestorage.com
```

`.env` file:

```
R2_ACCOUNT_ID=...
R2_ACCESS_KEY_ID=...
R2_SECRET_ACCESS_KEY=...
```

Add `.env` to `.gitignore`. The WRDS data in this bucket is licensed to Queen's
for academic use — do not commit credentials or data extracts to a public repo.

---

## 3. Bucket structure

```
quantt-historical-market-data/
│
├── options/                        Curated options trade data, by ticker
│   ├── GLD/tick/
│   ├── IWM/tick/
│   ├── QQQ/tick/
│   ├── SLV/tick/
│   ├── SPY/tick/                   ← primary dataset
│   │   ├── 2014-06.parquet         8-22 MB per month
│   │   ├── 2014-07.parquet
│   │   └── ... 146 files, no gaps ...
│   │   └── 2026-07.parquet
│   └── TLT/tick/
│
├── wrds/                           Raw WRDS library dump, 80+ libraries
│   ├── crsp_a_stock/               Equity prices
│   │   ├── dsf.parquet             2.2 GB — legacy format
│   │   ├── dsf_v2.parquet          4.8 GB — newer format, preferred
│   │   ├── dsedist.parquet         Distributions
│   │   └── ...
│   ├── cboe_all/
│   │   └── cboe.parquet            0.4 MB — VIX and related indices
│   ├── ff_all/
│   │   ├── factors_daily.parquet   0.3 MB — includes risk-free rate
│   │   └── ...
│   ├── frb_all/
│   │   ├── rates_daily.parquet     1.2 MB — Fed H.15 rates
│   │   └── ...
│   └── ... 76 other libraries ...
│
└── _recycle_bin/                   Deleted WRDS sample datasets — ignore
```

**Note:** there is no `optionm` (OptionMetrics) and no `taq` library. This means
**no bid/ask quote data exists for options anywhere in the bucket** — only
executed trades.

---

## 4. Dataset inventory

### 4.1 SPY options — `options/SPY/tick/YYYY-MM.parquet`

Executed option trades, tick-level. **146 files, 2014-06 through 2026-07, no
missing months, ~11 GB total.**

| Column | Type | Meaning |
| --- | --- | --- |
| `ts` | TIMESTAMP WITH TIME ZONE | Execution time, millisecond precision, US Eastern |
| `underlying` | VARCHAR | Always `SPY` in this folder |
| `expiry` | DATE | Contract expiration date |
| `opt_type` | VARCHAR | `C` or `P` |
| `strike` | DOUBLE | Strike price |
| `price` | DOUBLE | Trade price per share (multiply by 100 for contract value) |
| `size` | UINTEGER | Number of contracts in the trade |
| `exchange` | USMALLINT | Exchange code where the trade printed |
| `conditions` | VARCHAR | Trade condition codes |
| `osi` | VARCHAR | OSI contract symbol, e.g. `O:SPY140719P00192000` |

**What is NOT here:** implied volatility, greeks, bid/ask, open interest, or the
underlying spot price. All must be computed or sourced elsewhere.

**Scale:** roughly 1M rows per month, ~100k trades per day across ~1,500 distinct
contracts, spanning 23-24 expiries and 150-170 strikes daily.

**OSI symbol format:** `O:` + ticker + `YYMMDD` + `C`/`P` + strike × 1000, zero-padded
to 8 digits. It is fully redundant with the other columns, but useful as a unique
contract key for grouping.

### 4.2 Equity prices — `wrds/crsp_a_stock/`

CRSP Daily Stock File. SPY is **PERMNO 84398**.

**`dsf_v2.parquet` (preferred)** — 50 columns, SPY coverage 1993-01-29 to
**2025-12-31** (8,288 days).

| Column | Meaning |
| --- | --- |
| `permno` | Security identifier — 84398 for SPY |
| `ticker` | Ticker symbol, so you can filter on `'SPY'` directly |
| `dlycaldt` | Calendar date |
| `dlyclose` | Closing price |
| `dlyopen`, `dlyhigh`, `dlylow` | Daily OHLC |
| `dlybid`, `dlyask` | Closing bid/ask on the underlying |
| `dlyvol` | Share volume |
| `dlyret` | Return including dividends |
| `dlyretx` | Return excluding dividends — **use this for realized vol** |
| `dlyorddivamt` | Ordinary dividend amount on ex-date |

**`dsf.parquet` (legacy)** — 20 columns, SPY coverage 1993-01-29 to
**2024-12-31**. Column names are terser (`prc`, `ret`, `retx`, `vol`, `bid`,
`ask`, `openprc`, `bidlo`, `askhi`, `cfacpr`).

**CRSP gotcha:** in the legacy file, a **negative `prc` means no trade occurred**
and the value is the negative of the bid-ask midpoint. Always use `ABS(prc)`.
`dsf_v2` does not have this convention.

**Dividends:** `dlyorddivamt` is non-zero only on ex-dividend dates. SPY pays
quarterly (March, June, September, December), recently $1.59–$1.99 per share.

### 4.3 Volatility indices — `wrds/cboe_all/cboe.parquet`

Coverage **1986-01-02 to 2026-06-30**, 10,742 rows.

| Column group | Index |
| --- | --- |
| `vixo`, `vixh`, `vixl`, `vix` | VIX — S&P 500 30-day implied vol (open/high/low/close) |
| `vxoo`, `vxoh`, `vxol`, `vxo` | VXO — original 1993 VIX methodology, **discontinued (NaN in recent rows)** |
| `vxno`, `vxnh`, `vxnl`, `vxn` | VXN — Nasdaq-100 implied vol |
| `vxdo`, `vxdh`, `vxdl`, `vxd` | VXD — Dow Jones implied vol |

Use `vix` as the daily close. `vxn` becomes relevant if the strategy is ever
tested on QQQ.

### 4.4 Risk-free rate — two options

**`wrds/ff_all/factors_daily.parquet`** — Fama-French daily factors.
Coverage through **2026-04-30**. Columns: `date`, `mktrf`, `smb`, `hml`, `rf`,
`umd`. The `rf` column is the daily 1-month T-bill rate in decimal form
(e.g. `0.0001` = 1 basis point per day).

**`wrds/frb_all/rates_daily.parquet`** — Federal Reserve H.15 release, ~80
columns covering the full Treasury curve. Coverage ends **2025-02-13**, and the
last few rows are sparsely populated — the last fully-populated row is
2025-02-11.

Relevant columns if used:

| Column | Meaning |
| --- | --- |
| `dgs1mo`, `dgs3mo`, `dgs6mo`, `dgs1` | Constant-maturity Treasury yields |
| `dtb4wk`, `dtb3`, `dtb6`, `dtb1yr` | T-bill secondary market rates |
| `sofr`, `effr` | Overnight funding rates |

**Trade-off:** FRB has the better shape (a full term structure that can be
interpolated to an option's exact DTE) but is 17 months stale. Fama-French has
only one tenor but runs current. For 7–28 DTE options, the 1-month FF rate is a
reasonable tenor match.

### 4.5 Coverage summary

| Dataset | Starts | Ends | Gap vs options |
| --- | --- | --- | --- |
| SPY options | 2014-06 | **2026-07** | — |
| CBOE VIX | 1986-01 | 2026-06 | 1 month |
| FF risk-free | — | 2026-04 | 3 months |
| CRSP `dsf_v2` | 1993-01 | 2025-12 | 7 months |
| CRSP `dsf` | 1993-01 | 2024-12 | 19 months |
| FRB rates | — | 2025-02 | 17 months |

**Binding constraint:** CRSP spot ends 2025-12-31. The fully-supported backtest
window is therefore **2014-06 through 2025-12** (~11.5 years), which includes
August 2015, February 2018, March 2020, and 2022. Data after 2025-12 requires an
external spot source.

---

## 5. Two access patterns

Choose based on file size.

| | **boto3** | **DuckDB** |
| --- | --- | --- |
| Use for | Listing objects, small whole-file reads | Querying large Parquet in place |
| How it works | Downloads the full object | Reads Parquet metadata over HTTP range requests, fetches only needed columns and row groups |
| Good for | `cboe.parquet` (0.4 MB), `factors_daily.parquet` (0.3 MB) | `dsf_v2.parquet` (4.8 GB), monthly option files |
| Bad for | Anything over ~200 MB | Listing what exists |

**Why DuckDB matters here:** Parquet is columnar. A query selecting 4 of 10
columns transfers roughly 4 columns' worth of bytes. Row-group statistics let a
`WHERE` clause skip chunks of the file entirely. Filtering `dsf_v2.parquet` to
`permno = 84398` reads a small fraction of its 4.8 GB rather than all of it.

---

## 6. Connection code

### 6.1 boto3

```python
import os
import boto3
from botocore.config import Config
from dotenv import load_dotenv

load_dotenv()

s3 = boto3.client(
    "s3",
    endpoint_url=f"https://{os.environ['R2_ACCOUNT_ID']}.r2.cloudflarestorage.com",
    aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
    aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],
    region_name="auto",
    config=Config(
        signature_version="s3v4",
        s3={"addressing_style": "path"},
    ),
)
```

Three non-obvious parameters, all required:

- **`region_name="auto"`** — R2 has no regions, but botocore refuses to sign a
  request without a region string. Omitting this raises `NoRegionError`.
- **`signature_version="s3v4"`** — R2 rejects the older SigV2 signing scheme.
- **`addressing_style="path"`** — forces `endpoint/bucket/key` rather than
  `bucket.endpoint/key`. Virtual-host style can fail against R2.

### 6.2 DuckDB

```python
import duckdb

con = duckdb.connect()
con.execute("INSTALL httpfs; LOAD httpfs;")
con.execute(f"SET s3_endpoint='{account_id}.r2.cloudflarestorage.com'")
con.execute(f"SET s3_access_key_id='{access_key}'")
con.execute(f"SET s3_secret_access_key='{secret_key}'")
con.execute("SET s3_region='auto'")
con.execute("SET s3_url_style='path'")
```

Note the endpoint here is the **host only**, with no `https://` prefix — unlike
boto3, which wants the full URL.

Newer DuckDB versions prefer `CREATE SECRET` syntax over `SET`. Both work; `SET`
has wider version compatibility.

---

## 7. Query cookbook

### 7.1 List folders (not files)

```python
def folders(bucket, prefix=""):
    """List folder names one level below a prefix."""
    out = []
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix, Delimiter="/"):
        for p in page.get("CommonPrefixes", []):
            out.append(p["Prefix"])
    return out
```

`Delimiter="/"` is the key argument. Without it, the API returns individual keys
and a listing of `options/` would return thousands of filenames instead of six
ticker folders.

### 7.2 List objects with pagination

```python
def all_keys(bucket, prefix=""):
    """List every object under a prefix, past the 1000-key API cap."""
    out = []
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for o in page.get("Contents", []):
            out.append((o["Key"], o["Size"] / 1_000_000))
    return out
```

A plain `list_objects_v2` call caps at 1000 keys and truncates silently. Always
paginate.

### 7.3 Inspect a schema without downloading

```python
con.execute(f"""
    DESCRIBE SELECT * FROM read_parquet('{path}') LIMIT 0
""").df()
```

Reads only the Parquet footer — a small metadata block at the end of the file.
Works instantly even on the 4.8 GB `dsf_v2.parquet`.

### 7.4 Read a small file whole

```python
import io
import pandas as pd

obj = s3.get_object(Bucket=BUCKET, Key="wrds/cboe_all/cboe.parquet")
vix = pd.read_parquet(io.BytesIO(obj["Body"].read()))
```

### 7.5 SPY daily prices from CRSP

```python
spy = con.execute(f"""
    SELECT dlycaldt AS date,
           dlyclose AS close,
           dlyopen  AS open,
           dlyhigh  AS high,
           dlylow   AS low,
           dlyvol   AS volume,
           dlyretx  AS ret_ex_div,
           dlyorddivamt AS dividend
    FROM read_parquet('s3://{BUCKET}/wrds/crsp_a_stock/dsf_v2.parquet')
    WHERE permno = 84398
      AND dlycaldt BETWEEN DATE '2014-06-01' AND DATE '2025-12-31'
    ORDER BY dlycaldt
""").df()
```

### 7.6 One day of option trades

```python
day = "2024-03-15"
month_file = f"s3://{BUCKET}/options/SPY/tick/2024-03.parquet"

trades = con.execute(f"""
    SELECT ts, expiry, strike, opt_type, price, size, osi
    FROM read_parquet('{month_file}')
    WHERE CAST(ts AS DATE) = DATE '{day}'
      AND price >= 0.10
""").df()
```

The `price >= 0.10` filter excludes penny options — below roughly a dime, prices
are quantized too coarsely for Black-Scholes inversion to produce a meaningful
implied volatility.

### 7.7 Aggregate trades to contract level

```python
contracts = con.execute(f"""
    SELECT expiry,
           DATE_DIFF('day', DATE '{day}', expiry) AS dte,
           strike,
           opt_type,
           COUNT(*)                                AS trades,
           SUM(size)                               AS volume,
           SUM(price * size) / SUM(size)           AS vwap
    FROM read_parquet('{month_file}')
    WHERE CAST(ts AS DATE) = DATE '{day}'
      AND price >= 0.10
    GROUP BY 1, 2, 3, 4
    HAVING SUM(size) > 100
    ORDER BY volume DESC
""").df()
```

Volume-weighted average price is more robust than a simple mean, but is still
sensitive to single block trades.

### 7.8 Query multiple months with a glob

```python
con.execute(f"""
    SELECT CAST(ts AS DATE) AS day, COUNT(*) AS trades
    FROM read_parquet('s3://{BUCKET}/options/SPY/tick/2024-*.parquet')
    GROUP BY 1 ORDER BY 1
""").df()
```

Globs work in `read_parquet`. DuckDB reads each file's metadata and skips those
whose row groups cannot match the filter.

### 7.9 Filter to the strategy's target zone

```python
target = con.execute(f"""
    SELECT *
    FROM read_parquet('{month_file}')
    WHERE CAST(ts AS DATE) = DATE '{day}'
      AND price >= 0.10
      AND DATE_DIFF('day', DATE '{day}', expiry) BETWEEN 7 AND 28
""").df()
```

---

## 8. Gotchas

**Options data is trades, not quotes.** Every row is an executed transaction, so
prices bounce between bid and ask. There is no mid-price. Implied volatility
computed from trade prints is noisier than from quote midpoints, and the noise
scales with the bid-ask spread — which is widest exactly where the data is
thinnest.

**0-DTE dominates volume.** SPY has had daily expirations since 2022. On a
typical day the most-traded contracts are all same-day expiries, often by an
order of magnitude. The strategy targets 7–28 DTE, so most rows in the dataset
are not usable for it. Effective data volume is far smaller than 11 GB suggests.

**Wing liquidity is thin.** At ~21 DTE and ~5% OTM, individual strikes trade in
the tens to low hundreds of contracts per day, versus hundreds of thousands at
the money. This affects execution cost assumptions and the reliability of smile
fits at the wings.

**Expiry gaps are real, not bugs.** Daily expiries are listed only a couple of
weeks ahead, and market holidays remove expirations. A DTE ladder may jump from
13 to 21 days with nothing between. Verified on 2024-03-15, where Good Friday
(2024-03-29) removed one expiry and the April dailies were not yet listed.

**Avoid triple-witching days for sanity checks.** The third Friday of March,
June, September, and December sees atypical volume and open interest. 2024-03-15
was both a triple-witching day and an ex-dividend date — a poor choice of sample
day.

**Timestamps are timezone-aware.** `ts` carries a US Eastern offset. Casting with
`CAST(ts AS DATE)` respects it. Be careful mixing with naive timestamps.

**Moneyness needs intraday spot.** Computing `strike / close - 1` measures a
9:30 AM trade against a 4:00 PM price. Fine for rough profiling, wrong for
anything real.

**No intraday spot exists in this bucket.** CRSP is daily only. Intraday SPY
prices must come from Alpaca, or be implied from the options themselves via
put-call parity.

**Legacy CRSP negative prices.** In `dsf.parquet`, `prc < 0` signals no trade and
holds the negative bid-ask midpoint. Use `ABS(prc)`. Not an issue in `dsf_v2`.

**`numtrd` is null for SPY** in the legacy `dsf.parquet`. Do not rely on it.

---

## 9. Deferred decisions

Five design questions raised during data verification, held for the planning
phase:

1. **Wing distance.** Keep the proposed 5% OTM strangle strikes despite thin
   liquidity, or move closer to spot? Affects strike selection, transaction cost
   modelling, and how far the fitted smile can be trusted.

2. **Spot price source.** CRSP daily is confirmed but daily-only. The strategy
   requires intraday spot for realized volatility and hedge simulation. Options:
   Alpaca minute bars, put-call parity implied from the options data, or both
   with one cross-checking the other.

3. **Bar aggregation frequency.** Collapse ticks to 1-minute, 5-minute, or
   30-minute bars? Drives storage footprint, hedging granularity, and how much
   trade-price noise is averaged out.

4. **Risk-free rate source.** Fama-French `rf` (current through 2026-04, single
   1-month tenor) versus FRB H.15 (full term structure, stale after 2025-02).
   Possibly FRB historically and FF for recent dates.

5. **Backtest split boundaries.** Where train / validation / test boundaries fall
   across the 2014-06 to 2025-12 window. Should be fixed before any results are
   generated, so the holdout remains genuinely out-of-sample.
