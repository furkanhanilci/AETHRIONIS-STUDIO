#!/usr/bin/env python3
"""Visual QA: screenshots and the accessibility checks that can be automated.

The design system asks for screenshot regression, narrow widths, and checks that
status is never colour alone. Playwright is not installed here and Chrome is, so
the capture uses headless Chrome directly — the point is the regression, not the
driver.

What this cannot check is whether the result looks right. That is a person's
job, and the checklist below is the part a machine can hold.
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SHOTS = ROOT / "docs" / "screenshots"
BASE = "http://127.0.0.1:8100"

# Every surface, at the mockup's size and at a narrow width where the inspector
# and context rail are supposed to fall away.
SURFACES = [
    ("home", "/", (1672, 941)),
    ("dume-control", "/dume?channel=control", (1672, 941)),
    ("dume-review", "/dume?channel=review", (1672, 941)),
    ("wp-list", "/dume/wp", (1672, 941)),
    ("wp-specification", "/dume/wp?id=WP-001&tab=specification", (1672, 941)),
    ("wp-evidence", "/dume/wp?id=WP-001&tab=evidence", (1672, 941)),
    ("wp-gate", "/dume/wp?id=WP-001&tab=gate", (1672, 941)),
    ("wp-history", "/dume/wp?id=WP-001&tab=history", (1672, 941)),
    ("agents", "/agents", (1672, 941)),
    ("models", "/models", (1672, 941)),
    ("activity", "/activity", (1672, 941)),
    ("research", "/projects", (1672, 941)),
    ("dume-narrow", "/dume", (980, 900)),
    ("dume-mobile", "/dume", (760, 900)),
]


def capture(name: str, path: str, size: tuple[int, int]) -> Path:
    SHOTS.mkdir(parents=True, exist_ok=True)
    out = SHOTS / f"{name}.png"
    subprocess.run(
        ["google-chrome", "--headless=new", "--disable-gpu", "--hide-scrollbars",
         f"--window-size={size[0]},{size[1]}", f"--screenshot={out}",
         BASE + path],
        capture_output=True, timeout=90)
    return out


def fetch(path: str) -> str:
    with urllib.request.urlopen(BASE + path, timeout=10) as response:
        return response.read().decode()


def accessibility(html: str, surface: str) -> list[str]:
    """The checks a machine can make honestly."""
    problems = []

    # Every image needs alt text, even the decorative ones — an empty alt is a
    # decision, a missing one is an omission.
    for tag in re.findall(r"<img[^>]*>", html):
        if "alt=" not in tag:
            problems.append(f"{surface}: an <img> has no alt attribute")

    # Status must never be colour alone. Any element carrying a semantic colour
    # has to contain readable text.
    for match in re.finditer(r'<span class="pill"[^>]*>(.*?)</span>', html, re.S):
        if not match.group(1).strip():
            problems.append(f"{surface}: a status pill has colour but no text")

    # The rails are navigation and should say so.
    if 'aria-label="Primary"' not in html and surface != "narrow":
        problems.append(f"{surface}: the primary rail has no accessible name")

    # A page needs exactly one h1.
    h1s = len(re.findall(r"<h1[ >]", html))
    if h1s != 1:
        problems.append(f"{surface}: {h1s} <h1> elements, expected 1")

    if "<title>" not in html:
        problems.append(f"{surface}: no document title")
    return problems


def main() -> int:
    manifest = {}
    problems: list[str] = []
    for name, path, size in SURFACES:
        shot = capture(name, path, size)
        if not shot.is_file():
            problems.append(f"{name}: no screenshot produced")
            continue
        digest = hashlib.sha256(shot.read_bytes()).hexdigest()
        manifest[name] = {"path": path, "size": list(size),
                          "bytes": shot.stat().st_size, "sha256": digest[:16]}
        if not name.endswith(("narrow", "mobile")):
            problems.extend(accessibility(fetch(path), name))

    index = SHOTS / "manifest.json"
    previous = json.loads(index.read_text()) if index.is_file() else {}
    changed = [n for n, v in manifest.items()
               if previous.get(n, {}).get("sha256") not in (None, v["sha256"])]
    index.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")

    print(f"{len(manifest)} surface(s) captured into {SHOTS}")
    if changed:
        print(f"changed since the last run: {', '.join(sorted(changed))}")
    elif previous:
        print("no visual change")
    if problems:
        print(f"\n{len(problems)} accessibility finding(s):")
        for problem in problems:
            print(f"  · {problem}")
        return 1
    print("accessibility checks pass")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
