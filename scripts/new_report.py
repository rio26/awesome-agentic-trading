#!/usr/bin/env python3
"""Scaffold this week's report in reports/ with the data sections filled in.

    python scripts/new_report.py                       # reports/<today>.md
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
TEMPLATE = REPORTS / "_template.md"


def previous_report(today: str) -> Path | None:
    dated = sorted(p for p in REPORTS.glob("20??-??-??.md") if p.stem < today)
    return dated[-1] if dated else None


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", default=date.today().isoformat())
    parser.add_argument("--scout", type=Path, help="scout.md from scripts/scout.py to embed")
    args = parser.parse_args(argv)

    out = REPORTS / f"{args.date}.md"
    if out.exists():
        print(f"{out.relative_to(ROOT)} already exists; edit it instead", file=sys.stderr)
        return 1

    entries, sections, meta = load_entries(), load_sections(), load_metadata()
    prev = previous_report(args.date)
    since = prev.stem if prev else "0000-00-00"

    counts = {s["key"]: 0 for s in sections}
    for e in entries:
        counts[e["section"]] += 1
    numbers = f"{len(entries)} entries. " + ", ".join(f"{s['title']} {counts[s['key']]}" for s in sections if counts[s["key"]]) + "."

    added = [e for e in entries if since < str(e.get("added", "")) <= args.date]
    added_md = "\n".join(f"- [{e['name']}]({entry_url(e)}) ({e['section']}) - {e['description']}" for e in added) or "Nothing added."

    stale = []
    for e in entries:
        info = meta.get(e.get("repo", ""), {})
        age = days_since(info.get("pushed_at"))
        if info.get("archived"):
            stale.append(f"- {e['name']}: archived")
        elif age is not None and age > STALE_DAYS:
            stale.append(f"- {e['name']}: no commits in {age // 30} months")
    stale_md = ("Quiet:\n" + "\n".join(stale)) if stale else "Nothing quiet."

    held = [r for r in load_reviewed() if r["decision"] == "hold"]
    held_md = ("Held for review:\n" + "\n".join(f"- `{r['repo']}` until {r['revisit']}: {r['reason']}" for r in held)) if held else ""

    scout_md = "See the weekly issue."
    if args.scout and args.scout.exists():
        scout_md = re.sub(r"^## .*\n", "", args.scout.read_text(encoding="utf-8"), count=1).strip()

    text = TEMPLATE.read_text(encoding="utf-8")
    for key, value in {
        "date": args.date, "numbers": numbers, "added": added_md, "stale": stale_md, "held": held_md,
        "scout": scout_md, "previous": f"[{prev.stem}]({prev.name})" if prev else "none",
    }.items():
        text = text.replace("{{" + key + "}}", value)
    out.write_text(text, encoding="utf-8")
    print(f"wrote {out.relative_to(ROOT)}; now write Highlights and Opportunities, then add it to reports/README.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
