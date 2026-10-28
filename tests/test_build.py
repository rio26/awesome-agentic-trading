"""Tests for the data validation, README/section rendering, and scout ranking."""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import build_readme  # noqa: E402
import common  # noqa: E402
import scout  # noqa: E402

SECTIONS = [{"key": "agents", "title": "Trading agents & frameworks", "intro": "Intro."},
            {"key": "incidents", "title": "Incidents", "intro": "", "sort": "year"}]


def entry(**over):
    base = {"name": "Demo", "repo": "octo/demo", "section": "agents",
            "description": "Does a thing.", "markets": ["crypto"], "mode": "paper"}
    base.update(over)
    return base


def incident(name, year, n):
    return entry(name=name, repo=None, url=f"https://a.example/{n}", section="incidents", year=year, markets=[], mode=None)


# -- validation --------------------------------------------------------------- #

def test_valid_entry_has_no_problems():
    assert common.validate([entry()], SECTIONS) == []


def test_missing_fields_and_bad_section_are_reported():
    problems = common.validate([{"name": "X", "section": "nope", "repo": "a/b"}], SECTIONS)
    assert any("missing `description`" in p for p in problems)
    assert any("unknown section" in p for p in problems)


def test_needs_repo_or_url():
    assert any("needs `repo`" in p for p in common.validate([entry(repo=None)], SECTIONS))
    assert common.validate([entry(repo=None, url="https://example.org/x")], SECTIONS) == []


def test_bad_market_mode_and_description_style():
    problems = common.validate([entry(markets=["stonks"], mode="yolo", description="no full stop")], SECTIONS)
    assert any("unknown market" in p for p in problems)
    assert any("unknown mode" in p for p in problems)
    assert any("full stop" in p for p in problems)


def test_duplicate_targets_are_reported():
    problems = common.validate([entry(), entry(name="Other", repo="Octo/Demo")], SECTIONS)
    assert any("duplicate" in p for p in problems)


def test_entries_must_live_in_the_file_named_after_their_section(tmp_path, monkeypatch):
    d = tmp_path / "entries"
    d.mkdir()
    (d / "agents.yaml").write_text("- name: A\n  repo: a/a\n  section: risk\n  description: X.\n")
    monkeypatch.setattr(common, "ENTRIES_DIR", d)
    try:
        common.load_entries()
    except common.DataError as err:
        assert "file is `agents`" in str(err)
    else:
        raise AssertionError("expected DataError")


def test_section_defaults_to_file_name(tmp_path, monkeypatch):
    d = tmp_path / "entries"
    d.mkdir()
    (d / "agents.yaml").write_text("- name: A\n  repo: a/a\n  description: X.\n")
    monkeypatch.setattr(common, "ENTRIES_DIR", d)
    assert common.load_entries()[0]["section"] == "agents"


# -- rendering ---------------------------------------------------------------- #

def test_digest_entry_is_one_plain_line_and_full_entry_adds_tags_and_stars():
    digest = build_readme.render_entry(entry(), {})
    assert digest == "- [Demo](https://github.com/octo/demo) - Does a thing."
    full = build_readme.render_entry(entry(), {}, full=True)
    assert full.count("\n") == 0
    assert "`crypto`" in full and "`paper`" in full and "img.shields.io/github/stars/octo/demo" in full


def test_zh_uses_description_zh_and_falls_back_to_english():
    assert "做一件事。" in build_readme.render_entry(entry(description_zh="做一件事。"), {}, lang="zh")
    assert "Does a thing." in build_readme.render_entry(entry(), {}, lang="zh")


def test_render_entry_marks_stale_and_archived():
    old = (datetime.now(timezone.utc) - timedelta(days=400)).isoformat()
    assert "no commits in 13 months" in build_readme.render_entry(entry(), {"octo/demo": {"pushed_at": old}})
    assert "13 个月无提交" in build_readme.render_entry(entry(), {"octo/demo": {"pushed_at": old}}, lang="zh")
    assert "**archived**" in build_readme.render_entry(entry(), {"octo/demo": {"archived": True}})


def test_render_entry_without_repo_has_no_badges_but_shows_year():
    line = build_readme.render_entry(incident("Paper", 2024, 1), {})
    assert "(2024)" in line and "shields.io" not in line


def test_github_anchor_matches_github_rules():
    assert build_readme.github_anchor("Trading agents & frameworks") == "trading-agents--frameworks"
    assert build_readme.github_anchor("Execution: broker & exchange access") == "execution-broker--exchange-access"
    assert build_readme.github_anchor("Papers") == "papers"


def test_full_pages_sort_by_stars_then_name_and_year_sections_newest_first():
    meta = {"octo/big": {"stars": 500}, "octo/small": {"stars": 5}}
    items = [entry(name="zeta", repo="octo/small"), entry(name="Alpha", repo="octo/big"), entry(name="Mid", repo="octo/none")]
    assert [e["name"] for e in build_readme.ordered(items, SECTIONS[0], meta)] == ["Alpha", "zeta", "Mid"]
    inc = [incident("Old", 2012, 1), incident("New", 2026, 2)]
    assert [e["name"] for e in build_readme.ordered(inc, SECTIONS[1], {})] == ["New", "Old"]


def test_readme_is_a_digest_with_links_to_full_pages(monkeypatch):
    monkeypatch.setattr(build_readme, "TEMPLATES", ROOT / "templates")
    entries = [entry(name=f"Agent {i}", repo=f"octo/a{i}") for i in range(8)]
    out = build_readme.render_readme(entries, SECTIONS, {})
    assert out.count("[Agent ") == build_readme.DIGEST_PER_SECTION
    assert "**[All 8 →](sections/agents.md)**" in out
    assert "| [Trading agents & frameworks](#trading-agents--frameworks) (8) |" in out  # contents grid
    assert "<!-- entries: 8 -->" in out
    zh = build_readme.render_readme(entries, SECTIONS, {}, lang="zh")
    assert "**[全部 8 条 →](sections/agents.zh-CN.md)**" in zh and "## 目录" in zh


def test_readme_omits_the_all_link_when_the_section_fits(monkeypatch):
    monkeypatch.setattr(build_readme, "TEMPLATES", ROOT / "templates")
    out = build_readme.render_readme([entry()], SECTIONS, {})
    assert "→](sections/" not in out


def test_featured_entries_make_a_start_here_section(monkeypatch):
    monkeypatch.setattr(build_readme, "TEMPLATES", ROOT / "templates")
    out = build_readme.render_readme([entry(featured=True)], SECTIONS, {})
    assert "## Start here" in out and out.count("[Demo](") == 2


def test_section_pages_have_navigation_and_every_entry(monkeypatch):
    monkeypatch.setattr(build_readme, "TEMPLATES", ROOT / "templates")
    entries = [entry(name=f"Agent {i}", repo=f"octo/a{i}") for i in range(8)] + [incident("Boom", 2026, 1)]
    files = build_readme.render_all(entries, SECTIONS, {})
    agents = files[build_readme.SECTIONS_OUT / "agents.md"]
    incidents = files[build_readme.SECTIONS_OUT / "incidents.md"]
    assert agents.count("[Agent ") == 8
    assert "[← README](../README.md)" in agents and "[Incidents →](incidents.md)" in agents
    assert "[简体中文](agents.zh-CN.md)" in agents
    assert "[← Trading agents & frameworks](agents.md)" in incidents and "Incidents →" not in incidents
    assert "8 entries, by stars" in agents and "1 entries, newest first" in incidents
    zh = files[build_readme.SECTIONS_OUT / "agents.zh-CN.md"]
    assert "[← 首页](../README.zh-CN.md)" in zh and "[English](agents.md)" in zh and zh.count("[Agent ") == 8
    assert len(files) == 2 * (1 + 2)  # two languages × (README + two live sections)


def test_shipped_data_validates_and_generated_files_are_current():
    sections = common.load_sections()
    entries = common.load_entries()
    assert common.validate(entries, sections) == []
    assert build_readme.main(["--check"]) == 0


# -- scout ranking ------------------------------------------------------------ #

def test_scout_rank_excludes_listed_and_patterns_and_sorts_by_velocity():
    now = datetime.now(timezone.utc)
    def item(name, stars, days):
        return {"full_name": name, "name": name.split("/")[1], "stargazers_count": stars, "forks_count": 3,
                "license": {"spdx_id": "MIT"}, "created_at": (now - timedelta(days=days)).isoformat(),
                "language": "Python", "description": "x | y", "_pass": "new"}
    found = {"a/fast": item("a/fast", 100, 2), "a/slow": item("a/slow", 100, 50),
             "a/listed": item("a/listed", 999, 1), "a/tutorial-bot": item("a/tutorial-bot", 500, 1)}
    rows = scout.rank(found, {"a/listed"}, scout.DEFAULT_EXCLUDE)
    assert [r["repo"] for r in rows] == ["a/fast", "a/slow"]
    assert rows[0]["description"] == "x / y"  # pipes escaped for the Markdown table


def test_scout_flags_mark_the_common_junk_patterns():
    base = {"full_name": "a/b", "name": "b", "stargazers_count": 150, "forks_count": 0,
            "license": None, "description": "Great bot, contact me on Telegram t.me/x"}
    assert scout.flags(base, 3) == ["no-license", "0-forks", "fast-stars", "contact-funnel"]
    clean = {"full_name": "a/c", "name": "c", "stargazers_count": 150, "forks_count": 20,
             "license": {"spdx_id": "MIT"}, "description": "Does a thing."}
    assert scout.flags(clean, 30) == []
