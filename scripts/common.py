"""Shared helpers: load and validate data files, call the GitHub API."""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import yaml

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
ENTRIES_FILE = DATA_DIR / "entries.yaml"
SECTIONS_FILE = DATA_DIR / "sections.yaml"
METADATA_FILE = DATA_DIR / "metadata.json"

MARKETS = {"equities", "crypto", "futures", "options", "forex", "prediction-markets", "multi-asset"}
MODES = {"live", "paper", "research", "library"}
STALE_DAYS = 180

API = "https://api.github.com"


class DataError(ValueError):
    pass


def load_yaml(path: Path) -> Any:
    with path.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def load_sections() -> list[dict]:
    sections = load_yaml(SECTIONS_FILE)
    if not isinstance(sections, list) or not sections:
        raise DataError(f"{SECTIONS_FILE}: expected a non-empty list")
    keys = [s.get("key") for s in sections]
    if len(keys) != len(set(keys)):
        raise DataError(f"{SECTIONS_FILE}: duplicate section keys")
    return sections


def load_entries() -> list[dict]:
    entries = load_yaml(ENTRIES_FILE) or []
    if not isinstance(entries, list):
        raise DataError(f"{ENTRIES_FILE}: expected a list")
    return entries


def validate(entries: list[dict], sections: list[dict]) -> list[str]:
    """Return a list of human-readable problems; empty means valid."""
    problems: list[str] = []
    keys = {s["key"] for s in sections}
    seen_targets: dict[str, str] = {}
    for i, e in enumerate(entries):
        where = f"entry {i + 1} ({e.get('name', '?')})"
        for field in ("name", "section", "description"):
            if not e.get(field):
                problems.append(f"{where}: missing `{field}`")
        if e.get("section") not in keys:
            problems.append(f"{where}: unknown section `{e.get('section')}`")
        if not e.get("repo") and not e.get("url"):
            problems.append(f"{where}: needs `repo` (owner/name) or `url`")
        if e.get("repo") and e["repo"].count("/") != 1:
            problems.append(f"{where}: `repo` must be owner/name")
        desc = str(e.get("description", ""))
        if desc and not desc.rstrip().endswith((".", "。")):
            problems.append(f"{where}: description should end with a full stop")
        # Code entries get one line; incidents, papers and rules may need a second sentence.
        limit = 260 if e.get("repo") else 420
        if len(desc) > limit:
            problems.append(f"{where}: description over {limit} characters ({len(desc)})")
        for m in e.get("markets", []) or []:
            if m not in MARKETS:
                problems.append(f"{where}: unknown market `{m}` (allowed: {sorted(MARKETS)})")
        if e.get("mode") and e["mode"] not in MODES:
            problems.append(f"{where}: unknown mode `{e['mode']}` (allowed: {sorted(MODES)})")
        target = entry_url(e).lower().rstrip("/")
        if target in seen_targets:
            problems.append(f"{where}: duplicate of {seen_targets[target]}")
        seen_targets[target] = where
    return problems


def entry_url(e: dict) -> str:
    return e.get("url") or f"https://github.com/{e['repo']}"


def load_metadata() -> dict[str, dict]:
    if METADATA_FILE.exists():
        return json.loads(METADATA_FILE.read_text(encoding="utf-8"))
    return {}


def save_metadata(meta: dict[str, dict]) -> None:
    METADATA_FILE.write_text(json.dumps(meta, indent=2, sort_keys=True) + "\n", encoding="utf-8")


# --------------------------------------------------------------------------- #
# GitHub API
# --------------------------------------------------------------------------- #

def gh_get(path: str, params: Optional[dict] = None, retries: int = 3) -> Any:
    url = API + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "awesome-agentic-trading"}
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    for attempt in range(retries):
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as err:
            if err.code == 404:
                return None
            if err.code in (403, 429) and attempt < retries - 1:
                reset = err.headers.get("X-RateLimit-Reset")
                wait = max(5, int(reset) - int(time.time())) if reset else 30
                print(f"rate limited, sleeping {wait}s", file=sys.stderr)
                time.sleep(min(wait, 120))
                continue
            raise
    return None


def days_since(iso: Optional[str]) -> Optional[int]:
    if not iso:
        return None
    dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    return (datetime.now(timezone.utc) - dt).days
