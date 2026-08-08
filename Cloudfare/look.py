"""
look.py — the simplest possible thing. Connect to the club's R2 storage
and print what's in there.

Run it with:   python look.py

If it prints a list of filenames, you're connected. That's the only
goal right now.
"""

import os

import boto3
from botocore.config import Config
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------
# Step 1: open the connection
# ---------------------------------------------------------------
# This is the "log in to the internet folder" step. The three odd-looking
# settings at the bottom are just quirks of Cloudflare — copy them and
# don't worry about why.

s3 = boto3.client(
    "s3",
    endpoint_url=f"https://{os.environ['R2_ACCOUNT_ID']}.r2.cloudflarestorage.com",
    aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
    aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],
    region_name="auto",
    config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
)

# ---------------------------------------------------------------
# Step 2: what folders exist?
# ---------------------------------------------------------------

print("=" * 60)
print("BUCKETS (the folders your login can see)")
print("=" * 60)

buckets = [b["Name"] for b in s3.list_buckets()["Buckets"]]

if not buckets:
    print("None. Your token may not have access to any buckets yet —")
    print("ask whoever runs QUANTT's Cloudflare account.")
    raise SystemExit

for name in buckets:
    print(" -", name)

# ---------------------------------------------------------------
# Step 3: what's inside the first folder?
# ---------------------------------------------------------------

bucket = buckets[0]

print()
print("=" * 60)
print(f"FILES INSIDE '{bucket}' (first 30)")
print("=" * 60)

response = s3.list_objects_v2(Bucket=bucket, MaxKeys=30)
files = response.get("Contents", [])

if not files:
    print("The bucket is empty.")
else:
    for obj in files:
        size_mb = obj["Size"] / 1_000_000
        print(f"  {obj['Key']:<60} {size_mb:>10.2f} MB")

    total = response.get("KeyCount", 0)
    print()
    print(f"Showing {len(files)} files.")
    if response.get("IsTruncated"):
        print("There are more than 30 — this is just the first page.")

print()
print("Done. If you saw filenames above, you are connected.")