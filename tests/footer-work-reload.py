#!/usr/bin/env python3
"""Reload/restore checks for the Featured Work lightbox deep link.

For every project in lib/projects.ts this loads /?work=<slug>#work, then
reloads the page, and verifies:
  - the lightbox is restored with that project's category, title and note;
  - the dialog accessible name names the project;
  - focus moves into the dialog on restore (not left on <body>);
  - Tab keeps focus trapped inside the dialog;
  - pressing Escape closes it and returns focus to that project's carousel card;
  - the restored URL keeps ?work=<slug> and the #work hash.

Usage:
    python3 tests/footer-work-reload.py
    python3 tests/footer-work-reload.py --base-url http://localhost:3000
    python3 tests/footer-work-reload.py --report tests/report-footer-work-reload.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from urllib.request import urlopen

from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = ROOT.parent
REPORTS = ROOT / "report"

parser = argparse.ArgumentParser(description="Lightbox deep-link reload checks")
parser.add_argument("base_url", nargs="?", default="http://localhost:3000")
parser.add_argument("--base-url", dest="base_url_opt", default=None)
parser.add_argument("--report", default=None)
args = parser.parse_args()

BASE_URL = (args.base_url_opt or args.base_url).rstrip("/")


def load_projects() -> list[dict]:
    script = (
        'const m = await import("./lib/projects.ts");'
        "console.log(JSON.stringify(m.projects));"
    )
    out = subprocess.run(
        ["node", "--input-type=module", "-e", script], cwd=PROJECT_ROOT, capture_output=True, text=True, check=True
    )
    return json.loads(out.stdout.strip().splitlines()[-1])


def wait_for_server(url: str, attempts: int = 30) -> None:
    for _ in range(attempts):
        try:
            urlopen(url, timeout=2).read(1)
            return
        except Exception:
            time.sleep(1)
    raise SystemExit(f"dev server never came up at {url}")


async def stabilize(page) -> None:
    await page.add_style_tag(
        content="*,*::before,*::after{animation:none!important;transition:none!important}"
    )
    await page.evaluate("document.fonts ? document.fonts.ready : null")
    await page.wait_for_load_state("networkidle")


async def dialog_state(page) -> dict | None:
    return await page.evaluate(
        """() => {
          const dialog = document.querySelector('[role="dialog"]');
          if (!dialog) return null;
          const title = dialog.querySelector('h2');
          const active = document.activeElement;
          return {
            ariaLabel: dialog.getAttribute('aria-label'),
            titleText: title ? title.textContent.trim() : null,
            text: (dialog.innerText || '').replace(/\\s+/g, ' ').trim().toLowerCase(),
            focusInside: !!(active && dialog.contains(active)),
            focusTag: active ? active.tagName.toLowerCase() : null,
            focusLabel: active
              ? (active.getAttribute('aria-label') || (active.textContent || '').trim()).slice(0, 60)
              : null,
          };
        }"""
    )


async def check_project(page, project: dict) -> list[str]:
    failures: list[str] = []
    slug, name = project["slug"], project["name"]
    url = f"{BASE_URL}/?work={slug}#work"

    await page.goto(url, wait_until="domcontentloaded")
    await stabilize(page)
    try:
        await page.wait_for_selector('[role="dialog"]', timeout=6000)
    except Exception:
        return [f"{slug}: lightbox did not open on first load"]

    # Reload the very same URL — this is the case under test.
    await page.reload(wait_until="domcontentloaded")
    await stabilize(page)
    try:
        await page.wait_for_selector('[role="dialog"]', timeout=6000)
    except Exception:
        return [f"{slug}: lightbox was not restored after reload"]

    # Give Radix a tick to move focus into the dialog.
    await page.wait_for_timeout(300)
    state = await dialog_state(page)
    if state is None:
        return [f"{slug}: dialog vanished right after reload"]

    if state["titleText"] != name:
        failures.append(f"{slug}: restored title is {state['titleText']!r}, expected {name!r}")
    if project["category"].lower() not in state["text"]:
        failures.append(f"{slug}: restored lightbox is missing category {project['category']!r}")
    if project["note"][:40].lower() not in state["text"]:
        failures.append(f"{slug}: restored lightbox is missing the project note")
    if name not in (state["ariaLabel"] or ""):
        failures.append(
            f"{slug}: dialog accessible name {state['ariaLabel']!r} does not name the project"
        )
    if not state["focusInside"]:
        failures.append(
            f"{slug}: focus after reload is on <{state['focusTag']}> outside the dialog"
        )

    parsed = urlparse(page.url)
    if parse_qs(parsed.query).get("work", [None])[0] != slug:
        failures.append(f"{slug}: reload lost ?work={slug} (url is {page.url})")
    if parsed.fragment != "work":
        failures.append(f"{slug}: reload lost the #work hash (url is {page.url})")

    # Focus stays trapped while tabbing.
    for _ in range(6):
        await page.keyboard.press("Tab")
    trapped = await page.evaluate(
        """() => {
          const dialog = document.querySelector('[role="dialog"]');
          return !!(dialog && document.activeElement && dialog.contains(document.activeElement));
        }"""
    )
    if not trapped:
        failures.append(f"{slug}: focus escaped the dialog while tabbing after reload")

    # Escape closes and returns focus to the matching carousel card.
    await page.keyboard.press("Escape")
    try:
        await page.wait_for_function(
            "() => !document.querySelector('[role=\"dialog\"]')", timeout=4000
        )
    except Exception:
        failures.append(f"{slug}: Escape did not close the restored lightbox")
        return failures

    await page.wait_for_timeout(200)
    returned = await page.evaluate(
        """() => {
          const el = document.activeElement;
          if (!el) return null;
          return {
            tag: el.tagName.toLowerCase(),
            label: el.getAttribute('aria-label') || (el.textContent || '').trim(),
            inTrack: !!el.closest('#featured-work-track'),
          };
        }"""
    )
    if not returned or not returned["inTrack"]:
        failures.append(
            f"{slug}: focus after close is {returned!r}, expected the project's carousel card"
        )
    elif name not in (returned["label"] or ""):
        failures.append(
            f"{slug}: focus returned to {returned['label']!r}, expected the {name!r} card"
        )

    return failures


async def main() -> int:
    wait_for_server(BASE_URL)
    projects = load_projects()
    REPORTS.mkdir(parents=True, exist_ok=True)

    results: list[dict] = []
    all_failures: list[str] = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1280, "height": 900})
        page = await context.new_page()

        for project in projects:
            failures = await check_project(page, project)
            results.append(
                {"slug": project["slug"], "passed": not failures, "failures": failures}
            )
            all_failures += failures

        await context.close()
        await browser.close()

    report = {"base_url": BASE_URL, "passed": not all_failures, "results": results}
    report_path = Path(args.report) if args.report else REPORTS / "footer-work-reload.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2))

    for result in results:
        print(f"{'PASS' if result['passed'] else 'FAIL'} {result['slug']}")
        for failure in result["failures"]:
            print(f"      - {failure}")

    if all_failures:
        print(f"\n{len(all_failures)} failure(s)")
        return 1
    print(f"\nReloading a deep link restores all {len(projects)} lightboxes with correct focus.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
