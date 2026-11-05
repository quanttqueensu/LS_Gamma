---
name: strategy-research
description: Research a strategy question across every paper in docs/papers plus the web, and answer with verbatim quotes, exact page references, and the connections between papers. Saves every report as a compiled PDF (Overleaf basic LaTeX template, .tex + .pdf) in research/strategy_research/. Use when the user asks to investigate, research, or compare approaches (e.g. "how can RL be used to hedge delta", "what do the papers say about VRP forecasting").
---

# Strategy research

Goal: a sourced answer the PM can trust and hand to analysts. Every claim from a paper
has a verbatim quote and a page. Never fabricate a quote, page, author, or result.

## 1. Scope the question
If the question is vague, ask ONE clarifying question (e.g. which part: state design,
reward, results vs delta hedging?). Otherwise start. Write down 5-15 search terms,
including synonyms (e.g. RL: "reinforcement learning", "policy", "reward", "Q-learning",
"actor-critic", "PPO", "DDPG", "Bellman", "agent"; hedging: "hedge", "delta", "replicat",
"transaction cost", "P&L", "CVaR", "risk measure").

## 2. Refresh the index (fast; only new/changed PDFs are re-extracted)
```bash
venv/bin/python .claude/skills/strategy-research/index_papers.py
```
- `.claude/research/catalog.md` lists every paper: file, title, page count. Read it first;
  titles there come from the PDF and can be junk (journal headers); check page 1 if unsure.
- **Name papers by title.** If a PDF in `docs/papers/` has a non-descriptive name (arXiv id,
  `1-s2.0-...-main.pdf`, spaces), rename it to its printed title in the existing format:
  words joined by `-`, colons dropped, e.g. `Clustering-Market-Regimes-Using-the-Wasserstein-Distance.pdf`.
  Use `git mv` if tracked. Then update citations in `.claude/research/drafts/*.md` and rebuild
  the affected reports with `md_to_pdf.py`.
- `.claude/research/index/<paper>.txt` has one line per text line, prefixed `[pN]` =
  PDF page N (1-based, as shown in a PDF viewer's page counter).
- Requires `pypdf` in the venv (`venv/bin/pip install pypdf`).

## 3. Search the papers
- **Use `/usr/bin/grep -a`**, not `grep`: in this shell `grep` is a wrapper function that
  returns wrong counts, and some index files contain bytes that make grep say "Binary file
  matches" without `-a`. In zsh, define `g(){ /usr/bin/grep -a "$@"; }` rather than a variable.
- Rank papers by hits: `/usr/bin/grep -aic "<term>" .claude/research/index/*.txt | sort -t: -k2 -nr`
- Find passages: `grep -in "<term>" .claude/research/index/<paper>.txt`
- Read context around a hit: `sed -n '<line-10>,<line+15>p' .claude/research/index/<paper>.txt`
- Always read each relevant paper's abstract/introduction (pages 1-2) and conclusion to
  get its actual contribution, not just keyword hits.
- Cover every paper with meaningful hits. Say explicitly which papers were checked and
  had nothing relevant.

## 4. Verify quotes
- Quote text exactly as it appears. Extracted text can break words across lines and
  garble math/symbols. For every quote you present, confirm it on the page with the Read
  tool (`file_path` = the PDF, `pages: "N"`) and fix spacing/hyphenation to match the PDF.
- If the Read tool can't render PDFs (poppler/pdftoppm not installed), verify instead by
  re-extracting that page with pypdf and checking the quote is a substring after removing
  whitespace/hyphens and normalizing ligatures (ﬁ→fi, ﬀ→ff) and curly quotes. Batch all
  quotes in one script and only present quotes that print OK. Also map control-character
  ligatures some PDFs use: `\x1b`→ff, `\x1c`→fi, `\x1d`→fl, `\x1e`→ffi, `\x1f`→ffl
  (the index script already applies this via `LIGATURES`; import it rather than retyping).
- Printed page numbers: look for a line that is just a number on that page
  (`/usr/bin/grep -a -E "^\[pN\] [0-9]+$"`); arXiv preprints often run one lower than the PDF page.
- If the paper's printed page number differs from the PDF page, cite both:
  `p. 7 (printed p. 145)`.
- Equations: describe them or reproduce them in LaTeX from the PDF view, not from the
  extracted text.

## 5. Search the web
- Use WebSearch for relevant work NOT in the repo: newer papers, well-cited foundations,
  practical implementations (arXiv, SSRN, journals, reputable practitioner sources).
- Use WebFetch on abstracts/pages to confirm what a source says before citing it.
- Web claims get a link, not a page number. Label them clearly as outside the repo.
- List the best 2-5 papers worth adding to `docs/papers/`, with one line on why.

## 6. Write the answer
Use this structure:

```
## Short answer
3-6 sentences answering the question directly.

## What the papers say
### <Theme 1, e.g. How the RL problem is set up>
- Claim in your own words.
  > "verbatim quote" (Author(s) Year, *Short Title*, p. N)
...

## How the papers connect
| Paper | Builds on / agrees with | Differs from | Key contribution |
Then 2-5 bullets on agreements, disagreements, and lineage (who extends whom).

## Relevance to the LS Gamma desk
Only what follows from confirmed facts about the desk (see .claude/CLAUDE.md).
Mark suggestions as suggestions. Don't assume thresholds/structures the PM hasn't set.

## Gaps and open questions
What the papers don't answer, conflicting results, assumptions that may not hold for
SPY options with IBKR execution.

## Sources
- Repo papers used (file name, title, pages cited)
- Repo papers checked with nothing relevant
- Web sources (linked)
- Suggested papers to add
```

## Rules
- Distinguish clearly: what a paper states vs your inference vs a web source.
- Prefer fewer, strong quotes over many weak ones; 1-3 per important claim.
- Author names and years come from the paper's first page; if not found, use the title.
- If the papers don't cover the question, say so plainly and rely on the web section.
- Answer in the chat AND always record the report (step 7).

## 7. Record the report
Every report is saved as LaTeX (Overleaf basic template) plus its compiled PDF in
`research/strategy_research/YYYY-MM-DD-<short-kebab-topic>.{tex,pdf}`. This folder is
committed and shared with the analysts. No `.md` file goes in that folder.

1. Write the draft in markdown to `.claude/research/drafts/YYYY-MM-DD-<topic>.md`, starting with:
```
# <Question rephrased as a title>
*Strategy research · YYYY-MM-DD · L/S Gamma Desk, QUANTT*

**Question:** <the user's question, verbatim>

**Method:** Searched all N papers in `docs/papers/` (page-tagged index) + web search.
Quotes verified against the cited PDF pages. Page numbers are PDF pages; printed page
numbers are given where they differ.

---
```
   then the full answer from step 6.
2. Convert and compile:
   `venv/bin/python .claude/skills/strategy-research/md_to_pdf.py .claude/research/drafts/<file>.md --out research/strategy_research`
   - Line 1 becomes `\title`, the `*... · date · ...*` line becomes `\author` and `\date`.
   - `##` becomes `\section`, `###` becomes `\subsection` (leading "1. " numbering is stripped).
   - Lists, `>` quotes, tables (tabularx + booktabs), `**bold**`, `*italic*`, `` `code` ``, links and
     `$\latex$` math are converted. Unicode (–, −, Δ, ≈, accents) is mapped so the .tex compiles
     with pdflatex on Overleaf too.
   - Links to other reports use the `.pdf` name, e.g. `[Size and exit rules](2026-10-01-position-size-and-exit-rules.pdf)`.
   - Compiles with tectonic (`~/.local/bin/tectonic`); the first run downloads packages.
3. Check the result: `sips -s format png <file>.pdf --out <scratchpad>/p1.png`, then Read the PNG
   (first page only; split pages with pypdf for tables). Fix anything broken in the draft and rerun.
- Keep repo-paper references as file names in `docs/papers/` so analysts can open them.
- Don't include anything private (`.env`, R2 credentials, `.claude/` paths other than
  describing the method).
- If the same topic was researched before, read the earlier report first (the `.tex` is the
  readable source); create a new dated report and link the earlier `.pdf` under a
  `**Previous research:**` line in the header.
- Tell the user the PDF path. Don't commit it (use `/commit` if they ask).
