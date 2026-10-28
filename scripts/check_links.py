#!/usr/bin/env python3
"""Check that every non-GitHub `url` entry still resolves.

    python scripts/check_links.py                  # print a Markdown report
    python scripts/check_links.py --report links.md

GitHub repositories are covered by check_stale.py; this handles incidents,
regulation pages and other primary sources. A 403 or 405 usually means the
site blocks scripts, not that the page is gone, so those are listed as
"check by hand" rather than broken. Exit status is always 0.
"""
from __future__ import annotations

import argparse
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import load_entries  # noqa: E402

UA = "Mozilla/5.0 (compatible; awesome-agentic-trading link check; +https://github.com/rio26/awesome-agentic-trading)"
BLOCKED = {401, 403, 405, 429}


def probe(url: str, timeout: int = 20) -> tuple[str, int | None]:
    """Return ('ok' | 'blocked' | 'broken', status)."""
    for method in ("HEAD", "GET"):
        req = urllib.request.Request(url, method=method, headers={"User-Agent": UA, "Accept": "*/*"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return "ok", resp.status
        except urllib.error.HTTPError as err:
            if err.code in BLOCKED:
                return "blocked", err.code
            if method == "HEAD" and err.code in (404, 500, 501):
                continue  # some servers reject HEAD; try GET before giving up
            return "broken", err.code
        except Exception:  # noqa: BLE001 - DNS failure, timeout, TLS error: all "broken" for our purpose
            if method == "HEAD":
                continue
            return "broken", None
    return "broken", None


def report(results: list[tuple[dict, str, int | None]]) -> str:
    broken = [(e, st) for e, kind, st in results if kind == "broken"]
    blocked = [(e, st) for e, kind, st in results if kind == "blocked"]
    lines = ["## Link check", ""]
    if not broken and not blocked:
        lines.append(f"All {len(results)} external links resolve.")
        return "\n".join(lines) + "\n"
    if broken:
        lines += ["### Broken", ""] + [f"- [{e['name']}]({e['url']}) → {st or 'no response'}" for e, st in broken] + [""]
    if blocked:
        lines += ["### Check by hand (site blocks scripts)", ""] + [f"- [{e['name']}]({e['url']}) → {st}" for e, st in blocked] + [""]
    lines.append(f"{len(results)} links checked.")
    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args(argv)
    entries = [e for e in load_entries() if e.get("url") and not e.get("repo")]
    results = [(e, *probe(e["url"])) for e in entries]
    text = report(results)
    print(text)
    if args.report:
        args.report.write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
