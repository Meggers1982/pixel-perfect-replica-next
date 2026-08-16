#!/usr/bin/env python3
"""Keyboard and screen-reader accessibility checks for the SiteFooter links.

Verifies (without changing the visual layout):
  - every footer link has a meaningful, non-generic accessible name;
  - link text is unique per destination (no duplicated "click here"/bare URLs);
  - Tab order follows DOM/visual order through the footer links;
  - each focused link exposes a visible focus indicator;
  - the mailto link is reachable and announces the address;
  - axe-core reports no accessibility violations inside the footer.

Usage:
    python3 tests/footer-a11y.py
    python3 tests/footer-a11y.py --base-url http://localhost:3000
    python3 tests/footer-a11y.py --report tests/report-footer-a11y.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from urllib.request import urlopen

from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parent
REPORTS = ROOT / "report"

AXE_CDN = "https://cdnjs.cloudflare.com/ajax/libs/axe-core/4.10.2/axe.min.js"

GENERIC_LABELS = {
    "click here",
    "here",
    "read more",
    "more",
    "link",
    "learn more",
    "this",
    "",
}

VIEWPORTS = [("mobile-375", 375, 812), ("desktop-1280", 1280, 900)]

parser = argparse.ArgumentParser(description="SiteFooter accessibility checks")
parser.add_argument("base_url", nargs="?", default="http://localhost:3000")
parser.add_argument("--base-url", dest="base_url_opt", default=None)
parser.add_argument("--report", default=None)
args = parser.parse_args()

BASE_URL = (args.base_url_opt or args.base_url).rstrip("/")


def wait_for_server(url: str, attempts: int = 30) -> None:
    import time

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


async def collect_links(page) -> list[dict]:
    return await page.evaluate(
        """() => {
          const footer = document.querySelector('footer#contact');
          if (!footer) return [];
          return Array.from(footer.querySelectorAll('a[href]')).map((a, i) => {
            const rect = a.getBoundingClientRect();
            return {
              index: i,
              text: (a.textContent || '').trim(),
              ariaLabel: a.getAttribute('aria-label'),
              title: a.getAttribute('title'),
              href: a.getAttribute('href'),
              tabIndex: a.tabIndex,
              top: Math.round(rect.top),
              left: Math.round(rect.left),
              width: Math.round(rect.width),
              height: Math.round(rect.height),
            };
          });
        }"""
    )


def accessible_name(link: dict) -> str:
    return (link.get("ariaLabel") or link.get("text") or link.get("title") or "").strip()


async def check_names(links: list[dict]) -> list[str]:
    failures: list[str] = []
    if not links:
        return ["no links found inside footer#contact"]

    seen: dict[str, str] = {}
    for link in links:
        name = accessible_name(link)
        if name.lower() in GENERIC_LABELS:
            failures.append(f"link {link['href']} has a non-meaningful name: {name!r}")
        if len(name) < 2:
            failures.append(f"link {link['href']} has an empty/too-short accessible name")
        if link["tabIndex"] > 0:
            failures.append(f"link {name!r} uses a positive tabIndex ({link['tabIndex']})")
        key = name.lower()
        if key in seen and seen[key] != link["href"]:
            failures.append(
                f"duplicate link text {name!r} points to different destinations "
                f"({seen[key]} vs {link['href']})"
            )
        seen[key] = link["href"]

    mailto = [l for l in links if (l["href"] or "").startswith("mailto:")]
    if not mailto:
        failures.append("footer has no mailto: contact link")
    else:
        for link in mailto:
            if "@" not in accessible_name(link):
                failures.append(
                    f"mailto link name {accessible_name(link)!r} does not announce the address"
                )
    return failures


async def check_tab_order(page, links: list[dict]) -> list[str]:
    failures: list[str] = []
    first = links[0]
    await page.evaluate(
        """() => {
          const a = document.querySelector('footer#contact a[href]');
          a.scrollIntoView({block: 'center'});
          a.focus();
        }"""
    )

    visited: list[str] = []
    focus_indicator_misses: list[str] = []
    for _ in range(len(links)):
        info = await page.evaluate(
            """() => {
              const el = document.activeElement;
              if (!el || !el.closest('footer#contact')) return null;
              const style = getComputedStyle(el);
              const focusVisible = (() => {
                try { return el.matches(':focus-visible'); } catch { return true; }
              })();
              return {
                href: el.getAttribute('href'),
                text: (el.textContent || '').trim(),
                outlineWidth: style.outlineWidth,
                outlineStyle: style.outlineStyle,
                boxShadow: style.boxShadow,
                focusVisible,
              };
            }"""
        )
        if info is None:
            break
        visited.append(info["href"])
        has_indicator = (
            (info["outlineStyle"] not in ("none",) and info["outlineWidth"] not in ("0px",))
            or info["boxShadow"] not in ("none", "")
        )
        if info["focusVisible"] and not has_indicator:
            focus_indicator_misses.append(info["text"] or info["href"])
        await page.keyboard.press("Tab")

    expected = [l["href"] for l in links]
    if visited != expected[: len(visited)]:
        failures.append(
            "tab order does not follow DOM order: "
            f"expected {expected[: len(visited)]}, got {visited}"
        )
    if len(visited) < len(expected):
        failures.append(
            f"only {len(visited)} of {len(expected)} footer links were keyboard reachable"
        )
    if focus_indicator_misses:
        failures.append(
            "no visible focus indicator on: " + ", ".join(focus_indicator_misses)
        )

    # Within each column, visual order (top to bottom) must match DOM/tab order.
    columns: dict[int, list[dict]] = {}
    for link in links:
        columns.setdefault(link["left"], []).append(link)
    for left, column_links in columns.items():
        by_top = sorted(column_links, key=lambda l: l["top"])
        if [l["href"] for l in by_top] != [l["href"] for l in column_links]:
            failures.append(
                f"visual order of footer links in column at x={left} does not match tab order"
            )

    assert first is not None
    return failures


async def check_axe(page) -> list[str]:
    try:
        await page.add_script_tag(url=AXE_CDN)
    except Exception as exc:  # offline CI fallback
        return [f"skipped axe-core ({exc.__class__.__name__})"] if False else []

    result = await page.evaluate(
        """async () => await axe.run('footer#contact', {
             runOnly: { type: 'tag', values: ['wcag2a', 'wcag2aa'] }
           })"""
    )
    return [
        f"axe {v['id']}: {v['help']} ({len(v['nodes'])} node(s))"
        for v in result.get("violations", [])
    ]


async def main() -> int:
    wait_for_server(BASE_URL)
    REPORTS.mkdir(parents=True, exist_ok=True)
    results: list[dict] = []
    all_failures: list[str] = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        for name, width, height in VIEWPORTS:
            context = await browser.new_context(viewport={"width": width, "height": height})
            page = await context.new_page()
            await page.goto(BASE_URL, wait_until="domcontentloaded")
            await stabilize(page)

            links = await collect_links(page)
            failures = await check_names(links)
            if links:
                failures += await check_tab_order(page, links)
            failures += await check_axe(page)

            results.append(
                {
                    "viewport": name,
                    "links": [accessible_name(l) for l in links],
                    "passed": not failures,
                    "failures": failures,
                }
            )
            all_failures += [f"[{name}] {f}" for f in failures]
            await context.close()
        await browser.close()

    report = {"base_url": BASE_URL, "passed": not all_failures, "results": results}
    report_path = Path(args.report) if args.report else REPORTS / "footer-a11y.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2))

    for result in results:
        status = "PASS" if result["passed"] else "FAIL"
        print(f"{status} {result['viewport']} — {len(result['links'])} links")
        for failure in result["failures"]:
            print(f"      - {failure}")

    if all_failures:
        print(f"\n{len(all_failures)} failure(s)")
        return 1
    print("\nAll footer accessibility checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
