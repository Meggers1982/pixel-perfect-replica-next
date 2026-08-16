#!/usr/bin/env python3
"""Browser back/forward must keep the Featured Work lightbox in sync with the URL.

The test builds a real history stack by clicking footer Work links and closing the
lightbox, then walks the whole stack backwards and forwards. At every stop it asserts
the UI matches the URL:
  - ?work=<known slug>  -> lightbox open with that project's title/category/note
  - no ?work            -> no lightbox anywhere in the DOM
It also checks focus lands inside the dialog when history restores one, that no stale
project content is shown after a back/forward, and that no console/page errors fire.

Usage:
    python3 tests/footer-work-history.py
    python3 tests/footer-work-history.py --base-url http://localhost:3000
    python3 tests/footer-work-history.py --report tests/report-footer-work-history.json
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

parser = argparse.ArgumentParser(description="Back/forward lightbox state checks")
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
    await page.wait_for_selector("footer#contact a")


def slug_in_url(url: str) -> str | None:
    return parse_qs(urlparse(url).query).get("work", [None])[0]


async def snapshot(page) -> dict:
    return await page.evaluate(
        """() => {
          const dialog = document.querySelector('[role="dialog"]');
          const active = document.activeElement;
          return {
            open: !!dialog,
            titleText: dialog && dialog.querySelector('h2')
              ? dialog.querySelector('h2').textContent.trim() : null,
            text: dialog ? (dialog.innerText || '').replace(/\\s+/g, ' ').trim() : '',
            imgAlt: dialog && dialog.querySelector('img')
              ? dialog.querySelector('img').getAttribute('alt') : null,
            focusInside: !!(dialog && active && dialog.contains(active)),
          };
        }"""
    )


async def settle(page, want_open: bool) -> None:
    """Wait for the DOM to agree with the expected open/closed state."""
    try:
        await page.wait_for_function(
            "(want) => !!document.querySelector('[role=\"dialog\"]') === want",
            arg=want_open,
            timeout=5000,
        )
    except Exception:
        pass
    await page.wait_for_timeout(250)


async def assert_matches_url(page, projects: list[dict], label: str) -> list[str]:
    """The UI must match whatever ?work is in the current URL."""
    failures: list[str] = []
    slug = slug_in_url(page.url)
    known = next((p for p in projects if p["slug"] == slug), None)
    await settle(page, want_open=known is not None)
    state = await snapshot(page)

    if known is None:
        if state["open"]:
            failures.append(
                f"{label}: url has no known ?work ({page.url}) but a lightbox is open "
                f"showing {state['titleText']!r}"
            )
        return failures

    if not state["open"]:
        return [f"{label}: url is ?work={slug} but no lightbox is open"]

    text_lower = state["text"].lower()
    if state["titleText"] != known["name"]:
        failures.append(
            f"{label}: lightbox shows {state['titleText']!r}, expected {known['name']!r}"
        )
    if known["category"].lower() not in text_lower:
        failures.append(f"{label}: missing category {known['category']!r}")
    if known["note"][:40].lower() not in text_lower:
        failures.append(f"{label}: missing the {slug!r} note")
    if state["imgAlt"] != known["alt"]:
        failures.append(f"{label}: image alt is {state['imgAlt']!r}, expected the {slug!r} alt")
    for other in projects:
        if other["slug"] == slug:
            continue
        if other["name"].lower() in text_lower or other["note"][:40].lower() in text_lower:
            failures.append(f"{label}: stale content from {other['slug']!r} still visible")
    if not state["focusInside"]:
        failures.append(f"{label}: history restored the lightbox but focus is outside it")
    return failures


async def main() -> int:
    wait_for_server(BASE_URL)
    projects = load_projects()
    REPORTS.mkdir(parents=True, exist_ok=True)

    console_errors: list[str] = []
    steps: list[dict] = []
    all_failures: list[str] = []

    def record(label: str, url: str, failures: list[str]) -> None:
        steps.append({"label": label, "url": url, "passed": not failures, "failures": failures})
        all_failures.extend(failures)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1280, "height": 900})
        page = await context.new_page()
        page.on(
            "console",
            lambda msg: console_errors.append(msg.text) if msg.type == "error" else None,
        )
        page.on("pageerror", lambda err: console_errors.append(str(err)))

        await page.goto(BASE_URL, wait_until="domcontentloaded")
        await stabilize(page)

        # --- Build a history stack: open + close each project from the footer. ---
        for project in projects:
            link = page.locator(f'footer#contact a:text-is("{project["name"]}")')
            if await link.count() == 0:
                record(f"setup {project['slug']}", page.url, ["footer Work link not found"])
                continue
            await link.first.scroll_into_view_if_needed()
            await link.first.click()
            await settle(page, want_open=True)
            record(
                f"open {project['slug']}",
                page.url,
                await assert_matches_url(page, projects, f"open {project['slug']}"),
            )
            await page.keyboard.press("Escape")
            await settle(page, want_open=False)
            record(
                f"close {project['slug']}",
                page.url,
                await assert_matches_url(page, projects, f"close {project['slug']}"),
            )

        # --- Walk all the way back, checking each stop. ---
        back_stops = 0
        for i in range(len(projects) * 3):
            before = page.url
            await page.go_back()
            await page.wait_for_timeout(200)
            if page.url == before:
                break
            back_stops += 1
            record(
                f"back #{back_stops}",
                page.url,
                await assert_matches_url(page, projects, f"back #{back_stops}"),
            )
        if back_stops == 0:
            all_failures.append("history: going back never changed the URL")

        # --- And forward again. ---
        for i in range(back_stops):
            before = page.url
            await page.go_forward()
            await page.wait_for_timeout(200)
            if page.url == before:
                break
            record(
                f"forward #{i + 1}",
                page.url,
                await assert_matches_url(page, projects, f"forward #{i + 1}"),
            )

        # --- Back once more, then open a project again: state must not be stale. ---
        await page.go_back()
        await page.wait_for_timeout(300)
        record(
            "back after forward",
            page.url,
            await assert_matches_url(page, projects, "back after forward"),
        )

        # If history left a lightbox open, close it before touching the footer again.
        if await page.locator('[role="dialog"]').count():
            await page.keyboard.press("Escape")
            await settle(page, want_open=False)

        last = projects[-1]
        link = page.locator(f'footer#contact a:text-is("{last["name"]}")')
        if await link.count():
            await link.first.scroll_into_view_if_needed()
            await link.first.click()
            await settle(page, want_open=True)
            record(
                f"reopen {last['slug']}",
                page.url,
                await assert_matches_url(page, projects, f"reopen {last['slug']}"),
            )

        await context.close()
        await browser.close()

    if console_errors:
        all_failures.append(f"console/page errors: {console_errors[:5]}")

    report = {
        "base_url": BASE_URL,
        "passed": not all_failures,
        "console_errors": console_errors,
        "steps": steps,
    }
    report_path = Path(args.report) if args.report else REPORTS / "footer-work-history.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2))

    for step in steps:
        print(f"{'PASS' if step['passed'] else 'FAIL'} {step['label']:<28} {step['url']}")
        for failure in step["failures"]:
            print(f"      - {failure}")

    if all_failures:
        print(f"\n{len(all_failures)} failure(s)")
        return 1
    print(f"\nBack/forward keeps the lightbox in sync across {len(steps)} history stops.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
