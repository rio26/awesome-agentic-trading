#!/usr/bin/env python3
"""Render README.md from data/entries.yaml, data/sections.yaml and the templates.

    python scripts/build_readme.py          # write README.md
    python scripts/build_readme.py --check  # exit 1 if README.md is out of date (CI)
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (  # noqa: E402
    ROOT, STALE_DAYS, DataError, days_since, entry_url, load_entries, load_metadata,
    load_sections, validate,
)

TEMPLATES = ROOT / "templates"
README = ROOT / "README.md"
BADGE = "https://img.shields.io/github/{kind}/{repo}?style=flat-square&labelColor=2b2b2b&color=6b6b6b"


def github_anchor(title: str) -> str:
    """Mimic GitHub's heading anchors: lowercase, drop punctuation, spaces to hyphens (kept, even doubled)."""
    cleaned = re.sub(r"[^\w\- ]", "", title.lower())
    return cleaned.replace(" ", "-")


def badges(repo: str) -> str:
    stars = BADGE.format(kind="stars", repo=repo) + "&label=stars"
    updated = BADGE.format(kind="last-commit", repo=repo) + "&label=updated"
    return f'<img src="{stars}" alt="stars"> <img src="{updated}" alt="last commit">'


def tags(e: dict) -> str:
    parts = [f"`{m}`" for m in (e.get("markets") or [])]
    if e.get("mode"):
        parts.append(f"`{e['mode']}`")
    if e.get("language") and str(e["language"]).lower() not in ("none", "-", "null"):
        parts.append(f"`{e['language']}`")
    return " ".join(parts)


def status_note(e: dict, meta: dict) -> str:
    info = meta.get(e.get("repo", ""), {})
    if not info:
        return ""
    if info.get("archived"):
        return " · **archived**"
    age = days_since(info.get("pushed_at"))
    if age is not None and age > STALE_DAYS:
        return f" · no commits in {age // 30} months"
    return ""


def render_entry(e: dict, meta: dict) -> str:
    name, url, desc = e["name"], entry_url(e), e["description"].strip()
    year = f" ({e['year']})" if e.get("year") else ""
    line = f"- [{name}]({url}) - {desc}{year}{status_note(e, meta)}"
    extras = []
    if tags(e):
        extras.append(tags(e))
    if e.get("repo"):
        extras.append(badges(e["repo"]))
    if extras:
        line += "  \n  " + " &nbsp; ".join(extras)
    return line


def render(entries: list[dict], sections: list[dict], meta: dict) -> str:
    header = (TEMPLATES / "header.md").read_text(encoding="utf-8")
    footer = (TEMPLATES / "footer.md").read_text(encoding="utf-8")

    by_section: dict[str, list[dict]] = {s["key"]: [] for s in sections}
    for e in entries:
        by_section[e["section"]].append(e)

    toc = ["## Contents", ""]
    body: list[str] = []

    featured = [e for e in entries if e.get("featured")]
    if featured:
        toc.append("- [Start here](#start-here)")
        body += ["## Start here", "", "A few entries that give the shape of the field in an evening.", ""]
        body += [render_entry(e, meta) for e in featured[:5]]
        body.append("")

    for s in sections:
        if s.get("sort") == "year":
            items = sorted(by_section[s["key"]], key=lambda e: (-int(e.get("year") or 0), e["name"].lower()))
        else:
            items = sorted(by_section[s["key"]], key=lambda e: e["name"].lower())
        if not items:
            continue
        toc.append(f"- [{s['title']}](#{github_anchor(s['title'])}) ({len(items)})")
        body += [f"## {s['title']}", ""]
        if s.get("intro"):
            body += [s["intro"].strip(), ""]
        body += [render_entry(e, meta) for e in items]
        body.append("")

    counts = f"<!-- entries: {len(entries)} -->"
    return "\n".join([header.rstrip(), "", *toc, "", *body, footer.strip(), counts, ""])


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="verify README.md is up to date; do not write")
    args = parser.parse_args(argv)

    try:
        sections = load_sections()
        entries = load_entries()
    except DataError as err:
        print(f"error: {err}", file=sys.stderr)
        return 2
    problems = validate(entries, sections)
    if problems:
        print("data problems:", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        return 2

    output = render(entries, sections, load_metadata())
    if args.check:
        current = README.read_text(encoding="utf-8") if README.exists() else ""
        if current != output:
            print("README.md is out of date: run `python scripts/build_readme.py`", file=sys.stderr)
            return 1
        print(f"README.md is up to date ({len(entries)} entries)")
        return 0
    README.write_text(output, encoding="utf-8")
    print(f"wrote README.md with {len(entries)} entries in {len(sections)} sections")
    return 0


if __name__ == "__main__":
    sys.exit(main())
