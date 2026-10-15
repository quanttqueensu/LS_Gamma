# 0001. Main stays the trunk; live versions are tagged
*Date: 2026-10-15 · Status: Accepted*

**Context:** Research and backtests need to stay separate from what the paper bot runs. We considered renaming `main` to `prod` and adding a long-lived backtest branch.

**Decision:** `main` stays the protected trunk: changes go through PRs, and the PM is the CODEOWNER for `configs/paper.toml`, `core/Algos/` and `trading/runner.py`. Each version the paper bot runs is tagged `live-YYYY-MM-DD`. Research happens on short-lived branches and experiment TOMLs, not on a separate branch.

**Evidence:**
- A long-lived backtest branch drifts from live code, so its results would test code that doesn't trade (research/README.md rule: import desk code, don't copy it).
- Live and backtest are separated by entry point and config: `trading.runner` + `paper.toml` vs `backtest.run` + `configs/experiments/<name>.toml`.

**Consequences:** The PM sets up GitHub branch protection and CODEOWNERS. Changing an experiment config can't touch the paper account.
