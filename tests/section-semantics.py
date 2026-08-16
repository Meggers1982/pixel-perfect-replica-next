"""Section semantics audit.

For every breakpoint (plus short-height viewports) and both orientations:

  1. exactly one <h1>, exactly one <main>
  2. no skipped heading levels, no empty headings
  3. every section (hero, pillars, work, capabilities, about, footer) owns a heading
  4. axe-core: heading-order, landmark-one-main, page-has-heading-one, color-contrast
  5. on short viewports the hero overlay copy stays inside the hero image and
     does not overlap the CTA row

Usage:
    python3 tests/section-semantics.py
    python3 tests/section-semantics.py --only short-1280
    python3 tests/section-semantics.py --browsers chromium,firefox
"""

import argparse
import asyncio
import json
from pathlib import Path

from playwright.async_api import async_playwright

TESTS_DIR = Path(__file__).parent
CONFIG = json.loads((TESTS_DIR / "hero.config.json").read_text())

parser = argparse.ArgumentParser()
parser.add_argument("base_url", nargs="?")
parser.add_argument("--profile", default=CONFIG.get("defaultProfile", "tanstack"))
parser.add_argument("--browsers", default="chromium")
parser.add_argument("--only", default=None)
parser.add_argument("--orientation", default="both", choices=["both", "portrait", "landscape"])
parser.add_argument("--report", default=str(TESTS_DIR / "report-section-semantics.json"))
args = parser.parse_args()

PROFILE = CONFIG["profiles"][args.profile]
BASE_URL = (args.base_url or PROFILE["baseUrl"]).rstrip("/")
TARGET_URL = BASE_URL + PROFILE.get("path", "/")

SHORT_VIEWPORTS = [
    {"name": "short-1280", "width": 1280, "height": 600},
    {"name": "short-812", "width": 812, "height": 375},
]
VIEWPORTS = CONFIG["viewports"] + SHORT_VIEWPORTS
if args.only:
    wanted = {v.strip().lower() for v in args.only.split(",") if v.strip()}
    VIEWPORTS = [v for v in VIEWPORTS if v["name"].lower() in wanted or str(v["width"]) in wanted]

ORIENTATIONS = ["portrait", "landscape"] if args.orientation == "both" else [args.orientation]

SECTIONS = ["#top", "#services", "#work", "#capabilities", "#about", "#contact"]

AXE_URL = "https://cdn.jsdelivr.net/npm/axe-core@4.10.2/axe.min.js"
AXE_RULES = ["heading-order", "landmark-one-main", "page-has-heading-one", "color-contrast"]

STABILIZE_CSS = """
  *, *::before, *::after {
    animation-duration: 0s !important; animation-delay: 0s !important;
    transition-duration: 0s !important; transition-delay: 0s !important;
    scroll-behavior: auto !important;
  }
"""


async def stabilize(page):
    await page.add_style_tag(content=STABILIZE_CSS)
    await page.evaluate(
        """async () => {
          document.getAnimations?.().forEach(a => { try { a.finish(); } catch {} });
          await document.fonts.ready;
          await Promise.all([...document.images].filter(i => !i.complete)
            .map(i => i.decode().catch(() => {})));
          window.scrollTo(0, 0);
        }"""
    )
    try:
        await page.wait_for_load_state("networkidle", timeout=10_000)
    except Exception:
        pass


async def run_case(browser, engine, view, orientation):
    width, height = view["width"], view["height"]
    if orientation == "landscape":
        width, height = max(width, height), min(width, height)
    key = f"{engine}-{view['name']}-{orientation}"
    failures = []

    context = await browser.new_context(
        viewport={"width": width, "height": height}, reduced_motion="reduce"
    )
    page = await context.new_page()
    await page.goto(TARGET_URL, wait_until="networkidle")
    await stabilize(page)

    outline = await page.evaluate(
        """(sections) => {
          const heads = [...document.querySelectorAll('h1,h2,h3,h4,h5,h6')]
            .filter(h => h.offsetParent !== null || getComputedStyle(h).position === 'fixed')
            .map(h => ({level: Number(h.tagName[1]), text: h.innerText.trim().slice(0, 60)}));
          const perSection = {};
          for (const sel of sections) {
            const el = document.querySelector(sel);
            perSection[sel] = el ? el.querySelectorAll('h1,h2,h3,h4,h5,h6').length : -1;
          }
          return {
            heads,
            h1: document.querySelectorAll('h1').length,
            main: document.querySelectorAll('main').length,
            perSection,
          };
        }""",
        SECTIONS,
    )

    if outline["h1"] != 1:
        failures.append(f"{key}: {outline['h1']} <h1> elements, want 1")
    if outline["main"] != 1:
        failures.append(f"{key}: {outline['main']} <main> landmarks, want 1")

    prev = 0
    for head in outline["heads"]:
        if not head["text"]:
            failures.append(f"{key}: empty h{head['level']}")
        if prev and head["level"] > prev + 1:
            failures.append(
                f"{key}: heading level jumps h{prev} -> h{head['level']} ({head['text']!r})"
            )
        prev = head["level"]

    for sel, count in outline["perSection"].items():
        if count == -1:
            failures.append(f"{key}: section {sel} missing from the page")
        elif count == 0:
            failures.append(f"{key}: section {sel} has no heading")

    # hero overlay geometry on short viewports
    geom = await page.evaluate(
        """() => {
          const h1 = document.querySelector('h1');
          const img = document.querySelector('section#top img');
          const cta = document.querySelector('section#top a[href="#contact"]');
          const r = e => { const b = e.getBoundingClientRect();
            return {x: b.x, y: b.y, bottom: b.bottom, right: b.right, width: b.width, height: b.height}; };
          return {h1: r(h1), img: r(img), cta: r(cta)};
        }"""
    )
    h1b, imgb, ctab = geom["h1"], geom["img"], geom["cta"]
    if h1b["bottom"] > imgb["bottom"] + 1 or h1b["y"] < imgb["y"] - 1:
        failures.append(f"{key}: hero H1 escapes the hero image vertically")
    if h1b["bottom"] > ctab["y"] + 1:
        failures.append(f"{key}: hero H1 overlaps the CTA row")

    # axe
    await page.add_script_tag(url=AXE_URL)
    axe = await page.evaluate(
        """async (rules) => {
          const res = await window.axe.run(document, {runOnly: {type: 'rule', values: rules}});
          return res.violations.map(v => ({
            id: v.id, impact: v.impact, nodes: v.nodes.length,
            sample: v.nodes.slice(0, 3).map(n => n.target.join(' ') + ' :: ' + (n.failureSummary || '').split('\\n')[1]),
          }));
        }""",
        AXE_RULES,
    )
    for violation in axe:
        failures.append(
            f"{key}: axe {violation['id']} ({violation['impact']}) x{violation['nodes']} "
            f"-> {violation['sample']}"
        )

    await context.close()
    print(
        f"{key}: headings={len(outline['heads'])} h1={outline['h1']} "
        f"axe={len(axe)} {'OK' if not failures else 'FAIL'}"
    )
    return {
        "key": key,
        "engine": engine,
        "viewport": view["name"],
        "orientation": orientation,
        "width": width,
        "height": height,
        "headings": outline["heads"],
        "sectionHeadings": outline["perSection"],
        "axeViolations": axe,
        "failures": failures,
        "passed": not failures,
    }


async def main() -> int:
    engines = [b.strip() for b in args.browsers.split(",") if b.strip()]
    results = []
    print(f"url={TARGET_URL} viewports={len(VIEWPORTS)} orientations={ORIENTATIONS}")
    async with async_playwright() as pw:
        for engine in engines:
            browser = await getattr(pw, engine).launch(headless=True)
            for view in VIEWPORTS:
                for orientation in ORIENTATIONS:
                    results.append(await run_case(browser, engine, view, orientation))
            await browser.close()

    failures = [f for r in results for f in r["failures"]]
    Path(args.report).write_text(
        json.dumps(
            {
                "suite": "section-semantics",
                "url": TARGET_URL,
                "browsers": engines,
                "passed": not failures,
                "results": results,
            },
            indent=2,
        )
    )
    print(f"\nreport written to {args.report}")
    if failures:
        print("\nFAIL")
        for f in failures:
            print(" -", f)
        return 1
    print(f"\nPASS — {len(results)} cases")
    return 0


raise SystemExit(asyncio.run(main()))
