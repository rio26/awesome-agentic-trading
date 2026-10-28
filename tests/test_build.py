"""Tests for the data validation, README rendering, and scout ranking."""
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
            {"key": "papers", "title": "Papers", "intro": ""}]


def entry(**over):
    base = {"name": "Demo", "repo": "octo/demo", "section": "agents",
            "description": "Does a thing.", "markets": ["crypto"], "mode": "paper"}
    base.update(over)
    return base


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


# -- rendering ---------------------------------------------------------------- #

def test_render_entry_has_link_tags_and_badges():
    line = build_readme.render_entry(entry(), {})
    assert "[Demo](https://github.com/octo/demo) - Does a thing." in line
    assert "`crypto`" in line and "`paper`" in line
    assert "img.shields.io/github/stars/octo/demo" in line


def test_render_entry_marks_stale_and_archived():
    old = (datetime.now(timezone.utc) - timedelta(days=400)).isoformat()
    assert "no commits in 13 months" in build_readme.render_entry(entry(), {"octo/demo": {"pushed_at": old}})
    assert "**archived**" in build_readme.render_entry(entry(), {"octo/demo": {"archived": True}})


def test_render_entry_without_repo_has_no_badges_but_shows_year():
    line = build_readme.render_entry(entry(repo=None, url="https://arxiv.org/abs/1", year=2024, markets=[], mode=None), {})
    assert "(2024)" in line and "shields.io" not in line


def test_render_orders_sections_and_sorts_entries(monkeypatch):
    monkeypatch.setattr(build_readme, "TEMPLATES", ROOT / "templates")
    entries = [entry(name="zeta"), entry(name="Alpha", repo="octo/alpha"),
               entry(name="Paper", repo=None, url="https://arxiv.org/abs/2", section="papers", markets=[], mode=None)]
    out = build_readme.render(entries, SECTIONS, {})
    assert out.index("## Trading agents & frameworks") < out.index("## Papers")
    assert out.index("[Alpha]") < out.index("[zeta]")
    assert "- [Trading agents & frameworks](#trading-agents--frameworks) (2)" in out
    assert "<!-- entries: 3 -->" in out


def test_github_anchor_matches_github_rules():
    assert build_readme.github_anchor("Trading agents & frameworks") == "trading-agents--frameworks"
    assert build_readme.github_anchor("Execution: broker & exchange access") == "execution-broker--exchange-access"
    assert build_readme.github_anchor("Papers") == "papers"


def test_featured_entries_make_a_start_here_section(monkeypatch):
    monkeypatch.setattr(build_readme, "TEMPLATES", ROOT / "templates")
    out = build_readme.render([entry(featured=True)], SECTIONS, {})
    assert "## Start here" in out and out.count("[Demo](") == 2


def test_shipped_data_validates_and_readme_is_current():
    sections = common.load_sections()
    entries = common.load_entries()
    assert common.validate(entries, sections) == []
    assert build_readme.main(["--check"]) == 0


# -- scout ranking ------------------------------------------------------------ #

def test_scout_rank_excludes_listed_and_patterns_and_sorts_by_velocity():
    now = datetime.now(timezone.utc)
    def item(name, stars, days):
        return {"full_name": name, "name": name.split("/")[1], "stargazers_count": stars,
                "created_at": (now - timedelta(days=days)).isoformat(), "language": "Python",
                "description": "x | y", "_pass": "new"}
    found = {"a/fast": item("a/fast", 100, 2), "a/slow": item("a/slow", 100, 50),
             "a/listed": item("a/listed", 999, 1), "a/tutorial-bot": item("a/tutorial-bot", 500, 1)}
    rows = scout.rank(found, {"a/listed"}, scout.DEFAULT_EXCLUDE)
    assert [r["repo"] for r in rows] == ["a/fast", "a/slow"]
    assert rows[0]["description"] == "x / y"  # pipes escaped for the Markdown table


def test_year_sorted_sections_are_newest_first(monkeypatch):
    monkeypatch.setattr(build_readme, "TEMPLATES", ROOT / "templates")
    sections = [{"key": "incidents", "title": "Incidents", "sort": "year"}]
    entries = [entry(name="Old", repo=None, url="https://a.example/1", section="incidents", year=2012, markets=[], mode=None),
               entry(name="New", repo=None, url="https://a.example/2", section="incidents", year=2026, markets=[], mode=None)]
    out = build_readme.render(entries, sections, {})
    assert out.index("[New]") < out.index("[Old]")


def test_unknown_language_is_not_rendered_as_a_tag():
    assert "`none`" not in build_readme.render_entry(entry(language="none"), {})
