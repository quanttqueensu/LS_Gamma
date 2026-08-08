"""
check_inputs.py — verify the three non-options inputs your strategy needs.

  1. SPY daily prices  -> wrds/crsp_a_stock/dsf.parquet  (CRSP Daily Stock File)
  2. VIX               -> wrds/cboe_all/
  3. Risk-free rate    -> wrds/ff_all/ or wrds/frb_all/

dsf.parquet is 2.2 GB, but DuckDB filters over the network and only pulls
the row-groups and columns it needs, so this stays fast.

Run:   python check_inputs.py
"""

import os

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

pd.set_option("display.max_columns", None)
pd.set_option("display.width", 250)

s3 = boto3.client(
    "s3",
    endpoint_url=f"https://{ACCOUNT}.r2.cloudflarestorage.com",
    aws_access_key_id=KEY_ID,
    aws_secret_access_key=SECRET,
    region_name="auto",
    config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
)

con = duckdb.connect()
con.execute("INSTALL httpfs; LOAD httpfs;")
con.execute(f"SET s3_endpoint='{ACCOUNT}.r2.cloudflarestorage.com'")
con.execute(f"SET s3_access_key_id='{KEY_ID}'")
con.execute(f"SET s3_secret_access_key='{SECRET}'")
con.execute("SET s3_region='auto'")
con.execute("SET s3_url_style='path'")


def keys(prefix, limit=25):
    out = []
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=BUCKET, Prefix=prefix):
        for o in page.get("Contents", []):
            out.append((o["Key"], o["Size"] / 1_000_000))
            if len(out) >= limit:
                return out
    return out


def try_schema(path, label):
    print(f"\n--- {label} ---")
    print(f"    {path}")
    try:
        df = con.execute(f"DESCRIBE SELECT * FROM read_parquet('{path}') LIMIT 0").df()
        cols = df["column_name"].tolist()
        print(f"    {len(cols)} columns:")
        print("    " + ", ".join(cols))
        return cols
    except Exception as exc:
        print(f"    could not read: {exc}")
        return []


# ======================================================================
# 1. SPY daily prices from CRSP
# ======================================================================

print("=" * 70)
print("1. CRSP DAILY STOCK FILE — looking for SPY")
print("=" * 70)

dsf = f"s3://{BUCKET}/wrds/crsp_a_stock/dsf.parquet"
cols = try_schema(dsf, "dsf.parquet")

if cols:
    # CRSP identifies securities by PERMNO. SPY's PERMNO is 84398.
    # Column names are lowercase in most WRDS parquet exports.
    date_col = "date" if "date" in cols else ("dlycaldt" if "dlycaldt" in cols else None)
    permno_col = "permno" if "permno" in cols else None

    if permno_col and date_col:
        print("\n    Pulling SPY (PERMNO 84398), recent rows:")
        try:
            spy = con.execute(f"""
                SELECT * FROM read_parquet('{dsf}')
                WHERE {permno_col} = 84398
                ORDER BY {date_col} DESC
                LIMIT 5
            """).df()
            print(spy.to_string(index=False))

            rng = con.execute(f"""
                SELECT MIN({date_col}) AS first_day,
                       MAX({date_col}) AS last_day,
                       COUNT(*) AS n_days
                FROM read_parquet('{dsf}')
                WHERE {permno_col} = 84398
            """).df()
            print("\n    Coverage:")
            print(rng.to_string(index=False))
        except Exception as exc:
            print(f"    query failed: {exc}")
    else:
        print("\n    Could not find expected permno/date columns — see list above.")

# Also check dsf_v2, the newer CRSP format
print()
try_schema(f"s3://{BUCKET}/wrds/crsp_a_stock/dsf_v2.parquet", "dsf_v2.parquet (newer CRSP format)")

# ======================================================================
# 2. VIX from CBOE
# ======================================================================

print()
print("=" * 70)
print("2. CBOE LIBRARY — looking for VIX")
print("=" * 70)

for k, mb in keys("wrds/cboe_all/"):
    print(f"    {k}  ({mb:.2f} MB)")

cboe_files = [k for k, _ in keys("wrds/cboe_all/")]
for k in cboe_files:
    if any(h in k.lower() for h in ("vix", "index", "ivol", "hvol")):
        try_schema(f"s3://{BUCKET}/{k}", k.split("/")[-1])

# ======================================================================
# 3. Risk-free rate
# ======================================================================

print()
print("=" * 70)
print("3. RISK-FREE RATE — Fama-French and FRB")
print("=" * 70)

print("\nwrds/ff_all/ contents:")
for k, mb in keys("wrds/ff_all/", limit=15):
    print(f"    {k}  ({mb:.2f} MB)")

ff_files = [k for k, _ in keys("wrds/ff_all/", limit=15)]
for k in ff_files:
    if "factors_daily" in k.lower() or "daily" in k.lower():
        cols = try_schema(f"s3://{BUCKET}/{k}", k.split("/")[-1])
        if "rf" in [c.lower() for c in cols]:
            print("\n    Sample (rf is the daily risk-free rate):")
            try:
                print(con.execute(f"""
                    SELECT * FROM read_parquet('s3://{BUCKET}/{k}')
                    ORDER BY 1 DESC LIMIT 5
                """).df().to_string(index=False))
            except Exception as exc:
                print(f"    {exc}")
        break

print("\nwrds/frb_all/ contents:")
for k, mb in keys("wrds/frb_all/", limit=15):
    print(f"    {k}  ({mb:.2f} MB)")

print()
print("=" * 70)
print("Paste this output back.")
print("=" * 70)