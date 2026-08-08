"""
explore.py — show the FOLDER layout of the bucket, not a wall of files.

Run:   python explore.py

The previous script listed files alphabetically, so '_recycle_bin' hogged
the whole page. This one asks Cloudflare for folders instead, which gives
you the map in one screen.
"""

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
    config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
)

BUCKET = "quantt-historical-market-data"


def folders(prefix=""):
    """List folder names directly under a prefix.

    The Delimiter='/' argument is the trick: it tells Cloudflare to group
    keys by their next '/' and return the groups instead of every file.
    """
    out = []
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=BUCKET, Prefix=prefix, Delimiter="/"):
        for p in page.get("CommonPrefixes", []):
            out.append(p["Prefix"])
    return out


def files_in(prefix, limit=15):
    """List a few files directly inside a prefix."""
    resp = s3.list_objects_v2(Bucket=BUCKET, Prefix=prefix, Delimiter="/", MaxKeys=limit)
    return [(o["Key"], o["Size"] / 1_000_000) for o in resp.get("Contents", [])]


print("=" * 70)
print("TOP-LEVEL FOLDERS")
print("=" * 70)

top = folders()
if not top:
    print("No folders — files sit at the root.")
for f in top:
    print(" ", f)

# ---------------------------------------------------------------
# Look for anything options-related. In WRDS, OptionMetrics lives
# under a library called 'optionm'. CBOE data lives under 'cboe'.
# ---------------------------------------------------------------

print()
print("=" * 70)
print("FOLDERS THAT LOOK OPTIONS-RELATED")
print("=" * 70)

keywords = ("option", "optionm", "ivy", "cboe", "vol", "spx", "spy", "index", "crsp")
hits = [f for f in top if any(k in f.lower() for k in keywords)]

if not hits:
    print("Nothing obvious at the top level.")
    print("Look through the full list above — WRDS library names are cryptic.")
else:
    for f in hits:
        print(f"\n--- {f} ---")
        sub = folders(f)
        if sub:
            for s in sub:
                print("    folder:", s)
        for key, mb in files_in(f):
            print(f"    file:   {key}  ({mb:.2f} MB)")

print()
print("=" * 70)
print("Paste this output back and we'll find the SPY options data.")
print("=" * 70)