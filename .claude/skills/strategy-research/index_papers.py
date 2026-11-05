"""Build a page-tagged text index of every PDF in docs/papers.

Each paper becomes .claude/research/index/<name>.txt where every line starts with
its PDF page number, e.g. "[p12] Deep hedging minimises ...", so grep shows pages.
Only papers that are new or changed since the last run are re-extracted.

Run: venv/bin/python .claude/skills/strategy-research/index_papers.py
"""

from pathlib import Path

from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[3]
PAPERS = ROOT / "docs" / "papers"
INDEX = ROOT / ".claude" / "research" / "index"

# Some PDFs (e.g. the PIER paper) encode ligatures as control characters
LIGATURES = {"\x1b": "ff", "\x1c": "fi", "\x1d": "fl", "\x1e": "ffi", "\x1f": "ffl",
             "ﬀ": "ff", "ﬁ": "fi", "ﬂ": "fl", "ﬃ": "ffi", "ﬄ": "ffl"}


def clean(text):
    for k, v in LIGATURES.items():
        text = text.replace(k, v)
    return text


def extract(pdf, out):
    reader = PdfReader(pdf)
    lines = []
    for n, page in enumerate(reader.pages, start=1):
        text = clean(page.extract_text() or "")
        lines += [f"[p{n}] {line}" for line in text.splitlines() if line.strip()]
    out.write_text("\n".join(lines), encoding="utf-8")
    return reader


def title_of(reader, txt):
    meta = (reader.metadata or {}).get("/Title") if reader else None
    if meta and len(meta.strip()) > 8:
        return meta.strip()
    first = [l[5:].strip() for l in txt.read_text(encoding="utf-8").splitlines()[:8] if l.startswith("[p1]")]
    return " ".join(first[:2])[:150]


def main():
    INDEX.mkdir(parents=True, exist_ok=True)
    rows = []
    for pdf in sorted(PAPERS.glob("*.pdf")):
        txt = INDEX / f"{pdf.stem}.txt"
        reader = None
        if not txt.exists() or txt.stat().st_mtime < pdf.stat().st_mtime:
            try:
                reader = extract(pdf, txt)
                print(f"indexed  {pdf.name}")
            except Exception as e:
                print(f"FAILED   {pdf.name}: {e}")
                continue
        pages = txt.read_text(encoding="utf-8").rsplit("[p", 1)[-1].split("]", 1)[0]
        chars = txt.stat().st_size
        rows.append(f"| {pdf.name} | {title_of(reader, txt)} | {pages} | {'LOW TEXT - scanned?' if chars < 2000 else ''} |")

    names = {pdf.stem for pdf in PAPERS.glob("*.pdf")}
    for txt in INDEX.glob("*.txt"):
        if txt.stem not in names:
            txt.unlink()
            print(f"removed  {txt.name} (no matching PDF)")

    catalog = ["| File | Title (from PDF) | Pages | Note |", "|---|---|---|---|", *rows]
    (INDEX.parent / "catalog.md").write_text("\n".join(catalog) + "\n", encoding="utf-8")
    print(f"\n{len(rows)} papers in {INDEX.parent / 'catalog.md'}")


if __name__ == "__main__":
    main()
