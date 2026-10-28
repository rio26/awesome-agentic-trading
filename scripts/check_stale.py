#!/usr/bin/env python3
"""Refresh data/metadata.json from the GitHub API and report stale or archived entries.

    python scripts/check_stale.py                 # refresh metadata, print report
    python scripts/check_stale.py --report out.md # also write a Markdown report (used by the weekly issue)

Set GITHUB_TOKEN for a higher rate limit. Exit status is 0 even when entries are
stale; the report is the output, the list owner decides what to do.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import STALE_DAYS, days_since, gh_get, load_entries, load_metadata, save_metadata  # noqa: E402


def refresh(entries: list[dict]) -> tuple[dict, list[str]]:
    meta = load_metadata()
    missing: list[str] = []
    for e in entries:
        repo = e.get("repo")
        if not repo:
            continue
        info = gh_get(f"/repos/{repo}")
        if info is None:
            missing.append(repo)
            continue
        meta[repo] = {
            "stars": info.get("stargazers_count", 0),
            "pushed_at": info.get("pushed_at"),
            "archived": bool(info.get("archived")),
            "license": (info.get("license") or {}).get("spdx_id"),
            "full_name": info.get("full_name"),
        }
    return meta, missing


def report(entries: list[dict], meta: dict, missing: list[str]) -> str:
    stale, archived, renamed = [], [], []
    for e in entries:
        repo = e.get("repo")
        info = meta.get(repo or "")
        if not repo or not info:
            continue
        if info.get("archived"):
            archived.append((repo, e["name"]))
        age = days_since(info.get("pushed_at"))
        if age is not None and age > STALE_DAYS:
            stale.append((repo, e["name"], age))
        if info.get("full_name") and info["full_name"].lower() != repo.lower():
            renamed.append((repo, info["full_name"]))

    lines = ["## Stale check", ""]
    if not (stale or archived or missing or renamed):
        lines.append("All listed repositories are active. Nothing to do.")
        return "\n".join(lines) + "\n"
    if archived:
        lines += ["### Archived", ""] + [f"- `{r}` ({n})" for r, n in archived] + [""]
    if stale:
        lines += [f"### No commits in {STALE_DAYS}+ days", ""]
        lines += [f"- `{r}` ({n}): {a} days" for r, n, a in sorted(stale, key=lambda x: -x[2])] + [""]
    if renamed:
        lines += ["### Renamed or transferred", ""] + [f"- `{old}` is now `{new}`" for old, new in renamed] + [""]
    if missing:
        lines += ["### Not found (deleted or private)", ""] + [f"- `{r}`" for r in missing] + [""]
    lines.append("Stale entries stay listed with a note until they are removed by a maintainer.")
    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, help="write the Markdown report to this file")
    args = parser.parse_args(argv)

    entries = load_entries()
    meta, missing = refresh(entries)
    save_metadata(meta)
    text = report(entries, meta, missing)
    print(text)
    if args.report:
        args.report.write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
