import sys
import pandas as pd
from surface_plot import load_smiles

s = load_smiles("Data/data")
date = sys.argv[1] if len(sys.argv) > 1 else s["date"].max()

day = s[s["date"] == pd.Timestamp(date)].sort_values("dte")
print(f"{pd.Timestamp(date).date()}  {len(day)} fitted expiries\n")
print(day[["dte","atm_iv","p1","p2","n_points","rmse","k_min","k_max"]].round(4).to_string(index=False))

day = day.copy()
day["atm_jump"] = day["atm_iv"].diff().abs()
bad = day[day["atm_jump"] > 0.03]
if len(bad):
    print(f"\n{len(bad)} expiry(s) jump more than 3 vol points from the previous tenor:")
    print(bad[["dte","atm_iv","n_points","rmse"]].round(4).to_string(index=False))