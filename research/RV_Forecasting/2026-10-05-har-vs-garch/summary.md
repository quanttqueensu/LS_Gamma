# Summary: 2026-10-05-har-vs-garch

> Sample summary for the worked example, written during setup to show the format. Your own summaries should be written by you, in your own words.

**Owner:** setup example · **Date finished:** 2026-10-02 · **Verdict:** failed

## Result
HAR didn't beat GARCH. GARCH had the lower QLIKE overall (0.593 vs 0.636) and in 6 of the 7 yearly folds. HAR only won 2022. The pass bar needed HAR to win overall and in at least 5 folds, so this fails. We keep GARCH live.

## Trials
One run, no changes between runs. It covered 297 forecasts, every 5th trading day from 2019 to 2025, with the hold-out untouched.

## What surprised you
HAR wasn't just a bit worse, it forecast too high. Its median forecast was 17.2% vol against 13.8% realized (GARCH: 15.5%). Its average was much worse, because after big shocks like 2020 it stayed elevated for too long. Both models overshot in calm years like 2019 and 2023.

## Caveats
- Our HAR is fit on daily **squared returns**, which are very noisy. HAR was designed for cleaner realized variance built from intraday data, so this isn't a fair test of HAR itself, just of our current version.
- 2020 dominates the losses for both models.
- Forecast windows overlap (20 days ahead, every 5 days), so the 297 forecasts are far from 297 independent tests.

## Next step
Archive this one and try a follow-up: HAR fit on Garman-Klass RV (already in `pipeline/features.py`) instead of squared returns. Until then, nobody should switch the live forecaster to `har`.
