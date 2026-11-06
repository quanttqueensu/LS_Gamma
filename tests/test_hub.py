import json
from datetime import date

import pandas as pd
import pytest

pytest.importorskip("markdown_it")

from lsgamma import experiments
from lsgamma.hub import build, collect, desk, export
from lsgamma.trading import config, ledger

CARD = """# Hypothesis: a demo rule beats the baseline

> Fill this card in **before** running anything. Don't change the pass bar after you've seen results.

| | |
|---|---|
| **Experiment** | `2026-11-01-demo` |
| **Topic** | Agentic_Routing |
| **Owner** | Jane Doe (jdoe); run by Claude |
| **Status** | passed (in-sample; hold-out not run). +$5k |
| **Started** | 2026-11-01 |

## Hypothesis
See the [report](2026-11-01-demo.pdf) and [paper](../../../docs/papers/X.pdf).
"""
SUMMARY = ("# Summary: 2026-11-01-demo\n\n> Written by Claude at the PM's request (an exception).\n"
           "> Only aggregate numbers here.\n\n"
           "**Owner:** Jane; run by Claude at the PM's request · **Date finished:** 2026-11-03 · **Verdict:** passed\n")
ROADMAP = """
[[item]]
title = "An idea"
tag = "paper"
topic = "RV_Forecasting"

[[item]]
title = "Scheduled"
start = 2026-11-10
end = 2026-11-14
status = "next"

[[item]]
title = "Already carded"
card = "2026-11-01-demo"
"""


@pytest.fixture
def repo(tmp_path, monkeypatch):
    monkeypatch.setattr(collect, "REPO", tmp_path)
    card = tmp_path / "research" / "Agentic_Routing" / "2026-11-01-demo"
    (card / "figures").mkdir(parents=True)
    (card / "README.md").write_text(CARD)
    (card / "summary.md").write_text(SUMMARY)
    (card / "figures" / "drawdown.png").write_bytes(b"png")
    (card / "figures" / "cum_pnl.png").write_bytes(b"png")
    (card / "2026-11-01-demo.pdf").write_bytes(b"%PDF")
    (tmp_path / "research" / "roadmap.toml").write_text(ROADMAP)
    (tmp_path / "research" / "registry.csv").write_text(
        "card,variant,run,commit,start,end,holdout,spread_mult,pnl,sharpe,max_dd,es_5,trades,win_rate\n"
        "2026-11-01-demo,a,20261101-1,abc,2014-06-02,2024-12-31,False,1.0,100.5,0.5,10,-2,5,0.6\n"
        "2026-11-01-demo,a,20261101-2,abc,2014-06-02,2024-12-31,False,2.0,,,,,,\n")
    lit = tmp_path / "research" / "strategy_research"
    lit.mkdir()
    (lit / "2026-09-27-topic.pdf").write_bytes(b"%PDF")
    (lit / "2026-09-27-topic.tex").write_text("\\title{Deep Hedging \\& the \\allowbreak{}Desk}")
    return tmp_path


def test_split_status():
    assert collect.split_status("failed") == ("failed", "")
    assert collect.split_status("passed (in-sample; x (y)). +$5k") == ("passed", "in-sample; x (y). +$5k")


def test_collect_card(repo):
    data = collect.collect()
    card = data["cards"][0]
    assert card["title"] == "A demo rule beats the baseline"
    assert card["verdict"] == "passed" and card["detail"] == "in-sample; hold-out not run. +$5k"
    assert card["owner"] == "Jane Doe (jdoe)"
    assert (card["started"], card["finished"]) == ("2026-11-01", "2026-11-03")
    assert card["stages"] == [True, True, True, True, False, False, False]
    assert [f["caption"] for f in card["figures"]] == ["Cumulative P&L", "Drawdown"]
    assert card["trials"][0]["pnl"] == 100.5 and card["trials"][1]["pnl"] is None
    assert 'href="files/research/Agentic_Routing/2026-11-01-demo/2026-11-01-demo.pdf"' in card["cardHtml"]
    assert collect.GITHUB + "docs/papers/X.pdf" in card["cardHtml"]
    assert "Fill this card" not in card["cardHtml"]
    assert "by Claude" not in card["summaryHtml"] and "aggregate numbers" not in card["summaryHtml"]
    assert data["library"][0]["title"] == "Deep Hedging & the Desk"
    assert data["stats"]["trials"] == 2 and data["stats"]["passed"] == 1


def test_team(repo):
    (repo / "research" / "team.toml").write_text(
        '[[member]]\nname = "Jane Doe"\nrole = "Analyst"\ngithub = "jdoe"\nlinkedin = "https://www.linkedin.com/in/jdoe/"\n'
        'photo = "research/team/jane.jpg"\n'
        'logs = ["work-logs/jane", "work-logs/old"]\n\n[[member]]\nname = "Sam Roe"\nrole = "PM"\n')
    (repo / "research" / "team").mkdir()
    (repo / "research" / "team" / "jane.jpg").write_bytes(b"jpg")
    for folder, name, text in [("jane", "2026-11.md", "# Jane\n\n## 2026-11-02 10:00 · x\n\n## 2026-11-04 09:00 · y\n"),
                               ("old", "worklog1-oct21.md", "first meeting"), ("old", "empty.md", "")]:
        (repo / "work-logs" / folder).mkdir(parents=True, exist_ok=True)
        (repo / "work-logs" / folder / name).write_text(text)
    data = collect.collect()
    jane, sam = data["team"]
    assert jane["cards"] == 1 and "topics" not in jane
    assert jane["linkedin"] == "https://www.linkedin.com/in/jdoe/" and sam["linkedin"] == ""
    assert (jane["logs"], jane["lastLog"]) == (3, "2026-11-04")
    assert jane["photo"] == "files/research/team/jane.jpg" and "research/team/jane.jpg" in data["files"]
    assert (sam["role"], sam["photo"], sam["logs"]) == ("PM", "", 0)
    assert collect.legacy_date("worklog1-oct21", collect.date(2026, 11, 5)) == "2026-10-21"


def test_roadmap_ideas_and_cards(repo):
    timeline = collect.collect()["timeline"]
    plan = [t for t in timeline if t["source"] == "roadmap"]
    assert [t["title"] for t in plan] == ["An idea", "Scheduled"]
    assert plan[0]["start"] is None and plan[0]["tag"] == "paper"
    assert (plan[1]["start"], plan[1]["end"], plan[1]["topic"]) == ("2026-11-10", "2026-11-14", "General")
    done = [t for t in timeline if t["source"] == "card"][0]
    assert (done["start"], done["end"], done["status"]) == ("2026-11-01", "2026-11-03", "done")


def test_build_writes_site(repo, tmp_path_factory):
    out = tmp_path_factory.mktemp("site") / "_site"
    build.build(out, root=repo)
    page = (out / "index.html").read_text()
    blob = page.split('id="hub-data">')[1].split("</script>")[0]
    assert json.loads(blob)["stats"]["cards"] == 1
    assert (out / "files/research/Agentic_Routing/2026-11-01-demo/figures/cum_pnl.png").exists()
    assert (out / "files/research/strategy_research/2026-09-27-topic.pdf").exists()
    build.build(out, root=repo)
    other = tmp_path_factory.mktemp("other")
    (other / "keep.txt").write_text("x")
    with pytest.raises(SystemExit):
        build.build(other, root=repo)
    assert (other / "keep.txt").exists()


def test_export_adds_folder_runs(tmp_path, monkeypatch):
    monkeypatch.setattr(experiments, "ROOT", tmp_path)
    pd.DataFrame({"experiment": ["2026-11-01-demo/a", "baseline"], "run": ["2026-11-01-demo/a/20261101-120000", "baseline/20261015-233601"],
                  "commit": ["abc", "def"], "start": "2014-06-02", "end": "2024-12-31", "holdout": False,
                  "spread_mult": [1.0, 2.0], "pnl": [1.0, -2.0], "sharpe": 0.1, "max_dd": 3.0, "es_5": -1.0,
                  "trades": 4, "win_rate": 0.5, "config_hash": "x"}).to_parquet(tmp_path / "registry.parquet")
    run = tmp_path / "2026-10-05-forecast" / "20261002-143446"
    run.mkdir(parents=True)
    (run / "params.json").write_text(json.dumps({"commit": "123abc"}))
    (tmp_path / "2026-10-05-forecast" / "notes").mkdir()
    rows = export.export(out=tmp_path / "registry.csv")
    assert list(rows.columns) == export.COLUMNS
    assert rows.set_index("run").loc["20261101-120000", ["card", "variant"]].tolist() == ["2026-11-01-demo", "a"]
    assert rows.set_index("run").loc["20261002-143446", ["card", "commit"]].tolist() == ["2026-10-05-forecast", "123abc"]
    assert len(rows) == 3


def test_desk_snapshot(tmp_path, monkeypatch):
    monkeypatch.setattr(ledger, "ROOT", tmp_path)
    ledger.log("signals", {"date": "2026-11-04", "expiry": "2026-12-04", "dte": 30, "rv_forecast": 0.15,
                           "iv": 0.15, "vrp": 0.0, "signal": "flat", "ts": "2026-11-04T10:15:00-05:00"})
    ledger.log("signals", {"date": "2026-11-05", "expiry": "2026-12-04", "dte": 29, "rv_forecast": 0.15,
                           "iv": 0.2, "vrp": 0.05, "signal": "short", "ts": "2026-11-05T10:15:00-05:00"})
    pos = {"side": "short", "right": "P", "strike": 700.0, "expiry": "2026-12-04", "qty": 1, "entry_price": 10.0,
           "entry_date": "2026-11-05", "entry_ts": "2026-11-05T10:15:00-05:00",
           "hedges": [{"date": "2026-11-05", "ts": "2026-11-05T10:20:00-05:00", "shares": -50, "price": 700.0}]}
    ledger.save_position(pos)
    ledger.log("trades", {k: v for k, v in pos.items() if k != "hedges"} | {"date": "2026-11-05",
                          "ts": "2026-11-05T10:15:00-05:00", "action": "open", "price": 10.0})
    chain = pd.DataFrame({"asof": [pd.Timestamp("2026-11-05 10:30", tz="America/New_York")],
                          "expiry": [date(2026, 12, 4)], "strike": [700.0], "right": ["P"], "mid": [9.0],
                          "und_price": [702.0]})
    cfg = config.load()
    snap = desk.build(chain, cfg)
    p = snap["position"]
    assert (p["option_pnl"], p["hedge_pnl"], p["pnl"]) == (100.0, -100.0, 0.0)
    assert (p["premium"], p["stop"], p["take"], p["hedge_shares"]) == (1000.0, -1000.0, 500.0, -50)
    assert snap["asof"] == "2026-11-05T10:30:00-05:00" and snap["realized"] == 0
    assert snap["signals"][1]["signal"] == "short" and snap["trades"][0]["action"] == "open"
    assert [(b["date"], b["total"]) for b in snap["book"]] == [("2026-11-04", 0), ("2026-11-05", 0.0)]
    desk.write(chain, cfg, tmp_path / "desk.json")
    desk.write(chain, cfg, tmp_path / "desk.json")
    assert ledger.read_log("book")["date"].tolist() == ["2026-11-05"]
    ledger.clear_position()
    out = desk.write(chain, cfg, tmp_path / "desk.json")
    assert json.loads(out.read_text())["position"] is None


def test_collect_reads_desk(repo):
    (repo / "research" / "desk.json").write_text(json.dumps({"asof": "x", "signals": [], "trades": []}))
    assert collect.collect()["desk"]["asof"] == "x"


SHADOW = {"asof": "2026-11-06T10:14:00-05:00", "start": "2026-09-26", "capital": 250000, "min_days": 60,
          "snapshots": [{"date": "2026-11-06", "ts": "x", "folder": "2026-11-06/1014"}],
          "books": [{"name": "Paper rules", "exp": None, "variant": None, "error": None},
                    {"name": "Demo", "exp": "2026-11-01-demo", "variant": "a", "error": None},
                    {"name": "Gone", "exp": "2026-01-01-gone", "variant": "b", "placeholder": "Waiting"}]}


def test_collect_reads_shadow(repo):
    (repo / "research" / "shadow.json").write_text(json.dumps(SHADOW))
    (repo / "research" / "desk.json").write_text(json.dumps({
        "signals": [{"date": "2026-11-05"}, {"date": "2026-11-06"}],
        "trades": [{"action": "open"}, {"action": "close", "pnl": -27.0}],
        "book": [{"date": "2026-11-05", "total": 40.0}, {"date": "2026-11-06", "total": 15.0}]}))
    s = collect.collect()["shadow"]
    paper, demo, gone = s["books"]
    assert (paper["card"], paper["expect"]) == (None, None)
    assert demo["card"] == "2026-11-01-demo" and gone["card"] is None
    assert demo["expect"]["trades_year"] == pytest.approx(5 / 10.58, rel=1e-2)
    assert demo["expect"]["pnl_trade"] == pytest.approx(20.1)
    assert s["paper"] == {"pnl": 15.0, "max_dd": 25.0, "trades": 1, "win_rate": 0.0, "days": 2}


def test_build_has_strategies_view_and_refuses_nan(repo, tmp_path_factory):
    (repo / "research" / "shadow.json").write_text(json.dumps(SHADOW))
    out = tmp_path_factory.mktemp("site") / "_site"
    build.build(out, root=repo)
    page = (out / "index.html").read_text()
    assert 'id="strategies"' in page and 'id="to-strategies"' in page
    (repo / "research" / "shadow.json").write_text(json.dumps(SHADOW).replace('"capital": 250000', '"capital": NaN'))
    with pytest.raises(ValueError):
        build.build(out, root=repo)


def test_clean_drops_non_finite():
    assert desk.clean(float("-inf")) is None and desk.clean(float("nan")) is None and desk.clean(1.23456) == 1.2346
