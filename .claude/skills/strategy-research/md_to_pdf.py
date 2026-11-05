"""Convert strategy research markdown into Overleaf-basic-template LaTeX and compile to PDF.

Usage:
    venv/bin/python .claude/skills/strategy-research/md_to_pdf.py <report.md> [...] [--out DIR]

Writes <name>.tex and <name>.pdf into --out (default: the markdown file's folder).
The .tex compiles on Overleaf with the default pdflatex compiler. Locally it uses tectonic
(~/.local/bin/tectonic).
"""

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

TECTONIC = shutil.which("tectonic") or str(Path.home() / ".local/bin/tectonic")

PREAMBLE = r"""\documentclass{article}
\usepackage{graphicx} % Required for inserting images
\usepackage{float}
\usepackage[T1]{fontenc}
\usepackage{amsmath}
\usepackage[margin=1in]{geometry}
\usepackage{booktabs}
\usepackage{tabularx}
\usepackage[hidelinks]{hyperref}

\title{TITLE}
\author{AUTHOR}
\date{DATE}

\begin{document}

\maketitle
"""

UNICODE = {
    "–": "--", "—": "---", "·": r"\textperiodcentered{}", "…": r"\ldots{}",
    "−": r"\ensuremath{-}", "≈": r"\ensuremath{\approx}", "Δ": r"\ensuremath{\Delta}",
    "∆": r"\ensuremath{\Delta}", "Γ": r"\ensuremath{\Gamma}", "β": r"\ensuremath{\beta}",
    "σ": r"\ensuremath{\sigma}", "→": r"\ensuremath{\rightarrow}", "±": r"\ensuremath{\pm}",
    "×": r"\ensuremath{\times}", "≥": r"\ensuremath{\geq}", "≤": r"\ensuremath{\leq}",
    "½": r"\ensuremath{\frac12}", "λ": r"\ensuremath{\lambda}", "²": r"\textsuperscript{2}", "√": r"\ensuremath{\surd}", "Σ": r"\ensuremath{\Sigma}", "∫": r"\ensuremath{\int}", "Θ": r"\ensuremath{\Theta}", "ν": r"\ensuremath{\nu}", "∈": r"\ensuremath{\in}", "Ś": r"\'{S}", "ś": r"\'{s}", "Ł": r"\L{}", "ł": r"\l{}", "’": "'", "‘": "`", "“": "``", "”": "''",
}

SPECIAL = {"\\": r"\textbackslash{}", "&": r"\&", "%": r"\%", "$": r"\$", "#": r"\#",
           "_": r"\_", "{": r"\{", "}": r"\}", "~": r"\textasciitilde{}", "^": r"\textasciicircum{}"}


def escape(text):
    out = "".join(SPECIAL.get(ch, ch) for ch in text)
    out = "".join(UNICODE.get(ch, ch) for ch in out)
    return re.sub(r'"([^"]*)"', r"``\1''", out)


def code(text):
    return r"\texttt{" + re.sub(r"([/\-_.,])", r"\1\\allowbreak{}", text).replace(
        "_\\allowbreak", "\\_\\allowbreak") + "}"


def url(u):
    return u.replace("\\", "").replace("%", r"\%").replace("#", r"\#").replace("&", r"\&")


def is_math(s):
    if re.fullmatch(r"[A-Za-z]{1,2}", s):
        return True
    return bool(re.search(r"[\\^_]", s)) and "http" not in s and "](" not in s


def inline(text):
    tokens = []

    def keep(s):
        tokens.append(s)
        return f"\x00{len(tokens) - 1}\x00"

    text = re.sub(r"`([^`]+)`", lambda m: keep(code(escape(m.group(1)).replace(r"\_", "_"))), text)
    text = re.sub(r"\$(?!\d)([^$\n]{1,120}?)\$", lambda m: keep(f"${m.group(1)}$") if is_math(m.group(1)) else m.group(0), text)
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", lambda m: keep(link(m.group(1), m.group(2))), text)
    text = escape(text).replace("/", "/\\allowbreak{}")
    text = re.sub(r"\*\*(.+?)\*\*", r"\\textbf{\1}", text)
    text = re.sub(r"(?<![*\w])\*(?!\s)(.+?)(?<!\s)\*(?![*\w])", r"\\emph{\1}", text)
    return re.sub(r"\x00(\d+)\x00", lambda m: tokens[int(m.group(1))], text)


def link(label, target):
    if not re.match(r"[a-z]+://", target):
        target = re.sub(r"\.md$", ".pdf", target)
    return r"\href{" + url(target) + "}{" + inline(label) + "}"


def table(rows):
    cells = [[c.strip() for c in r.strip().strip("|").split("|")] for r in rows]
    head, body = cells[0], [r for r in cells[2:]]
    narrow = [max(len(r[i]) if i < len(r) else 0 for r in [head] + body) <= 12 for i in range(len(head))]
    if all(narrow):
        narrow[-1] = False
    spec = " ".join("l" if n else r">{\raggedright\arraybackslash}X" for n in narrow)
    lines = [r"\begin{center}\small", r"\begin{tabularx}{\linewidth}{" + spec + "}", r"\toprule",
             " & ".join(r"\textbf{" + inline(c) + "}" for c in head) + r" \\", r"\midrule"]
    lines += [" & ".join(inline(c) for c in r) + r" \\" for r in body]
    lines += [r"\bottomrule", r"\end{tabularx}", r"\end{center}"]
    return "\n".join(lines)


ITEM = re.compile(r"^(\s*)(-|\d+\.)\s+(.*)$")
IMAGE = re.compile(r"^!\[(.*)\]\((.+)\)$")


def figure(caption, path):
    # path is relative to the --out folder
    cap = r"\caption{" + inline(caption) + "}" if caption else ""
    return (r"\begin{figure}[H]\centering\includegraphics[width=0.92\linewidth]{" + path
            + "}" + cap + r"\end{figure}")


def body(lines):
    out, stack, para, quote = [], [], [], []

    def flush():
        if para:
            out.append(inline(" ".join(para)))
            para.clear()
        if quote:
            out.append(r"\begin{quote}" + inline(" ".join(quote)) + r"\end{quote}")
            quote.clear()

    def close_to(indent):
        while stack and stack[-1][1] > indent:
            flush()
            out.append(r"\end{" + stack.pop()[0] + "}")

    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        indent = len(line) - len(line.lstrip())
        if not stripped:
            flush()
            i += 1
            continue

        item = ITEM.match(line)
        image = IMAGE.match(stripped)
        if image:
            flush()
            close_to(-1)
            out.append(figure(image.group(1), image.group(2)))
        elif stripped.startswith("$$") and stripped.endswith("$$") and len(stripped) > 4:
            flush()
            out.append(r"\[" + stripped[2:-2].strip() + r"\]")
        elif stripped.startswith("#"):
            flush()
            close_to(-1)
            level = len(stripped) - len(stripped.lstrip("#"))
            title = re.sub(r"^\d+\.\s+", "", stripped.lstrip("#").strip())
            out.append({2: r"\section", 3: r"\subsection"}.get(level, r"\subsubsection")
                       + "{" + inline(title) + "}")
        elif stripped.startswith("|"):
            flush()
            close_to(indent)
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                rows.append(lines[i])
                i += 1
            out.append(table(rows))
            continue
        elif stripped == "---":
            flush()
        elif item:
            flush()
            env = "itemize" if item.group(2) == "-" else "enumerate"
            content_indent = indent + len(item.group(2)) + 1
            close_to(content_indent)
            if not stack or stack[-1][1] < content_indent or stack[-1][0] != env:
                if stack and stack[-1][1] == content_indent:
                    out.append(r"\end{" + stack.pop()[0] + "}")
                out.append(r"\begin{" + env + "}")
                stack.append((env, content_indent))
            out.append(r"\item " if not item.group(3).startswith(">") else r"\item")
            para.append(item.group(3))
        elif stripped.startswith(">"):
            if para:
                flush()
            close_to(indent)
            quote.append(stripped.lstrip(">").strip())
        else:
            if quote:
                flush()
            close_to(indent)
            para.append(stripped)
        i += 1

    flush()
    close_to(-1)
    return "\n\n".join(out).replace("\\item \n\n", "\\item ")


def header(lines):
    title = lines[0].lstrip("#").strip()
    meta = lines[1].strip().strip("*").split("·") if len(lines) > 1 else []
    meta = [m.strip() for m in meta]
    date = next((m for m in meta if re.match(r"\d{4}-\d{2}-\d{2}", m)), "")
    author = " \\textperiodcentered{} ".join(escape(m) for m in meta if m != date)
    return {"title": inline(title), "author": author, "date": date}, lines[2:]


def convert(md_path, out_dir):
    lines = Path(md_path).read_text().splitlines()
    meta, rest = header(lines)
    pre = PREAMBLE
    for k, v in meta.items():
        pre = pre.replace(k.upper() + "}", v + "}", 1)
    tex = pre + "\n" + body(rest) + "\n\n\\end{document}\n"
    tex_path = Path(out_dir) / (Path(md_path).stem + ".tex")
    tex_path.write_text(tex)
    return tex_path


def compile_pdf(tex_path):
    r = subprocess.run([TECTONIC, "--keep-logs", "-c", "minimal", tex_path.name],
                       cwd=tex_path.parent, capture_output=True, text=True)
    log = tex_path.with_suffix(".log")
    if r.returncode != 0:
        sys.exit(f"tectonic failed on {tex_path}:\n{r.stderr[-3000:]}")
    log.unlink(missing_ok=True)
    return tex_path.with_suffix(".pdf")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("md", nargs="+")
    p.add_argument("--out", default=None)
    a = p.parse_args()
    for md in a.md:
        tex = convert(md, a.out or Path(md).parent)
        print(f"{compile_pdf(tex)}")


if __name__ == "__main__":
    main()
