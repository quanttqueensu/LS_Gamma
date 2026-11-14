# Card checklist

The card is `research/<Topic>/<YYYY-MM-DD-slug>/README.md`, copied from `research/_template/README.md`.
Every item must hold before any work starts. For each gap, quote the failing text and ask the questions listed.
Never write the answer for the analyst.

## 1. Template text is gone
Nothing from the template is left: `<one falsifiable sentence>`, `YYYY-MM-DD` (outside real dates), `e.g.`, `name (GitHub handle)`,
`planned / running / passed / failed / promoted`, "One sentence that can be proven wrong", "What changes in the live strategy
if this is true?", "Walk-forward settings", the example `forecaster = "har"` step, and "(dated notes, if the plan had to change)"
is fine to keep only while there are no changes.
- *Question:* "Which parts of the template haven't you replaced yet?"

## 2. Table
- **Experiment** = the folder name exactly; **Topic** = the parent folder name; **Owner** = the analyst; **Status** = planned;
  **Started** = a real date.
- *Question:* "What is the folder name, and which topic folder is it in?"

## 3. Hypothesis
One sentence that a backtest can prove wrong: it names the change, the comparison, and the direction ("X gives higher net P&L
than the current rules"). The `# Hypothesis:` title line is filled too.
- *Questions:* "What exactly changes compared with the current rules?" "Compared with what?" "Better how: P&L, Sharpe,
  drawdown, tail?" "What result would make you say it's wrong?"

## 4. Why it matters for the desk
What changes in the live strategy (`configs/paper.toml` or the traded book) if it is true. More than "changes how we trade".
- *Question:* "If this passes, which setting or rule would the desk change, and why would that make money or cut risk?"

## 5. Data
- R2 replay snapshots (the version in `configs/backtest.toml [history]`), development window **2014-06-02 to 2024-12-31**.
- Says the out-of-sample window (2025-01-01 to 2026-07-10) is **not used**.
- *Questions:* "Which window will you test on?" "Have you kept 2025-01-01 onward untouched?"

## 6. Method
- The variants: one **primary**, at most two sensitivity variants, each a concrete setting with a number
  (e.g. a band of 10 shares, a delta of 0.20), not a description like "use the slope".
- The **comparison**: the baseline (current `paper.toml` + `backtest.toml`) or a named reference variant.
- Every variant at **1x and 2x spreads** (the desk standard).
- Any signal or feature it uses must exist in, or be derivable from, the backtest data on completed days (no look-ahead).
- *Questions:* "What is the one setting you're changing, and to what value?" "How do you compute it each day, from which
  data?" "What will you compare it against?" "Do you want one or two sensitivity values around it?"

## 7. Metric and pass bar
- Named metrics (net P&L, Sharpe, max drawdown, ES 5%, or another `report.table` column) with a rule and number for each check.
- Each check holds at **both 1x and 2x**.
- P&L or Sharpe improvements hold over the **full window and in each half** (2014-06..2019-12, 2020-01..2024-12).
- A **tail guard**: |ES 5%| within 1.10x of the comparison, unless ES is the target.
- An **event floor** with a reason: the minimum number of times the mechanism must fire (e.g. 30 stops), else INCONCLUSIVE.
- Says which variant the bar judges, and that the others cannot change the verdict.
- *Questions:* "What number would convince you it's better?" "Does it still hold at 2x spreads?" "In both halves, or only
  overall?" "How bad can the worst days get before you'd reject it?" "How many times must it fire for the result to mean anything?"

## 8. In-sample note
If the idea came from earlier results on 2014-2024 (another card, a backtest, the paper account), the card says so.
- *Question:* "Where did the idea come from? Did you see it in an earlier result on the same years?"

## 9. If it passes
The next step: out-of-sample confirmation (run by the PM), then shadow mode, then the one-line change it would make.
- *Question:* "If it passes, what would you ask the PM to change?"

## 10. Changes
Present (may be empty).
