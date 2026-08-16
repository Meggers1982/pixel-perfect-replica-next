#!/usr/bin/env python3
"""End-to-end checks that every footer Work link resolves and opens the right lightbox.

For each project exported from lib/projects.ts this verifies:
  - a footer Work link exists with the project's display title;
  - clicking it navigates to /?work=<slug>#work (correct route + search param);
  - the lightbox opens and shows that project's category, title and note;
  - the lightbox accessible name matches the project;
  - the same deep link works on a cold page load (direct navigation);
  - closing the lightbox clears the ?work param.

Project data is read straight from lib/projects.ts (via node) so this test
fails whenever the footer and the shared data drift apart.

Usage:
    python3 tests/footer-work-links.py
    python3 tests/footer-work-links.py --base-url http://localhost:3000
    python3 tests/footer-work-links.py --report tests/report-footer-work-links.json
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

parser = argparse.ArgumentParser(description="Footer Work link routing + lightbox checks")
parser.add_argument("base_url", nargs="?", default="http://localhost:3000")
parser.add_argument("--base-url", dest="base_url_opt", default=None)
parser.add_argument("--report", default=None)
args = parser.parse_args()

BASE_URL = (args.base_url_opt or args.base_url).rstrip("/")


def load_projects() -> list[dict]:
    """Read the shared projects array from lib/projects.ts."""
    script = (
        'const m = await import("./lib/projects.ts");'
        "console.log(JSON.stringify(m.projects));"
    )
    out = subprocess.run(
        ["node", "--input-type=module", "-e", script],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=True,
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
    await page.wait_for_selector("footer#contact a")


async def read_lightbox(page) -> dict | None:
    return await page.evaluate(
        """() => {
          const dialog = document.querySelector('[role="dialog"][data-state="open"]')
            || document.querySelector('[role="dialog"]');
          if (!dialog) return null;
          const title = dialog.querySelector('h2, [id^="radix"][class*="display"]');
          const body = dialog.innerText || '';
          return {
            ariaLabel: dialog.getAttribute('aria-label'),
            text: body.replace(/\\s+/g, ' ').trim(),
            titleText: title ? title.textContent.trim() : null,
          };
        }"""
    )


async def close_lightbox(page) -> None:
    await page.keyboard.press("Escape")
    try:
        await page.wait_for_function(
            "() => !document.querySelector('[role=\"dialog\"]')", timeout=4000
        )
    except Exception:
        pass


async def check_project_via_footer(page, project: dict) -> list[str]:
    failures: list[str] = []
    name = project["name"]
    slug = project["slug"]

    await page.goto(BASE_URL, wait_until="domcontentloaded")
    await stabilize(page)

    link = page.locator(f'footer#contact a:text-is("{name}")')
    if await link.count() == 0:
        return [f"{slug}: no footer Work link with text {name!r}"]

    href = await link.first.get_attribute("href")
    expected_href = f"/?work={slug}#work"
    if href != expected_href:
        failures.append(f"{slug}: footer href is {href!r}, expected {expected_href!r}")

    await link.first.scroll_into_view_if_needed()
    await link.first.click()

    try:
        await page.wait_for_selector('[role="dialog"]', timeout=6000)
    except Exception:
        return failures + [f"{slug}: clicking the footer link did not open the lightbox"]

    parsed = urlparse(page.url)
    query = parse_qs(parsed.query)
    if query.get("work", [None])[0] != slug:
        failures.append(f"{slug}: url after click is {page.url} (missing ?work={slug})")
    if parsed.fragment != "work":
        failures.append(f"{slug}: url fragment is {parsed.fragment!r}, expected 'work'")

    info = await read_lightbox(page)
    if info is None:
        failures.append(f"{slug}: lightbox content could not be read")
    else:
        if info["titleText"] != name:
            failures.append(
                f"{slug}: lightbox title is {info['titleText']!r}, expected {name!r}"
            )
        haystack = info["text"].lower()
        if project["category"].lower() not in haystack:
            failures.append(f"{slug}: lightbox is missing category {project['category']!r}")
        if project["note"][:40].lower() not in haystack:
            failures.append(f"{slug}: lightbox is missing the project note")
        if name not in (info["ariaLabel"] or ""):
            failures.append(
                f"{slug}: dialog accessible name {info['ariaLabel']!r} does not name the project"
            )

    await close_lightbox(page)
    if "work=" in page.url:
        failures.append(f"{slug}: closing the lightbox left ?work in the url ({page.url})")

    return failures


async def check_project_deep_link(page, project: dict) -> list[str]:
    failures: list[str] = []
    slug = project["slug"]
    await page.goto(f"{BASE_URL}/?work={slug}#work", wait_until="domcontentloaded")
    await stabilize(page)
    try:
        await page.wait_for_selector('[role="dialog"]', timeout=6000)
    except Exception:
        return [f"{slug}: deep link did not open the lightbox on a cold load"]

    info = await read_lightbox(page)
    if info is None or info["titleText"] != project["name"]:
        failures.append(
            f"{slug}: deep link opened {info['titleText'] if info else None!r}, "
            f"expected {project['name']!r}"
        )
    await close_lightbox(page)
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
            failures = await check_project_via_footer(page, project)
            failures += await check_project_deep_link(page, project)
            results.append(
                {"slug": project["slug"], "passed": not failures, "failures": failures}
            )
            all_failures += failures

        await context.close()
        await browser.close()

    report = {
        "base_url": BASE_URL,
        "project_count": len(projects),
        "passed": not all_failures,
        "results": results,
    }
    report_path = Path(args.report) if args.report else REPORTS / "footer-work-links.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2))

    for result in results:
        print(f"{'PASS' if result['passed'] else 'FAIL'} {result['slug']}")
        for failure in result["failures"]:
            print(f"      - {failure}")

    if all_failures:
        print(f"\n{len(all_failures)} failure(s)")
        return 1
    print(f"\nAll {len(projects)} footer Work links resolve to the correct lightbox.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
