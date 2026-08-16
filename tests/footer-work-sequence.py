#!/usr/bin/env python3
"""Sequential footer Work link clicks must never show stale lightbox content.

On a single page load this walks a sequence of footer Work links (forward, then
reverse, then a repeat/alternating pass) and after each click verifies:
  - the lightbox shows the clicked project's category, title, note, image and alt;
  - no other project's title or note is present (no stale content);
  - the dialog accessible name matches the clicked project;
  - the URL is /?work=<slug>#work;
  - focus is inside the dialog, and Escape returns focus to that project's card.

Usage:
    python3 tests/footer-work-sequence.py
    python3 tests/footer-work-sequence.py --base-url http://localhost:3000
    python3 tests/footer-work-sequence.py --report tests/report-footer-work-sequence.json
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

parser = argparse.ArgumentParser(description="Sequential footer Work link lightbox checks")
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


async def read_lightbox(page) -> dict | None:
    return await page.evaluate(
        """() => {
          const dialog = document.querySelector('[role="dialog"]');
          if (!dialog) return null;
          const title = dialog.querySelector('h2');
          const img = dialog.querySelector('img');
          const active = document.activeElement;
          return {
            ariaLabel: dialog.getAttribute('aria-label') || '',
            titleText: title ? title.textContent.trim() : null,
            text: (dialog.innerText || '').replace(/\\s+/g, ' ').trim(),
            imgSrc: img ? img.getAttribute('src') : null,
            imgAlt: img ? img.getAttribute('alt') : null,
            focusInside: !!(active && dialog.contains(active)),
            focusTag: active ? active.tagName.toLowerCase() : null,
          };
        }"""
    )


async def close_and_check_focus(page, project: dict) -> list[str]:
    failures: list[str] = []
    await page.keyboard.press("Escape")
    try:
        await page.wait_for_function(
            "() => !document.querySelector('[role=\"dialog\"]')", timeout=4000
        )
    except Exception:
        return [f"{project['slug']}: Escape did not close the lightbox"]

    await page.wait_for_timeout(150)
    focused = await page.evaluate(
        """() => {
          const el = document.activeElement;
          if (!el) return null;
          return {
            label: el.getAttribute('aria-label') || (el.textContent || '').trim(),
            inTrack: !!el.closest('#featured-work-track'),
          };
        }"""
    )
    if not focused or not focused["inTrack"]:
        failures.append(
            f"{project['slug']}: after close focus is {focused!r}, expected its carousel card"
        )
    elif project["name"] not in (focused["label"] or ""):
        failures.append(
            f"{project['slug']}: focus returned to {focused['label']!r}, "
            f"expected the {project['name']!r} card"
        )

    query = parse_qs(urlparse(page.url).query)
    if "work" in query:
        failures.append(f"{project['slug']}: ?work not cleared after close (url {page.url})")
    return failures


async def open_via_footer(page, project: dict, others: list[dict], step: int) -> list[str]:
    failures: list[str] = []
    slug, name = project["slug"], project["name"]
    tag = f"step {step} ({slug})"

    link = page.locator(f'footer#contact a:text-is("{name}")')
    if await link.count() == 0:
        return [f"{tag}: no footer Work link with text {name!r}"]

    await link.first.scroll_into_view_if_needed()
    await link.first.click()

    try:
        await page.wait_for_function(
            """(expected) => {
              const d = document.querySelector('[role="dialog"]');
              const h = d && d.querySelector('h2');
              return !!h && h.textContent.trim() === expected;
            }""",
            arg=name,
            timeout=6000,
        )
    except Exception:
        state = await read_lightbox(page)
        return [
            f"{tag}: lightbox did not show {name!r} after click "
            f"(showing {state['titleText'] if state else None!r})"
        ]

    await page.wait_for_timeout(250)
    state = await read_lightbox(page)
    if state is None:
        return [f"{tag}: dialog disappeared"]

    text_lower = state["text"].lower()
    if project["category"].lower() not in text_lower:
        failures.append(f"{tag}: missing category {project['category']!r}")
    if project["note"][:40].lower() not in text_lower:
        failures.append(f"{tag}: missing the project note")
    if name not in state["ariaLabel"]:
        failures.append(f"{tag}: dialog accessible name {state['ariaLabel']!r} is wrong")
    if state["imgAlt"] != project["alt"]:
        failures.append(f"{tag}: image alt is {state['imgAlt']!r}, expected the project alt")
    img_key = project["image"].split("/")[-1].split("?")[0]
    if img_key and state["imgSrc"] and img_key not in state["imgSrc"]:
        failures.append(f"{tag}: stale image src {state['imgSrc']!r}, expected {img_key!r}")

    # No other project's content may linger in the dialog.
    for other in others:
        if other["slug"] == slug:
            continue
        if other["name"].lower() in text_lower:
            failures.append(f"{tag}: stale title {other['name']!r} still visible")
        if other["note"][:40].lower() in text_lower:
            failures.append(f"{tag}: stale note from {other['slug']!r} still visible")
        if other["alt"] == state["imgAlt"]:
            failures.append(f"{tag}: stale image alt from {other['slug']!r}")

    parsed = urlparse(page.url)
    if parse_qs(parsed.query).get("work", [None])[0] != slug:
        failures.append(f"{tag}: url is {page.url}, expected ?work={slug}")
    if parsed.fragment != "work":
        failures.append(f"{tag}: url fragment is {parsed.fragment!r}, expected 'work'")
    if not state["focusInside"]:
        failures.append(f"{tag}: focus is on <{state['focusTag']}> outside the dialog")

    return failures


def build_sequence(projects: list[dict]) -> list[dict]:
    forward = list(projects)
    reverse = list(reversed(projects))
    alternating: list[dict] = []
    for i in range(len(projects)):
        alternating.append(projects[i])
        alternating.append(projects[0])
    return forward + reverse + alternating


async def main() -> int:
    wait_for_server(BASE_URL)
    projects = load_projects()
    sequence = build_sequence(projects)
    REPORTS.mkdir(parents=True, exist_ok=True)

    console_errors: list[str] = []
    results: list[dict] = []
    all_failures: list[str] = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1280, "height": 900})
        page = await context.new_page()
        page.on(
            "console",
            lambda msg: console_errors.append(msg.text) if msg.type == "error" else None,
        )
        page.on("pageerror", lambda err: console_errors.append(str(err)))

        # One page load for the whole sequence — that is the point of the test.
        await page.goto(BASE_URL, wait_until="domcontentloaded")
        await stabilize(page)

        for step, project in enumerate(sequence, start=1):
            failures = await open_via_footer(page, project, projects, step)
            if not failures or "did not show" not in failures[0]:
                failures += await close_and_check_focus(page, project)
            results.append(
                {"step": step, "slug": project["slug"], "passed": not failures, "failures": failures}
            )
            all_failures += failures

        await context.close()
        await browser.close()

    if console_errors:
        all_failures.append(f"console/page errors during sequence: {console_errors[:5]}")

    report = {
        "base_url": BASE_URL,
        "steps": len(sequence),
        "passed": not all_failures,
        "console_errors": console_errors,
        "results": results,
    }
    report_path = Path(args.report) if args.report else REPORTS / "footer-work-sequence.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2))

    for result in results:
        print(f"{'PASS' if result['passed'] else 'FAIL'} step {result['step']:>2} {result['slug']}")
        for failure in result["failures"]:
            print(f"      - {failure}")

    if all_failures:
        print(f"\n{len(all_failures)} failure(s)")
        return 1
    print(f"\n{len(sequence)} sequential footer link clicks: no stale content, focus correct.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
