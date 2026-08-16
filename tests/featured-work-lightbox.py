#!/usr/bin/env python3
"""End-to-end checks for the Featured Work lightbox.

Covers:
  1. deep-linking (?work=<slug>) opens the matching item on a hard refresh,
     with no layout shift and the body scroll lock restored;
  2. prev/next keeps the URL in sync and neighbour images are already decoded;
  3. reduced-motion disables the lightbox transitions;
  4. focus returns to the clicked card after closing.

Usage:
  python3 tests/featured-work-lightbox.py
  python3 tests/featured-work-lightbox.py --base-url http://localhost:3000
  python3 tests/featured-work-lightbox.py --report tests/report-lightbox.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from pathlib import Path

from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parent
SLUGS = ["hollow-roasters", "field-and-frame", "meridian-health"]
NAMES = ["Hollow Roasters", "Field & Frame", "Meridian Health"]

CLS_JS = """
() => {
  window.__cls = 0;
  new PerformanceObserver((list) => {
    for (const entry of list.getEntries()) {
      if (!entry.hadRecentInput) window.__cls += entry.value;
    }
  }).observe({ type: 'layout-shift', buffered: true });
}
"""


class Results:
    def __init__(self) -> None:
        self.rows: list[dict] = []

    def check(self, name: str, ok: bool, detail: str = "") -> None:
        self.rows.append({"name": name, "status": "pass" if ok else "fail", "detail": detail})
        print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"  — {detail}" if detail else ""))

    @property
    def failed(self) -> list[dict]:
        return [r for r in self.rows if r["status"] != "pass"]


async def deep_link_case(context, base_url: str, res: Results) -> None:
    """Hard refresh straight onto ?work=<slug>: right item, no CLS, scroll locked."""
    page = await context.new_page()
    await page.add_init_script(CLS_JS)
    slug, name = SLUGS[1], NAMES[1]
    await page.goto(f"{base_url}/?work={slug}", wait_until="networkidle")

    dialog = page.get_by_role("dialog")
    await dialog.wait_for(state="visible", timeout=5000)
    title = (await dialog.locator("h2, [id$='radix-title'], .display").first.inner_text()).strip()
    res.check("deep link opens the matching item", title == name.upper() or title == name,
              f"title={title!r} expected≈{name!r}")

    # Image frame ratio is reserved before the image loads → no shift on paint.
    await page.wait_for_timeout(600)
    cls = await page.evaluate("() => window.__cls || 0")
    res.check("deep-linked open has no layout shift", cls < 0.02, f"CLS={cls:.4f}")

    locked = await page.evaluate(
        "() => getComputedStyle(document.body).overflow === 'hidden'"
        " || document.body.hasAttribute('data-scroll-locked')"
    )
    res.check("scroll lock applied on deep-linked open", bool(locked))

    scroll_before = await page.evaluate("() => window.scrollY")
    await page.mouse.wheel(0, 400)
    await page.wait_for_timeout(200)
    res.check(
        "page behind the lightbox cannot scroll",
        await page.evaluate("() => window.scrollY") == scroll_before,
    )

    # Close restores scrolling.
    await page.get_by_role("button", name=re.compile(r"^Close ")).first.click()
    await dialog.wait_for(state="hidden", timeout=5000)
    unlocked = await page.evaluate("() => getComputedStyle(document.body).overflow !== 'hidden'")
    res.check("scroll lock released on close", unlocked)
    await page.close()


async def neighbour_preload_case(context, base_url: str, res: Results) -> None:
    page = await context.new_page()
    await page.goto(f"{base_url}/?work={SLUGS[0]}", wait_until="networkidle")
    dialog = page.get_by_role("dialog")
    await dialog.wait_for(state="visible")
    await page.wait_for_timeout(500)

    decoded = await page.evaluate(
        "() => Array.from(document.images).filter(i => i.complete && i.naturalWidth > 0).length"
    )
    res.check("neighbour images decoded ahead of navigation", decoded >= 3, f"{decoded} images ready")

    await page.get_by_role("button", name=re.compile(r"^Next project")).first.click()
    await page.wait_for_timeout(300)
    res.check("next updates the URL", f"work={SLUGS[1]}" in page.url, page.url)

    await page.keyboard.press("ArrowLeft")
    await page.wait_for_timeout(300)
    res.check("arrow-left updates the URL", f"work={SLUGS[0]}" in page.url, page.url)
    await page.close()


async def reduced_motion_case(browser, base_url: str, res: Results) -> None:
    context = await browser.new_context(
        viewport={"width": 1280, "height": 1800}, reduced_motion="reduce"
    )
    page = await context.new_page()
    await page.goto(f"{base_url}/?work={SLUGS[0]}", wait_until="networkidle")
    dialog = page.get_by_role("dialog")
    await dialog.wait_for(state="visible")

    flag = await dialog.get_attribute("data-reduced-motion")
    res.check("lightbox reports reduced motion", flag == "true", f"data-reduced-motion={flag}")

    animated = await dialog.evaluate(
        "(el) => { const s = getComputedStyle(el);"
        " return { anim: s.animationName, dur: s.animationDuration, tdur: s.transitionDuration }; }"
    )
    ok = animated["anim"] in ("none", "") or animated["dur"] in ("0s", "0.000001s")
    res.check("lightbox transitions disabled under reduced motion", ok, json.dumps(animated))
    await context.close()


async def focus_return_case(context, base_url: str, res: Results) -> None:
    page = await context.new_page()
    await page.goto(base_url, wait_until="networkidle")
    card = page.get_by_role("button", name=re.compile(r"^View Meridian Health")).first
    await card.scroll_into_view_if_needed()
    await card.click()

    dialog = page.get_by_role("dialog")
    await dialog.wait_for(state="visible")
    res.check("clicking a card deep-links its slug", f"work={SLUGS[2]}" in page.url, page.url)

    await page.keyboard.press("Escape")
    await dialog.wait_for(state="hidden", timeout=5000)
    await page.wait_for_timeout(200)

    focused = await page.evaluate("() => document.activeElement?.getAttribute('aria-label') || ''")
    res.check(
        "focus returns to the clicked card",
        focused.startswith(f"View {NAMES[2]}"),
        f"activeElement aria-label={focused!r}",
    )
    res.check("closing clears the work param", "work=" not in page.url, page.url)
    await page.close()


async def run(base_url: str, report: Path | None) -> int:
    res = Results()
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1280, "height": 1800})
        await deep_link_case(context, base_url, res)
        await neighbour_preload_case(context, base_url, res)
        await focus_return_case(context, base_url, res)
        await context.close()
        await reduced_motion_case(browser, base_url, res)
        await browser.close()

    if report:
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text(
            json.dumps(
                {"baseUrl": base_url, "passed": not res.failed, "results": res.rows}, indent=2
            )
        )
        print(f"report written to {report}")

    print(f"\n{len(res.rows) - len(res.failed)}/{len(res.rows)} checks passed")
    return 1 if res.failed else 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="End-to-end checks for the Featured Work lightbox "
        "(deep-linking, scroll lock, neighbour preloading, reduced motion, focus return).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="examples:\n"
        "  python3 tests/featured-work-lightbox.py\n"
        "  python3 tests/featured-work-lightbox.py --base-url http://localhost:3000\n"
        "  python3 tests/featured-work-lightbox.py --report tests/report-lightbox.json\n",
    )
    parser.add_argument("--base-url", default="http://localhost:3000", help="app under test")
    parser.add_argument(
        "--report",
        default=str(ROOT / "report-lightbox.json"),
        help="path for the JSON run report ('none' to skip)",
    )
    args = parser.parse_args()
    report = None if args.report.lower() == "none" else Path(args.report)
    return asyncio.run(run(args.base_url.rstrip("/"), report))


if __name__ == "__main__":
    sys.exit(main())
