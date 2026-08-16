#!/usr/bin/env python3
"""Safe-fallback checks for deep links to unknown Featured Work slugs.

For each bogus ?work=<slug> deep link this verifies:
  - the page renders normally (hero, Featured Work carousel, footer all present);
  - no lightbox/dialog opens;
  - no uncaught page errors or console errors are emitted;
  - the stale ?work param is stripped from the URL while the #work hash is kept;
  - a real project link still works afterwards (the app is not wedged).

Usage:
    python3 tests/footer-work-invalid-slug.py
    python3 tests/footer-work-invalid-slug.py --base-url http://localhost:3000
    python3 tests/footer-work-invalid-slug.py --report tests/report-footer-invalid-slug.json
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

BAD_SLUGS = [
    "does-not-exist",
    "hollow-roasters-typo",
    "Heartland Plein Air Festival",  # display title instead of a slug
    "../../etc/passwd",
    "<script>alert(1)</script>",
    "",  # ?work= with an empty value
]

IGNORED_CONSOLE = ("favicon", "Download the React DevTools", "[vite]")

parser = argparse.ArgumentParser(description="Unknown work slug fallback checks")
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


async def check_bad_slug(context, slug: str) -> list[str]:
    failures: list[str] = []
    errors: list[str] = []
    page = await context.new_page()
    page.on("pageerror", lambda exc: errors.append(f"pageerror: {exc}"))
    page.on(
        "console",
        lambda msg: errors.append(f"console.{msg.type}: {msg.text}")
        if msg.type == "error" and not any(s in msg.text for s in IGNORED_CONSOLE)
        else None,
    )

    from urllib.parse import quote

    url = f"{BASE_URL}/?work={quote(slug, safe='')}#work"
    await page.goto(url, wait_until="domcontentloaded")
    await stabilize(page)

    # 1. The page still renders its real content.
    for selector, label in (
        ("h1", "hero H1"),
        ("#featured-work-track", "Featured Work carousel"),
        ("footer#contact a", "footer links"),
    ):
        if await page.locator(selector).count() == 0:
            failures.append(f"{slug!r}: {label} missing — page did not render safely")

    # 2. No lightbox opened.
    if await page.locator('[role="dialog"]').count() > 0:
        failures.append(f"{slug!r}: a lightbox opened for an unknown slug")

    # 3. The stale param is cleared, the hash is preserved.
    await page.wait_for_timeout(400)
    parsed = urlparse(page.url)
    if "work" in parse_qs(parsed.query):
        failures.append(f"{slug!r}: stale ?work param was not cleared ({page.url})")
    if parsed.fragment != "work":
        failures.append(f"{slug!r}: #work hash was lost (url is {page.url})")

    # 4. No runtime errors.
    if errors:
        failures.append(f"{slug!r}: runtime errors -> {errors[:3]}")

    await page.close()
    return failures


async def check_recovery(context, project: dict) -> list[str]:
    """After a bad slug, a real footer link must still open the right lightbox."""
    page = await context.new_page()
    await page.goto(f"{BASE_URL}/?work=nope#work", wait_until="domcontentloaded")
    await stabilize(page)

    link = page.locator(f'footer#contact a:text-is("{project["name"]}")')
    if await link.count() == 0:
        await page.close()
        return [f"recovery: footer link for {project['name']!r} missing after bad slug"]

    await link.first.scroll_into_view_if_needed()
    await link.first.click()
    try:
        await page.wait_for_selector('[role="dialog"]', timeout=6000)
    except Exception:
        await page.close()
        return ["recovery: lightbox did not open after an unknown-slug deep link"]

    title = await page.evaluate(
        """() => {
             const d = document.querySelector('[role="dialog"]');
             const t = d && d.querySelector('h2');
             return t ? t.textContent.trim() : null;
           }"""
    )
    await page.close()
    if title != project["name"]:
        return [f"recovery: lightbox showed {title!r}, expected {project['name']!r}"]
    return []


async def main() -> int:
    wait_for_server(BASE_URL)
    projects = load_projects()
    REPORTS.mkdir(parents=True, exist_ok=True)

    results: list[dict] = []
    all_failures: list[str] = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1280, "height": 900})

        for slug in BAD_SLUGS:
            failures = await check_bad_slug(context, slug)
            results.append({"case": slug or "(empty)", "passed": not failures, "failures": failures})
            all_failures += failures

        recovery = await check_recovery(context, projects[0])
        results.append({"case": "recovery", "passed": not recovery, "failures": recovery})
        all_failures += recovery

        await context.close()
        await browser.close()

    report = {"base_url": BASE_URL, "passed": not all_failures, "results": results}
    report_path = Path(args.report) if args.report else REPORTS / "footer-invalid-slug.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2))

    for result in results:
        print(f"{'PASS' if result['passed'] else 'FAIL'} {result['case']}")
        for failure in result["failures"]:
            print(f"      - {failure}")

    if all_failures:
        print(f"\n{len(all_failures)} failure(s)")
        return 1
    print("\nUnknown work slugs fall back safely.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
