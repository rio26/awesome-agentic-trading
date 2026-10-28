#!/usr/bin/env python3
"""Render README.md, README.zh-CN.md and sections/*.md from data/.

README is a fixed-size digest: a grid of sections, then the top entries of each
section by stars with a link to the full page. sections/<key>.md (and
sections/<key>.zh-CN.md) hold every entry of that section.

    python scripts/build_readme.py          # write all generated files
    python scripts/build_readme.py --check  # exit 1 if any generated file is out of date (CI)
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (  # noqa: E402
    ROOT, SECTIONS_OUT, SEED_DATE, STALE_DAYS, DataError, days_since, entry_url, load_entries, load_metadata,
    load_sections, validate,
)

TEMPLATES = ROOT / "templates"
DIGEST_PER_SECTION = 5
LANGS = ("en", "zh")
STARS_BADGE = "https://img.shields.io/github/stars/{repo}?style=flat-square&labelColor=2b2b2b&color=6b6b6b&label="

T = {
    "en": {
        "readme": "README.md", "suffix": "", "header": "header.md", "footer": "footer.md",
        "contents": "Contents", "start_here": "Start here",
        "start_blurb": "A few entries that give the shape of the field in an evening.",
        "recent": "Recently added",
        "all": "All {n} →", "entries_by_stars": "{n} entries, by stars.", "entries_by_year": "{n} entries, newest first.",
        "edit": "Add one by editing `data/entries/{key}.yaml`.", "back": "← README", "lang_switch": "[简体中文]({page})",
        "archived": "archived", "stale": "no commits in {m} months",
    },
    "zh": {
        "readme": "README.zh-CN.md", "suffix": ".zh-CN", "header": "header.zh-CN.md", "footer": "footer.zh-CN.md",
        "contents": "目录", "start_here": "从这里开始",
        "start_blurb": "一个晚上就能看出这个领域大致轮廓的几条。",
        "recent": "最近新增",
        "all": "全部 {n} 条 →", "entries_by_stars": "共 {n} 条，按 star 排序。", "entries_by_year": "共 {n} 条，最新在前。",
        "edit": "新增条目请编辑 `data/entries/{key}.yaml`。", "back": "← 首页", "lang_switch": "[English]({page})",
        "archived": "已归档", "stale": "{m} 个月无提交",
    },
}


def github_anchor(title: str) -> str:
    """Mimic GitHub's heading anchors: lowercase, drop punctuation, spaces to hyphens (kept, even doubled)."""
    cleaned = re.sub(r"[^\w\- ]", "", title.lower())
    return cleaned.replace(" ", "-")


def title_of(section: dict, lang: str) -> str:
    return section.get("title_zh") or section["title"] if lang == "zh" else section["title"]


def intro_of(section: dict, lang: str) -> str:
    return (section.get("intro_zh") or section.get("intro") or "") if lang == "zh" else (section.get("intro") or "")


def desc_of(e: dict, lang: str) -> str:
    return (e.get("description_zh") or e["description"]).strip() if lang == "zh" else e["description"].strip()


def status_note(e: dict, meta: dict, lang: str) -> str:
    info = meta.get(e.get("repo", ""), {})
    if not info:
        return ""
    if info.get("archived"):
        return f" · **{T[lang]['archived']}**"
    age = days_since(info.get("pushed_at"))
    if age is not None and age > STALE_DAYS:
        return " · " + T[lang]["stale"].format(m=age // 30)
    return ""


def tags(e: dict) -> str:
    parts = [f"`{m}`" for m in (e.get("markets") or [])]
    if e.get("mode"):
        parts.append(f"`{e['mode']}`")
    return " ".join(parts)


def render_entry(e: dict, meta: dict, lang: str = "en", full: bool = False) -> str:
    """One line per entry. Digest: name - description. Full page: adds tags and a stars badge."""
    year = f" ({e['year']})" if e.get("year") else ""
    line = f"- [{e['name']}]({entry_url(e)}) - {desc_of(e, lang)}{year}{status_note(e, meta, lang)}"
    if full:
        if tags(e):
            line += " " + tags(e)
        if e.get("repo"):
            line += f' <img src="{STARS_BADGE.format(repo=e["repo"])}" alt="stars">'
    return line


def stars_of(e: dict, meta: dict) -> int:
    return int(meta.get(e.get("repo", ""), {}).get("stars", 0) or 0)


def ordered(items: list[dict], section: dict, meta: dict) -> list[dict]:
    """By year (newest first) when the section says so, else by stars then name."""
    if section.get("sort") == "year":
        return sorted(items, key=lambda e: (-int(e.get("year") or 0), e["name"].lower()))
    return sorted(items, key=lambda e: (-stars_of(e, meta), e["name"].lower()))


def page_name(section: dict, lang: str) -> str:
    return f"{section['key']}{T[lang]['suffix']}.md"


def contents_grid(sections: list[dict], counts: dict[str, int], lang: str) -> list[str]:
    """Section links as a 3-column table, like a site map."""
    cells = [f"[{title_of(s, lang)}](#{github_anchor(title_of(s, lang))}) ({counts[s['key']]})" for s in sections if counts[s["key"]]]
    rows = [cells[i:i + 3] for i in range(0, len(cells), 3)]
    out = ["| | | |", "|---|---|---|"]
    for row in rows:
        out.append("| " + " | ".join(row + [""] * (3 - len(row))) + " |")
    return out


def render_readme(entries: list[dict], sections: list[dict], meta: dict, lang: str = "en") -> str:
    t = T[lang]
    header = (TEMPLATES / t["header"]).read_text(encoding="utf-8")
    footer = (TEMPLATES / t["footer"]).read_text(encoding="utf-8")

    by_section: dict[str, list[dict]] = {s["key"]: [] for s in sections}
    for e in entries:
        by_section[e["section"]].append(e)
    counts = {k: len(v) for k, v in by_section.items()}

    body: list[str] = [f"## {t['contents']}", ""] + contents_grid(sections, counts, lang) + [""]

    featured = [e for e in entries if e.get("featured")]
    if featured:
        body += [f"## {t['start_here']}", "", t["start_blurb"], ""]
        body += [render_entry(e, meta, lang) for e in featured[:5]]
        body.append("")

    recent = sorted((e for e in entries if str(e.get("added", "")) > SEED_DATE),
                    key=lambda e: (str(e["added"]), e["name"].lower()), reverse=True)[:10]
    if recent:
        body += [f"## {t['recent']}", ""] + [render_entry(e, meta, lang) + f" `{e['added']}`" for e in recent] + [""]

    for s in sections:
        items = ordered(by_section[s["key"]], s, meta)
        if not items:
            continue
        page = f"sections/{page_name(s, lang)}"
        body += [f"## {title_of(s, lang)}", ""]
        if intro_of(s, lang):
            body += [intro_of(s, lang).strip(), ""]
        body += [render_entry(e, meta, lang) for e in items[:DIGEST_PER_SECTION]]
        if len(items) > DIGEST_PER_SECTION:
            body += ["", f"**[{t['all'].format(n=len(items))}]({page})**"]
        body.append("")

    return "\n".join([header.rstrip(), "", *body, footer.strip(), f"<!-- entries: {len(entries)} -->", ""])


def render_section_page(section: dict, items: list[dict], meta: dict, lang: str, prev: dict | None, nxt: dict | None) -> str:
    t = T[lang]
    other = "zh" if lang == "en" else "en"
    nav = [f"[{t['back']}](../{t['readme']})"]
    if prev:
        nav.append(f"[← {title_of(prev, lang)}]({page_name(prev, lang)})")
    if nxt:
        nav.append(f"[{title_of(nxt, lang)} →]({page_name(nxt, lang)})")
    nav.append(t["lang_switch"].format(page=page_name(section, other)))
    count_line = (t["entries_by_year"] if section.get("sort") == "year" else t["entries_by_stars"]).format(n=len(items))
    lines = [
        f"<!-- Generated by scripts/build_readme.py from data/entries/{section['key']}.yaml. Edit the data, not this file. -->",
        f"# {title_of(section, lang)}",
        "",
        " · ".join(nav),
        "",
    ]
    if intro_of(section, lang):
        lines += [intro_of(section, lang).strip(), ""]
    lines += [f"{count_line} {t['edit'].format(key=section['key'])}", ""]
    lines += [render_entry(e, meta, lang, full=True) for e in items]
    lines += ["", " · ".join(nav), ""]
    return "\n".join(lines)


def render_all(entries: list[dict], sections: list[dict], meta: dict) -> dict[Path, str]:
    """Every generated file, keyed by path."""
    by_section: dict[str, list[dict]] = {s["key"]: [] for s in sections}
    for e in entries:
        by_section[e["section"]].append(e)
    live = [s for s in sections if by_section[s["key"]]]
    out: dict[Path, str] = {}
    for lang in LANGS:
        out[ROOT / T[lang]["readme"]] = render_readme(entries, sections, meta, lang)
        for i, s in enumerate(live):
            prev = live[i - 1] if i > 0 else None
            nxt = live[i + 1] if i + 1 < len(live) else None
            out[SECTIONS_OUT / page_name(s, lang)] = render_section_page(s, ordered(by_section[s["key"]], s, meta), meta, lang, prev, nxt)
    return out


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="verify generated files are up to date; do not write")
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

    files = render_all(entries, sections, load_metadata())
    if args.check:
        stale = [p for p, text in files.items() if (p.read_text(encoding="utf-8") if p.exists() else "") != text]
        extra = [p for p in SECTIONS_OUT.glob("*.md") if p not in files] if SECTIONS_OUT.exists() else []
        if stale or extra:
            for p in stale:
                print(f"out of date: {p.relative_to(ROOT)}", file=sys.stderr)
            for p in extra:
                print(f"orphan page: {p.relative_to(ROOT)}", file=sys.stderr)
            print("run `python scripts/build_readme.py`", file=sys.stderr)
            return 1
        print(f"generated files are up to date ({len(entries)} entries, {len(files)} files)")
        return 0

    SECTIONS_OUT.mkdir(exist_ok=True)
    for p, text in files.items():
        p.write_text(text, encoding="utf-8")
    for p in SECTIONS_OUT.glob("*.md"):
        if p not in files:
            p.unlink()
    print(f"wrote {len(files)} files for {len(entries)} entries")
    return 0


if __name__ == "__main__":
    sys.exit(main())
