# Hypothesis: <one falsifiable sentence>

written by Brandon Scheidler

| | |
|---|---|
| **Experiment** | 2026-11-11-Lowest-Fifth-Slope-Selling (same as the folder and `configs/experiments/<name>.toml`) |
| **Topic** | Risk Management |
| **Owner** | Brandon-Scheidler |
| **Status** | planned  |
| **Started** | 2026-11-11 |

## Hypothesis
Selling the book except when the slope is in the bottom 20% beats our current strategy

## Why it matters for the desk
Changes how and when we trade

## Data
- R2 Spy Option Snapshots
- **Hold-out:** from `YYYY-MM-DD` onward. Not used until the final run.

## Method
- Measure the IV on a slope

## Metric and pass bar
- Fixed bottom 20% buy

## If it passes
The concrete next step, e.g. "set `forecaster = "har"` in `configs/paper.toml` after shadow mode".

## Changes
- (dated notes, if the plan had to change)dd d
