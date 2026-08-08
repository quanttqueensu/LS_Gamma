"""
final_check.py — verify the last three unknowns, then produce the first
genuinely useful output: one day of SPY option trades joined to spot,
with moneyness and DTE computed.

Checks:
  1. wrds/cboe_all/cboe.parquet          - is this VIX?
  2. wrds/frb_all/rates_daily.parquet    - Treasury curve?
  3. wrds/crsp_a_stock/dsf_v2.parquet    - does it cover 2025-2026?

Then:
  4. Joins SPY options for one day against the CRSP close and shows the
     moneyness / DTE distribution — the first real look at your data.

Run:   python final_check.py
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

con = duckdb.connect()
con.execute("INSTALL httpfs; LOAD httpfs;")
con.execute(f"SET s3_endpoint='{ACCOUNT}.r2.cloudflarestorage.com'")
con.execute(f"SET s3_access_key_id='{KEY_ID}'")
con.execute(f"SET s3_secret_access_key='{SECRET}'")
con.execute("SET s3_region='auto'")
con.execute("SET s3_url_style='path'")

S3 = f"s3://{BUCKET}"


def describe(path, label):
    print(f"\n--- {label} ---")
    try:
        df = con.execute(f"DESCRIBE SELECT * FROM read_parquet('{path}') LIMIT 0").df()
        print("    columns: " + ", ".join(df["column_name"].tolist()))
        return df["column_name"].tolist()
    except Exception as exc:
        print(f"    failed: {exc}")
        return []


def sample(path, label, n=5, order_col=None):
    try:
        order = f"ORDER BY {order_col} DESC" if order_col else ""
        df = con.execute(f"SELECT * FROM read_parquet('{path}') {order} LIMIT {n}").df()
        print(f"\n    {label} sample:")
        print(df.to_string(index=False))
    except Exception as exc:
        print(f"    sample failed: {exc}")


# ======================================================================
# 1. CBOE — is this VIX?
# ======================================================================

print("=" * 70)
print("1. wrds/cboe_all/cboe.parquet")
print("=" * 70)

cboe_path = f"{S3}/wrds/cboe_all/cboe.parquet"
cboe_cols = describe(cboe_path, "cboe.parquet")
if cboe_cols:
    sample(cboe_path, "cboe", n=5, order_col=cboe_cols[0])
    try:
        rng = con.execute(f"""
            SELECT MIN({cboe_cols[0]}) AS first, MAX({cboe_cols[0]}) AS last, COUNT(*) AS n
            FROM read_parquet('{cboe_path}')
        """).df()
        print("\n    coverage:")
        print(rng.to_string(index=False))
    except Exception as exc:
        print(f"    {exc}")

# ======================================================================
# 2. FRB rates — Treasury curve?
# ======================================================================

print()
print("=" * 70)
print("2. wrds/frb_all/rates_daily.parquet")
print("=" * 70)

rates_path = f"{S3}/wrds/frb_all/rates_daily.parquet"
rate_cols = describe(rates_path, "rates_daily.parquet")
if rate_cols:
    sample(rates_path, "rates_daily", n=3, order_col=rate_cols[0])

# ======================================================================
# 3. dsf_v2 — does it cover 2025-2026?
# ======================================================================

print()
print("=" * 70)
print("3. wrds/crsp_a_stock/dsf_v2.parquet — SPY coverage")
print("=" * 70)

dsf2 = f"{S3}/wrds/crsp_a_stock/dsf_v2.parquet"
try:
    cov = con.execute(f"""
        SELECT MIN(dlycaldt) AS first_day,
               MAX(dlycaldt) AS last_day,
               COUNT(*) AS n_days
        FROM read_parquet('{dsf2}')
        WHERE permno = 84398
    """).df()
    print(cov.to_string(index=False))

    print("\n    Most recent SPY rows (key columns):")
    recent = con.execute(f"""
        SELECT dlycaldt, ticker, dlyclose, dlyopen, dlyhigh, dlylow,
               dlybid, dlyask, dlyvol, dlyret, dlyretx, dlyorddivamt
        FROM read_parquet('{dsf2}')
        WHERE permno = 84398
        ORDER BY dlycaldt DESC
        LIMIT 5
    """).df()
    print(recent.to_string(index=False))

    print("\n    Recent SPY dividends (solves the BS dividend adjustment):")
    divs = con.execute(f"""
        SELECT dlycaldt, dlyorddivamt
        FROM read_parquet('{dsf2}')
        WHERE permno = 84398 AND dlyorddivamt > 0
        ORDER BY dlycaldt DESC
        LIMIT 8
    """).df()
    print(divs.to_string(index=False))
except Exception as exc:
    print(f"    failed: {exc}")

# ======================================================================
# 4. FIRST REAL OUTPUT — options joined to spot
# ======================================================================

print()
print("=" * 70)
print("4. FIRST REAL LOOK — SPY options on 2024-03-15, joined to spot")
print("=" * 70)

DAY = "2024-03-15"
MONTH_FILE = f"{S3}/options/SPY/tick/2024-03.parquet"

# Get that day's SPY close from CRSP
try:
    spot_df = con.execute(f"""
        SELECT ABS(prc) AS close
        FROM read_parquet('{S3}/wrds/crsp_a_stock/dsf.parquet')
        WHERE permno = 84398 AND date = DATE '{DAY}'
    """).df()
    spot = float(spot_df["close"][0])
    print(f"\nSPY close on {DAY}: ${spot:.2f}")
except Exception as exc:
    print(f"Could not get spot: {exc}")
    spot = None

if spot:
    # Aggregate trades to contract level for that day, compute moneyness + DTE
    print("\nMost-traded contracts that day, with moneyness and DTE:")
    q = f"""
        SELECT
            expiry,
            DATE_DIFF('day', DATE '{DAY}', expiry)        AS dte,
            strike,
            opt_type,
            ROUND(strike / {spot} - 1, 4)                 AS moneyness,
            COUNT(*)                                      AS trades,
            SUM(size)                                     AS volume,
            ROUND(SUM(price * size) / SUM(size), 3)       AS vwap
        FROM read_parquet('{MONTH_FILE}')
        WHERE CAST(ts AS DATE) = DATE '{DAY}'
          AND price >= 0.10
        GROUP BY 1, 2, 3, 4
        HAVING SUM(size) > 100
        ORDER BY volume DESC
        LIMIT 15
    """
    print(con.execute(q).df().to_string(index=False))

    # How many contracts sit in the strategy's target zone?
    print(f"\nContracts in your strategy's target zone (7-28 DTE):")
    q2 = f"""
        SELECT
            DATE_DIFF('day', DATE '{DAY}', expiry) AS dte,
            COUNT(DISTINCT strike)                 AS strikes,
            COUNT(*)                               AS trades,
            SUM(size)                              AS volume
        FROM read_parquet('{MONTH_FILE}')
        WHERE CAST(ts AS DATE) = DATE '{DAY}'
          AND price >= 0.10
          AND DATE_DIFF('day', DATE '{DAY}', expiry) BETWEEN 7 AND 28
        GROUP BY 1
        ORDER BY 1
    """
    print(con.execute(q2).df().to_string(index=False))

    # Liquidity at the 5% OTM wings your strangle would sell
    print(f"\nLiquidity at your ~5% OTM strangle wings:")
    q3 = f"""
        SELECT
            opt_type,
            strike,
            ROUND(strike / {spot} - 1, 3) AS moneyness,
            DATE_DIFF('day', DATE '{DAY}', expiry) AS dte,
            COUNT(*) AS trades,
            SUM(size) AS volume
        FROM read_parquet('{MONTH_FILE}')
        WHERE CAST(ts AS DATE) = DATE '{DAY}'
          AND price >= 0.10
          AND DATE_DIFF('day', DATE '{DAY}', expiry) BETWEEN 14 AND 21
          AND (
                (opt_type = 'P' AND strike / {spot} BETWEEN 0.94 AND 0.96)
             OR (opt_type = 'C' AND strike / {spot} BETWEEN 1.04 AND 1.06)
          )
        GROUP BY 1, 2, 3, 4
        ORDER BY opt_type, strike
    """
    print(con.execute(q3).df().to_string(index=False))

print()
print("=" * 70)
print("Paste this back — then we start building.")
print("=" * 70)