import csv
import os
import re
import subprocess
import tomllib
from datetime import date
from pathlib import Path

from markdown_it import MarkdownIt

REPO = Path(__file__).resolve().parents[3]
GITHUB = "https://github.com/quanttqueensu/LS_Gamma/blob/main/"
TOPICS = ["RV_Forecasting", "Deep_Hedging", "Agentic_Routing", "Risk_Management"]
VERDICTS = {"planned", "running", "passed", "failed", "inconclusive", "promoted"}
NUMERIC = {"spread_mult", "pnl", "sharpe", "max_dd", "es_5", "trades", "win_rate"}
FIRST = ["cum_pnl", "drawdown", "yearly", "fees", "by_reason"]
CAPTIONS = {"cum_pnl": "Cumulative P&L", "drawdown": "Drawdown", "yearly": "P&L by year",
            "fees": "Fees and costs", "by_reason": "P&L by exit reason"}
LIBRARY = [("research/strategy_research", "Literature report"),
           ("research/Misc_Research_Notes", "Research note"),
           ("research/general_research", "General research")]
BOILERPLATE = ("> Fill this card in", "> If you must change it")
DAY = re.compile(r"(\d{4}-\d{2}-\d{2})")
MONTHS = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]
MD = MarkdownIt("commonmark").enable("table")


def topic_label(topic):
    return topic.replace("_", " ")


def rel(path):
    return path.resolve().relative_to(REPO).as_posix()


def table(text):
    rows = re.findall(r"^\|\s*\*\*([^*]+)\*\*\s*\|\s*(.*?)\s*\|\s*$", text, re.M)
    return {k.strip().lower(): v for k, v in rows}


def split_status(text):
    word, _, rest = text.strip().partition(" ")
    rest = rest.strip()
    if rest.startswith("("):
        depth = 0
        for i, ch in enumerate(rest):
            depth += {"(": 1, ")": -1}.get(ch, 0)
            if depth == 0:
                tail = rest[i + 1:].lstrip(".;, ")
                rest = rest[1:i] + (". " + tail if tail else "")
                break
    return word.strip(".,;:").lower(), rest


def link(href, base, files):
    if re.match(r"^([a-z]+:|#)", href):
        return href
    path, _, frag = href.partition("#")
    target = Path(os.path.normpath(base / path))
    try:
        name = target.relative_to(REPO).as_posix()
    except ValueError:
        return href
    if target.suffix in (".pdf", ".png") and name.startswith("research/") and target.exists():
        files.add(name)
        return "files/" + name
    return GITHUB + name + ("#" + frag if frag else "")


def render(text, base, files):
    tokens = MD.parse(text)
    for tok in tokens:
        for child in tok.children or []:
            if child.type == "link_open":
                child.attrSet("href", link(child.attrGet("href"), base, files))
                child.attrSet("target", "_blank")
            if child.type == "image":
                child.attrSet("src", link(child.attrGet("src"), base, files))
    return MD.renderer.render(tokens, MD.options, {})


def strip(text):
    lines = text.splitlines()
    if lines and lines[0].startswith("# "):
        lines = lines[1:]
    return "\n".join(l for l in lines if not l.startswith(BOILERPLATE))


def caption(stem):
    return CAPTIONS.get(stem, stem.replace("_", " ").capitalize())


def figures(folder, files):
    pngs = sorted((folder / "figures").glob("*.png"))
    pngs.sort(key=lambda p: FIRST.index(p.stem) if p.stem in FIRST else len(FIRST))
    for p in pngs:
        files.add(rel(p))
    return [{"src": "files/" + rel(p), "caption": caption(p.stem)} for p in pngs]


def number(value):
    try:
        return float(value)
    except ValueError:
        return None


def load_registry(path):
    if not path.exists():
        return []
    with open(path, newline="") as f:
        return [{k: (number(v) if k in NUMERIC else v) for k, v in row.items()}
                for row in csv.DictReader(f)]



def stages(verdict, status, trials, report, summary):
    low = status.lower()
    return [True, bool(trials) or verdict != "planned", bool(report), bool(summary),
            any(t["holdout"] == "True" for t in trials), "shadow" in low,
            verdict == "promoted" or low.startswith("live")]


def card(folder, topic, registry, files):
    readme = (folder / "README.md").read_text()
    summary_path = folder / "summary.md"
    summary = summary_path.read_text() if summary_path.exists() else ""
    meta = table(readme)
    head = readme.splitlines()[0]
    title = re.sub(r"^#\s*(Hypothesis:\s*)?", "", head).strip()
    verdict, detail = split_status(meta.get("status", "planned"))
    if verdict not in VERDICTS:
        verdict, detail = "planned", meta.get("status", "")
    filled = re.search(r"\*\*Verdict:\*\*\s*(\S.*)", summary)
    filled = filled and not filled.group(1).startswith("passed /")
    finished = re.search(r"\*\*Date finished:\*\*\s*" + DAY.pattern, summary)
    started = DAY.search(meta.get("started", "")) or DAY.search(folder.name)
    pdf = folder / f"{folder.name}.pdf"
    report = None
    if pdf.exists():
        files.add(rel(pdf))
        report = "files/" + rel(pdf)
    trials = [r for r in registry if r["card"] == folder.name]
    return {
        "id": folder.name, "title": title[:1].upper() + title[1:], "topic": topic,
        "topicLabel": topic_label(topic), "owner": meta.get("owner", "").split(";")[0].strip(),
        "verdict": verdict, "detail": detail, "started": started.group(1),
        "finished": finished.group(1) if finished else None,
        "stages": stages(verdict, meta.get("status", ""), trials, report, filled),
        "trials": trials, "figures": figures(folder, files), "report": report,
        "cardHtml": render(strip(readme), folder, files),
        "summaryHtml": render(strip(summary), folder, files) if filled else None,
        "github": GITHUB.replace("/blob/", "/tree/") + rel(folder),
    }


def cards(root, registry, files):
    out = []
    for topic in TOPICS:
        for folder in sorted((root / "research" / topic).glob("20*-*")):
            if (folder / "README.md").exists():
                out.append(card(folder, topic, registry, files))
    return sorted(out, key=lambda c: (c["finished"] or c["started"], c["id"]), reverse=True)


def braced(text, start):
    depth = 0
    for i in range(start, len(text)):
        depth += {"{": 1, "}": -1}.get(text[i], 0)
        if depth == 0:
            return text[start + 1:i]
    return ""


def tex_title(path):
    text = path.read_text(errors="ignore")
    at = text.find("\\title{")
    if at < 0:
        return None
    t = braced(text, at + len("\\title"))
    t = t.replace("\\&", "&").replace("\\_", "_").replace("--", "–").replace("\\\\", " ")
    t = re.sub(r"\\[a-zA-Z]+\{\}|\\[a-zA-Z]+\s?", "", t)
    return re.sub(r"\s+", " ", t.replace("{", "").replace("}", "")).strip()


def library(root, files):
    out = []
    for folder, kind in LIBRARY:
        for pdf in sorted((root / folder).glob("*.pdf")):
            tex = pdf.with_suffix(".tex")
            day = DAY.match(pdf.name)
            title = tex_title(tex) if tex.exists() else None
            files.add(rel(pdf))
            out.append({"kind": kind, "title": title or pdf.stem[11:].replace("-", " ").capitalize(),
                        "date": day.group(1) if day else None, "href": "files/" + rel(pdf),
                        "note": "-notes-" in pdf.name})
    out.sort(key=lambda d: d["date"] or "", reverse=True)
    for pdf in sorted((root / "docs" / "papers").glob("*.pdf")):
        out.append({"kind": "Paper", "title": pdf.stem.replace("-", " "), "date": None,
                    "href": GITHUB + rel(pdf), "note": False})
    return out


def text_date(value):
    return value.isoformat() if isinstance(value, date) else (str(value) if value else None)


def roadmap(path, known, files):
    if not path.exists():
        return []
    with open(path, "rb") as f:
        items = tomllib.load(f).get("item", [])
    out = []
    for it in items:
        if it.get("card") in known:
            continue
        start, end = text_date(it.get("start")), text_date(it.get("end"))
        out.append({"title": it["title"], "tag": it.get("tag", "experiment"),
                    "topic": it.get("topic", "General"), "owner": it.get("owner", ""),
                    "start": start, "end": end or start, "status": it.get("status", "idea"),
                    "card": it.get("card", ""), "note": it.get("note", ""),
                    "link": link(it["link"], REPO, files) if it.get("link") else "",
                    "source": "roadmap"})
    return out


def timeline(cards, docs, plan):
    done = [{"title": c["title"], "short": c["id"][11:], "tag": "experiment", "topic": c["topic"],
             "owner": c["owner"], "start": c["started"], "end": c["finished"] or c["started"],
             "status": "done" if c["finished"] else "active", "verdict": c["verdict"], "card": c["id"],
             "link": "", "note": c["detail"], "source": "card"} for c in cards]
    reports = [{"title": d["title"], "tag": "paper" if d["kind"] == "Literature report" else "general",
                "topic": "General", "owner": "", "start": d["date"], "end": d["date"],
                "status": "done", "card": "", "link": d["href"], "note": d["kind"], "source": "library"}
               for d in docs if d["date"] and not d["note"]]
    return done + reports + plan


def owners(root):
    out = {}
    for topic in TOPICS:
        readme = root / "research" / topic / "README.md"
        text = readme.read_text() if readme.exists() else ""
        block = text.partition("## Who's working on it")[2].split("\n## ")[0]
        rows = re.findall(r"^\|([^|]*)\|([^|]*)\|", block, re.M)
        out[topic] = [(n.strip(), g.strip()) for n, g in rows
                      if n.strip() not in ("Name", "TBD") and not n.strip().startswith("-")]
    return out


def legacy_date(stem, today):
    m = re.search(r"(" + "|".join(MONTHS) + r")[a-z]*-?(\d{1,2})", stem.lower())
    try:
        day = date(today.year, MONTHS.index(m.group(1)) + 1, int(m.group(2))) if m else None
    except ValueError:
        return None
    return day and (day if day <= today else day.replace(year=day.year - 1)).isoformat()


def work_logs(root, folders, today):
    count, dates = 0, []
    for folder in folders:
        for md in sorted((root / folder).glob("*.md")):
            text = md.read_text(errors="ignore")
            if not text.strip():
                continue
            heads = re.findall(r"^## (\d{4}-\d{2}-\d{2})", text, re.M)
            count += len(heads) or 1
            dates += heads or [d for d in [legacy_date(md.stem, today)] if d]
    return count, max(dates) if dates else None


def team(root, cards, files):
    path = root / "research" / "team.toml"
    if not path.exists():
        return []
    with open(path, "rb") as f:
        members = tomllib.load(f).get("member", [])
    own, today, out = owners(root), date.today(), []
    for m in members:
        name, gh, logs = m["name"], m.get("github", ""), m.get("logs", [])
        count, last = work_logs(root, logs, today)
        photo = m.get("photo", "")
        if photo and (root / photo).exists():
            files.add(photo)
        out.append({"name": name, "role": m.get("role", "Analyst"), "github": gh,
                    "photo": "files/" + photo if photo in files else "",
                    "topics": [topic_label(t) for t, rows in own.items()
                               if any(n.startswith(name) or (gh and g.strip("`") == gh) for n, g in rows)],
                    "cards": sum(c["owner"].startswith(name) for c in cards),
                    "logs": count, "lastLog": last,
                    "logLink": GITHUB.replace("/blob/", "/tree/") + logs[0] if logs else ""})
    return out


def commit(root):
    sha = os.environ.get("GITHUB_SHA", "")[:7]
    if sha:
        return sha
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=root,
                              capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def collect(root=None):
    root = Path(root or REPO)
    files = set()
    registry = load_registry(root / "research" / "registry.csv")
    found = cards(root, registry, files)
    docs = library(root, files)
    plan = roadmap(root / "research" / "roadmap.toml", {c["id"] for c in found}, files)
    stats = {"cards": len(found), "trials": len(registry),
             "passed": sum(c["verdict"] in ("passed", "promoted") for c in found),
             "oos": sum(c["stages"][4] for c in found),
             "reports": sum(d["kind"] != "Paper" for d in docs) + sum(bool(c["report"]) for c in found),
             "papers": sum(d["kind"] == "Paper" for d in docs)}
    return {"cards": found, "library": docs, "timeline": timeline(found, docs, plan), "team": team(root, found, files),
            "topics": [[t, topic_label(t)] for t in TOPICS] + [["General", "General"]],
            "stats": stats, "build": {"commit": commit(root), "date": date.today().isoformat()},
            "repo": GITHUB.split("/blob/")[0], "files": sorted(files)}
