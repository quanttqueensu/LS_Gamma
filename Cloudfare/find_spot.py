"""
find_spot.py — locate SPY underlying price data, and map full coverage.

Your options data has no spot price. Black-Scholes needs it, delta hedging
needs it, realized vol needs it. This script hunts for it in the bucket and
also reports how far your options history actually runs.

Run:   python find_spot.py
"""

import os
import re

import boto3
import duckdb
import pandas as pd
from botocore.config import Config
from dotenv import load_dotenv

load_dotenv()

ACCOUNT = os.environ["R2_ACCOUNT_ID"]
KEY_ID = os.environ["R2_ACCESS_KEY_ID"]
SECRET = os.environ["R2_SECRET_ACCESS_KEY"]
BUCKET = "quantt-historical-market-data"

s3 = boto3.client(
    "s3",
    endpoint_url=f"https://{ACCOUNT}.r2.cloudflarestorage.com",
    aws_access_key_id=KEY_ID,
    aws_secret_access_key=SECRET,
    region_name="auto",
    config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
)

pd.set_option("display.max_columns", None)
pd.set_option("display.width", 250)


def folders(prefix):
    out = []
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=BUCKET, Prefix=prefix, Delimiter="/"):
        for p in page.get("CommonPrefixes", []):
            out.append(p["Prefix"])
    return out


def all_keys(prefix):
    out = []
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=BUCKET, Prefix=prefix):
        for o in page.get("Contents", []):
            out.append((o["Key"], o["Size"] / 1_000_000))
    return out


# ---------------------------------------------------------------
# 1. How far does the SPY options history actually run?
# ---------------------------------------------------------------

print("=" * 70)
print("SPY OPTIONS COVERAGE")
print("=" * 70)

spy_files = all_keys("options/SPY/")
months = sorted(m for k, _ in spy_files for m in re.findall(r"(\d{4}-\d{2})", k))

if months:
    total_mb = sum(mb for _, mb in spy_files)
    print(f"Files:    {len(spy_files)}")
    print(f"Earliest: {months[0]}")
    print(f"Latest:   {months[-1]}")
    print(f"Total:    {total_mb:,.0f} MB")

    # gaps
    expected = pd.period_range(months[0], months[-1], freq="M").astype(str).tolist()
    missing = sorted(set(expected) - set(months))
    print(f"Missing months: {missing if missing else 'none'}")

# ---------------------------------------------------------------
# 2. Hunt for underlying price data
# ---------------------------------------------------------------

print()
print("=" * 70)
print("WHAT IS IN wrds/ ?")
print("=" * 70)

wrds_folders = folders("wrds/")
for f in wrds_folders:
    print("  ", f)

print()
print("=" * 70)
print("HUNTING FOR UNDERLYING PRICE DATA")
print("=" * 70)

# WRDS libraries that carry equity/ETF prices:
#   crsp   - daily & monthly stock file (the standard academic source)
#   taq    - tick-level trades and quotes
#   comp   - Compustat, fundamentals but has some pricing
#   optionm - OptionMetrics; its 'secprd' table has underlying closes
price_hints = ("crsp", "taq", "sec", "price", "equity", "stock", "dsf", "optionm", "ivy")

candidates = [f for f in wrds_folders if any(h in f.lower() for h in price_hints)]

if candidates:
    for c in candidates:
        print(f"\n--- {c} ---")
        for k, mb in all_keys(c)[:10]:
            print(f"    {k}  ({mb:.2f} MB)")
else:
    print("No obvious price library at the top of wrds/. Full listing:")
    for f in wrds_folders:
        print("  ", f)

# Also check whether options/SPY/ has a sibling folder besides tick/
print()
print("=" * 70)
print("OTHER FOLDERS UNDER options/SPY/")
print("=" * 70)
for f in folders("options/SPY/"):
    print("  ", f)

# ---------------------------------------------------------------
# 3. Profile one month of trades — how usable is it really?
# ---------------------------------------------------------------

print()
print("=" * 70)
print("LIQUIDITY PROFILE — one month of SPY trades")
print("=" * 70)

con = duckdb.connect()
con.execute("INSTALL httpfs; LOAD httpfs;")
con.execute(f"SET s3_endpoint='{ACCOUNT}.r2.cloudflarestorage.com'")
con.execute(f"SET s3_access_key_id='{KEY_ID}'")
con.execute(f"SET s3_secret_access_key='{SECRET}'")
con.execute("SET s3_region='auto'")
con.execute("SET s3_url_style='path'")

path = f"s3://{BUCKET}/options/SPY/tick/2015-01.parquet"

print("\nTrades per day:")
print(
    con.execute(f"""
    SELECT CAST(ts AS DATE) AS day,
           COUNT(*) AS trades,
           COUNT(DISTINCT osi) AS contracts_traded,
           SUM(size) AS volume
    FROM read_parquet('{path}')
    GROUP BY 1 ORDER BY 1 LIMIT 10
""").df().to_string(index=False)
)

print("\nHow many distinct expiries trade on a given day?")
print(
    con.execute(f"""
    SELECT CAST(ts AS DATE) AS day,
           COUNT(DISTINCT expiry) AS expiries,
           COUNT(DISTINCT strike) AS strikes
    FROM read_parquet('{path}')
    GROUP BY 1 ORDER BY 1 LIMIT 5
""").df().to_string(index=False)
)

print("\nStrike coverage for the nearest expiry on one day:")
print(
    con.execute(f"""
    SELECT strike, opt_type, COUNT(*) AS trades, MIN(price) AS lo, MAX(price) AS hi
    FROM read_parquet('{path}')
    WHERE CAST(ts AS DATE) = DATE '2015-01-15'
    GROUP BY 1, 2
    ORDER BY trades DESC
    LIMIT 20
""").df().to_string(index=False)
)

print()
print("Paste this output back.")