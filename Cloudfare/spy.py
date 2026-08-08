"""
spy.py — look inside options/SPY/ and find out what the data actually is.

Run:   python spy.py

Two parts:
  1. boto3 shows how the folder is organised (by year? by month? one file?)
  2. DuckDB reads the column names and a few sample rows from one file,
     WITHOUT downloading the whole thing.

Needs duckdb:   pip install duckdb
"""

import os

import boto3
import duckdb
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

# ---------------------------------------------------------------
# Part 1 — how is options/SPY/ organised?
# ---------------------------------------------------------------

print("=" * 70)
print("STRUCTURE OF options/SPY/")
print("=" * 70)


def folders(prefix):
    out = []
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=BUCKET, Prefix=prefix, Delimiter="/"):
        for p in page.get("CommonPrefixes", []):
            out.append(p["Prefix"])
    return out


def files(prefix, limit=20):
    resp = s3.list_objects_v2(Bucket=BUCKET, Prefix=prefix, Delimiter="/", MaxKeys=limit)
    return [(o["Key"], o["Size"] / 1_000_000) for o in resp.get("Contents", [])]


subfolders = folders("options/SPY/")
direct_files = files("options/SPY/")

if subfolders:
    print(f"Subfolders ({len(subfolders)}):")
    for f in subfolders[:20]:
        print("   ", f)
    if len(subfolders) > 20:
        print(f"    ... and {len(subfolders) - 20} more")

if direct_files:
    print(f"\nFiles directly inside ({len(direct_files)} shown):")
    for k, mb in direct_files:
        print(f"    {k}  ({mb:.2f} MB)")

# Find one actual parquet file to inspect, going one level deeper if needed.
sample_key = None
for k, _ in direct_files:
    if k.endswith(".parquet"):
        sample_key = k
        break

if not sample_key and subfolders:
    print(f"\nLooking inside {subfolders[0]} ...")
    for k, mb in files(subfolders[0]):
        print(f"    {k}  ({mb:.2f} MB)")
        if k.endswith(".parquet") and not sample_key:
            sample_key = k

if not sample_key:
    print("\nNo .parquet file found yet — paste this output and we'll dig further.")
    raise SystemExit

# ---------------------------------------------------------------
# Part 2 — what columns does it have?
# ---------------------------------------------------------------

print()
print("=" * 70)
print(f"COLUMNS IN {sample_key}")
print("=" * 70)

con = duckdb.connect()
con.execute("INSTALL httpfs; LOAD httpfs;")
con.execute(f"SET s3_endpoint='{ACCOUNT}.r2.cloudflarestorage.com'")
con.execute(f"SET s3_access_key_id='{KEY_ID}'")
con.execute(f"SET s3_secret_access_key='{SECRET}'")
con.execute("SET s3_region='auto'")
con.execute("SET s3_url_style='path'")

path = f"s3://{BUCKET}/{sample_key}"

schema = con.execute(f"DESCRIBE SELECT * FROM read_parquet('{path}') LIMIT 0").df()
print(schema[["column_name", "column_type"]].to_string(index=False))

print()
print("=" * 70)
print("SAMPLE ROWS")
print("=" * 70)

import pandas as pd

pd.set_option("display.max_columns", None)
pd.set_option("display.width", 250)

sample = con.execute(f"SELECT * FROM read_parquet('{path}') LIMIT 5").df()
print(sample.to_string(index=False))

print()
print("=" * 70)
print("ROW COUNT")
print("=" * 70)
count = con.execute(f"SELECT COUNT(*) AS n FROM read_parquet('{path}')").df()
print(f"{int(count['n'][0]):,} rows in this file")

print()
print("Paste all of this back and we'll write your first real query.")