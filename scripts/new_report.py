#!/usr/bin/env python3
"""Scaffold this week's report in reports/, in English and Simplified Chinese, with the data sections filled in.

    python scripts/new_report.py                       # reports/<today>.md and reports/<today>.zh-CN.md
    python scripts/new_report.py --scout scout.md      # also paste the scout table from the weekly job

Fills: entry counts, entries added since the previous report, stale and held
repositories. Leaves "Highlights" and "Opportunities" for a human to write.
Refuses to overwrite an existing report.
"""
from __future__ import annotations

import argparse
import re
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (  # noqa: E402
    ROOT, STALE_DAYS, days_since, entry_url, load_entries, load_metadata, load_reviewed, load_sections,
)

REPORTS = ROOT / "reports"
LANGS = {
    "en": {"suffix": "", "template": "_template.md",
           "numbers": "{n} entries. {parts}.", "nothing_added": "Nothing added.",
           "quiet": "Quiet:", "nothing_quiet": "Nothing quiet.", "archived": "archived", "stale": "no commits in {m} months",
           "held": "Held for review:", "until": "until", "scout": "See the weekly issue.", "none": "none"},
    "zh": {"suffix": ".zh-CN", "template": "_template.zh-CN.md",
           "numbers": "共 {n} 条。{parts}。", "nothing_added": "本周没有新增。",
           "quiet": "沉寂：", "nothing_quiet": "没有沉寂的条目。", "archived": "已归档", "stale": "{m} 个月无提交",
           "held": "观察中：", "until": "至", "scout": "见本周的 issue。", "none": "无"},
}


def previous_report(today: str) -> Path | None:
    dated = sorted(p for p in REPORTS.glob("20??-??-??.md") if p.stem < today)
    return dated[-1] if dated else None


def section_title(s: dict, lang: str) -> str:
    return (s.get("title_zh") or s["title"]) if lang == "zh" else s["title"]


def description(e: dict, lang: str) -> str:
    return (e.get("description_zh") or e["description"]) if lang == "zh" else e["description"]


def build(lang: str, today: str, since: str, prev: Path | None, scout_text: str | None,
          entries: list[dict], sections: list[dict], meta: dict, reviewed: list[dict]) -> str:
    t = LANGS[lang]
    counts = {s["key"]: 0 for s in sections}
    for e in entries:
        counts[e["section"]] += 1
    parts = "、".join if lang == "zh" else ", ".join
    numbers = t["numbers"].format(n=len(entries), parts=parts(f"{section_title(s, lang)} {counts[s['key']]}" for s in sections if counts[s["key"]]))

    added = [e for e in entries if since < str(e.get("added", "")) <= today]
    added_md = "\n".join(f"- [{e['name']}]({entry_url(e)}) ({e['section']}) - {description(e, lang)}" for e in added) or t["nothing_added"]

    stale = []
    for e in entries:
        info = meta.get(e.get("repo", ""), {})
        age = days_since(info.get("pushed_at"))
        if info.get("archived"):
            stale.append(f"- {e['name']}: {t['archived']}")
        elif age is not None and age > STALE_DAYS:
            stale.append(f"- {e['name']}: " + t["stale"].format(m=age // 30))
    stale_md = (t["quiet"] + "\n" + "\n".join(stale)) if stale else t["nothing_quiet"]

    held = [r for r in reviewed if r["decision"] == "hold"]
    held_md = (t["held"] + "\n" + "\n".join(f"- `{r['repo']}` {t['until']} {r['revisit']}: {r['reason']}" for r in held)) if held else ""

    scout_md = scout_text or t["scout"]
    previous = f"[{prev.stem}]({prev.stem}{t['suffix']}.md)" if prev else t["none"]

    text = (REPORTS / t["template"]).read_text(encoding="utf-8")
    for key, value in {"date": today, "numbers": numbers, "added": added_md, "stale": stale_md,
                       "held": held_md, "scout": scout_md, "previous": previous}.items():
        text = text.replace("{{" + key + "}}", value)
    return text


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", default=date.today().isoformat())
    parser.add_argument("--scout", type=Path, help="scout.md from scripts/scout.py to embed")
    args = parser.parse_args(argv)

    outputs = {lang: REPORTS / f"{args.date}{t['suffix']}.md" for lang, t in LANGS.items()}
    existing = [p for p in outputs.values() if p.exists()]
    if existing:
        print(f"{existing[0].relative_to(ROOT)} already exists; edit it instead", file=sys.stderr)
        return 1

    scout_text = None
    if args.scout and args.scout.exists():
        scout_text = re.sub(r"^## .*\n", "", args.scout.read_text(encoding="utf-8"), count=1).strip()

    entries, sections, meta, reviewed = load_entries(), load_sections(), load_metadata(), load_reviewed()
    prev = previous_report(args.date)
    since = prev.stem if prev else "0000-00-00"
    for lang, out in outputs.items():
        out.write_text(build(lang, args.date, since, prev, scout_text, entries, sections, meta, reviewed), encoding="utf-8")
        print(f"wrote {out.relative_to(ROOT)}")
    print("now write Highlights and Opportunities in both, then add a row to reports/README.md and reports/README.zh-CN.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
