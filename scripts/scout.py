#!/usr/bin/env python3
"""Scout GitHub for new and rising agentic-trading repositories that are not yet listed.

    python scripts/scout.py                    # print a Markdown report
    python scripts/scout.py --days 14 --min-stars 20 --report scout.md

Two passes:
  * new:    created in the last --days days with at least --min-stars stars
  * rising: created in the last 90 days with at least 5x --min-stars stars

Candidates are ranked by stars per day since creation. Repositories already in
data/entries/, and names matching --exclude patterns, are skipped. The output
is a report for a human; nothing is added to the list automatically.
"""
from __future__ import annotations

import argparse
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import gh_get, load_entries, load_reviewed  # noqa: E402

# Topic and free-text queries. Kept short on purpose: each is one search call.
TOPIC_QUERIES = [
    "topic:agentic-trading",
    "topic:trading-agents",
    "topic:trading-agent",
    "topic:ai-trading",
    "topic:llm-trading",
    "topic:prediction-markets",
    "topic:polymarket",
    "topic:trading-bot topic:llm",
    "topic:trading-bot topic:ai-agents",
    "topic:mcp-server topic:trading",
    "topic:mcp topic:finance",
]
TEXT_QUERIES = [
    '"trading agent" llm in:name,description',
    '"ai trading" agent in:name,description',
    'polymarket agent in:name,description',
    'kalshi bot in:name,description',
    'mcp server broker OR exchange trading in:description',
]
DEFAULT_EXCLUDE = [r"tutorial", r"course", r"homework", r"assignment", r"^test", r"template$"]


def search(query: str, created_after: datetime, min_stars: int) -> list[dict]:
    q = f"{query} created:>={created_after:%Y-%m-%d} stars:>={min_stars} archived:false"
    data = gh_get("/search/repositories", {"q": q, "sort": "stars", "order": "desc", "per_page": 50})
    time.sleep(2.1)  # search API: 30 requests per minute
    return (data or {}).get("items", [])


def collect(days: int, min_stars: int) -> dict[str, dict]:
    now = datetime.now(timezone.utc)
    found: dict[str, dict] = {}
    passes = [("new", now - timedelta(days=days), min_stars), ("rising", now - timedelta(days=90), min_stars * 5)]
    for label, since, stars in passes:
        for query in TOPIC_QUERIES + TEXT_QUERIES:
            for item in search(query, since, stars):
                key = item["full_name"].lower()
                if key not in found:
                    item["_pass"] = label
                    found[key] = item
    return found


def flags(item: dict, age_days: int) -> list[str]:
    """Cheap warning signs seen on star-farmed or promotional repos. A flag is a reason to look, not a verdict."""
    out = []
    if not (item.get("license") or {}).get("spdx_id"):
        out.append("no-license")
    stars = item.get("stargazers_count", 0)
    if stars >= 50 and item.get("forks_count", 0) == 0:
        out.append("0-forks")
    if age_days <= 7 and stars / age_days > 30:
        out.append("fast-stars")
    desc = (item.get("description") or "").lower()
    if any(w in desc for w in ("telegram", "t.me/", "whatsapp", "wechat", "contact me")):
        out.append("contact-funnel")
    return out


def reviewed_state(reviewed: list[dict], today: str) -> tuple[set[str], dict[str, dict]]:
    """Repos to hide (rejected, or held until a future date) and held repos now due for a second look."""
    hidden: set[str] = set()
    due: dict[str, dict] = {}
    for r in reviewed:
        key = r["repo"].lower()
        if r["decision"] == "rejected" or str(r.get("revisit")) > today:
            hidden.add(key)
        else:
            due[key] = r
    return hidden, due


def rank(found: dict[str, dict], listed: set[str], exclude: list[str], reviewed: list[dict] | None = None) -> list[dict]:
    now = datetime.now(timezone.utc)
    patterns = [re.compile(p, re.I) for p in exclude]
    hidden, due = reviewed_state(reviewed or [], now.strftime("%Y-%m-%d"))
    rows = []
    for key, item in found.items():
        if key in listed or key in hidden or any(p.search(item["name"]) for p in patterns):
            continue
        created = datetime.fromisoformat(item["created_at"].replace("Z", "+00:00"))
        age = max(1, (now - created).days)
        rows.append({
            "repo": item["full_name"],
            "stars": item["stargazers_count"],
            "age_days": age,
            "velocity": item["stargazers_count"] / age,
            "language": item.get("language") or "-",
            "license": (item.get("license") or {}).get("spdx_id") or "none",
            "forks": item.get("forks_count", 0),
            "flags": " ".join((["revisit"] if key in due else []) + flags(item, age)),
            "description": (item.get("description") or "").strip().replace("|", "/")[:120],
            "pass": item["_pass"],
        })
    return sorted(rows, key=lambda r: -r["velocity"])


def report(rows: list[dict], days: int) -> str:
    today = datetime.now(timezone.utc).date()
    lines = [f"## Scout report {today} (last {days} days, plus 90-day risers)", ""]
    if not rows:
        return "\n".join(lines + ["No new candidates.", ""])
    lines += ["| repo | stars | forks | age | stars/day | lang | license | flags | description |",
              "|---|---:|---:|---:|---:|---|---|---|---|"]
    for r in rows[:40]:
        lines.append(
            f"| [{r['repo']}](https://github.com/{r['repo']}) | {r['stars']} | {r['forks']} | {r['age_days']}d | "
            f"{r['velocity']:.1f} | {r['language']} | {r['license']} | {r['flags']} | {r['description']} |"
        )
    lines += ["", "Flags: `no-license`, `0-forks` (50+ stars, none), `fast-stars` (>30/day in the first week), "
              "`contact-funnel` (Telegram/WeChat/WhatsApp in the description), `revisit` (held earlier, now due). "
              "A flag means look closer, not reject. Decisions go in `data/reviewed.yaml` so they are not re-surfaced."]
    lines += ["", f"{len(rows)} candidates in total; top 40 shown. Add the good ones to the matching file under `data/entries/`.", ""]
    return "\n".join(lines)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--days", type=int, default=14)
    parser.add_argument("--min-stars", type=int, default=20)
    parser.add_argument("--exclude", action="append", default=[], help="regex on repo name; repeatable")
    parser.add_argument("--report", type=Path, help="write the Markdown report to this file")
    args = parser.parse_args(argv)

    listed = {e["repo"].lower() for e in load_entries() if e.get("repo")}
    found = collect(args.days, args.min_stars)
    rows = rank(found, listed, DEFAULT_EXCLUDE + args.exclude, load_reviewed())
    text = report(rows, args.days)
    print(text)
    if args.report:
        args.report.write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
