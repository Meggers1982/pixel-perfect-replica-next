"""Sitewide contrast audit — measured from rendered pixels, not tokens.

For hero, each service pillar, featured work, capabilities, about and the
footer, every text role (heading / label / body / control) is measured against
the pixels actually painted behind its glyphs. Text over photography is
therefore judged on the photograph, not on an assumed flat colour.

Thresholds: 4.5:1 for normal text, 3:1 for large text (>=24px, or >=18.66px
bold), per WCAG 2.1 AA.

Usage:
    python3 tests/section-contrast.py
    python3 tests/section-contrast.py --only mobile-375,desktop-1440
    python3 tests/section-contrast.py --browsers chromium,firefox
"""

import argparse
import asyncio
import json
from pathlib import Path

from PIL import Image, ImageChops
from playwright.async_api import async_playwright

TESTS_DIR = Path(__file__).parent
CONFIG = json.loads((TESTS_DIR / "hero.config.json").read_text())

parser = argparse.ArgumentParser()
parser.add_argument("base_url", nargs="?")
parser.add_argument("--profile", default=CONFIG.get("defaultProfile", "tanstack"))
parser.add_argument("--browsers", default="chromium")
parser.add_argument("--only", default=None)
parser.add_argument("--orientation", default="both", choices=["both", "portrait", "landscape"])
parser.add_argument("--report", default=str(TESTS_DIR / "report-section-contrast.json"))
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

# section -> css selectors whose *own* text is measured
TARGETS = {
    "hero": ["section#top h1", "section#top p", "section#top a"],
    "pillars": ["section#services h2", "section#services p", "section#services a"],
    "work": [
        "section#work > div p",
        "section#work h2",
        "section#work h3",
        "section#work article p",
        "section#work [data-testid='carousel-counter']",
    ],
    "capabilities": [
        "section#capabilities p",
        "section#capabilities h2",
        "section#capabilities h3",
        "section#capabilities li span",
    ],
    "about": ["section#about h2", "section#about p"],
    "footer": [
        "footer#contact h2",
        "footer#contact p",
        "footer#contact li a",
        "footer#contact button",
    ],
}

SCREENSHOTS = TESTS_DIR / "screenshots" / "section-contrast"

STABILIZE_CSS = """
  *, *::before, *::after {
    animation-duration: 0s !important; animation-delay: 0s !important;
    transition-duration: 0s !important; transition-delay: 0s !important;
    scroll-behavior: auto !important;
  }
  html { caret-color: transparent !important; }
"""


async def stabilize(page):
    await page.add_style_tag(content=STABILIZE_CSS)
    await page.evaluate(
        """async () => {
          document.getAnimations?.().forEach(a => { try { a.finish(); } catch {} });
          await document.fonts.ready;
          await Promise.all([...document.images].filter(i => !i.complete)
            .map(i => i.decode().catch(() => {})));
        }"""
    )
    try:
        await page.wait_for_load_state("networkidle", timeout=10_000)
    except Exception:
        pass


def _srgb(c):
    c = c / 255
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def luminance(rgb):
    r, g, b = (_srgb(v) for v in rgb[:3])
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(fg, bg):
    l1, l2 = luminance(fg), luminance(bg)
    hi, lo = max(l1, l2), min(l1, l2)
    return (hi + 0.05) / (lo + 0.05)


def _crop(png: Path, box, scale):
    img = Image.open(png).convert("RGB")
    x0, y0 = max(0, int(box["x"] * scale)), max(0, int(box["y"] * scale))
    x1 = min(img.width, int((box["x"] + box["width"]) * scale))
    y1 = min(img.height, int((box["y"] + box["height"]) * scale))
    if x1 <= x0 or y1 <= y0:
        return None
    return img.crop((x0, y0, x1, y1))


def worst_contrast(text_png, bg_png, box, fg, scale, glyph_threshold=24):
    fg_img, bg_img = _crop(text_png, box, scale), _crop(bg_png, box, scale)
    if fg_img is None or bg_img is None:
        return None, None
    mask = (
        ImageChops.difference(fg_img, bg_img)
        .convert("L")
        .point(lambda v: 255 if v > glyph_threshold else 0)
    )
    worst, worst_px = 99.0, None
    bg_px, mask_px = bg_img.load(), mask.load()
    for y in range(bg_img.height):
        for x in range(bg_img.width):
            if not mask_px[x, y]:
                continue
            ratio = contrast(fg, bg_px[x, y])
            if ratio < worst:
                worst, worst_px = ratio, bg_px[x, y]
    return (None, None) if worst_px is None else (worst, worst_px)


COLLECT_JS = """(selectors) => {
  const cv = document.createElement('canvas');
  cv.width = cv.height = 1;
  const ctx = cv.getContext('2d');
  const toRgb = (css) => { ctx.fillStyle = css; ctx.fillRect(0, 0, 1, 1);
    const d = ctx.getImageData(0, 0, 1, 1).data; return [d[0], d[1], d[2]]; };
  const out = [];
  const seen = new Set();
  for (const sel of selectors) {
    for (const el of document.querySelectorAll(sel)) {
      if (seen.has(el)) continue;
      seen.add(el);
      const text = (el.innerText || '').trim();
      if (!text) continue;
      const b = el.getBoundingClientRect();
      if (b.width < 2 || b.height < 2) continue;
      const cs = getComputedStyle(el);
      if (cs.visibility === 'hidden' || cs.display === 'none' || Number(cs.opacity) === 0) continue;
      const size = parseFloat(cs.fontSize);
      const weight = Number(cs.fontWeight) || 400;
      const large = size >= 24 || (size >= 18.66 && weight >= 700);
      out.push({
        selector: sel,
        label: text.slice(0, 40).replace(/\\s+/g, ' '),
        color: toRgb(cs.color),
        fontSize: size,
        large,
        box: {x: b.x + window.scrollX, y: b.y + window.scrollY, width: b.width, height: b.height},
      });
    }
  }
  return out;
}"""


async def measure_section(page, section, selectors, key, width):
    """Scroll the section into view, then sample every text node in it."""
    items = await page.evaluate(COLLECT_JS, selectors)
    if not items:
        return [], [f"{key}/{section}: no measurable text matched {selectors}"]

    results, failures = [], []
    SCREENSHOTS.mkdir(parents=True, exist_ok=True)
    text_shot = SCREENSHOTS / f"text-{key}-{section}.png"
    bg_shot = SCREENSHOTS / f"bg-{key}-{section}.png"

    # group items by the scroll position needed to see them
    for item in items:
        await page.evaluate("(y) => window.scrollTo(0, y)", max(0, item["box"]["y"] - 120))
        await page.evaluate(
            "() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))"
        )
        scroll_y = await page.evaluate("() => window.scrollY")
        rel = {
            "x": item["box"]["x"],
            "y": item["box"]["y"] - scroll_y,
            "width": item["box"]["width"],
            "height": item["box"]["height"],
        }
        if rel["y"] < 0 or rel["y"] + rel["height"] > await page.evaluate(
            "() => window.innerHeight"
        ):
            rel["y"] = max(0, rel["y"])
            rel["height"] = min(rel["height"], await page.evaluate("() => window.innerHeight") - rel["y"])
        if rel["height"] < 2:
            continue

        await page.screenshot(path=str(text_shot))
        await page.evaluate(
            """([sel, label]) => {
              for (const el of document.querySelectorAll(sel)) {
                if ((el.innerText || '').trim().slice(0, 40).replace(/\\s+/g, ' ') === label) {
                  el.dataset.contrastProbe = '1';
                  el.style.color = 'transparent';
                }
              }
            }""",
            [item["selector"], item["label"]],
        )
        await page.evaluate(
            "() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))"
        )
        await page.screenshot(path=str(bg_shot))
        await page.evaluate(
            """() => document.querySelectorAll('[data-contrast-probe]').forEach(el => {
                 el.style.color = ''; delete el.dataset.contrastProbe; })"""
        )

        scale = Image.open(bg_shot).width / width
        ratio, pixel = worst_contrast(text_shot, bg_shot, rel, tuple(item["color"]), scale)
        if ratio is None:
            continue
        minimum = 3.0 if item["large"] else 4.5
        entry = {
            "section": section,
            "selector": item["selector"],
            "text": item["label"],
            "fontSize": round(item["fontSize"], 1),
            "large": item["large"],
            "ratio": round(ratio, 2),
            "required": minimum,
            "color": item["color"],
            "worstBackdrop": list(pixel),
        }
        results.append(entry)
        if ratio < minimum - 0.01:
            failures.append(
                f"{key}/{section}: {item['label']!r} ({item['fontSize']:.0f}px) "
                f"{ratio:.2f}:1 below {minimum}:1 — rgb{tuple(item['color'])} over rgb{pixel}"
            )

    text_shot.unlink(missing_ok=True)
    bg_shot.unlink(missing_ok=True)
    return results, failures


async def run_case(browser, engine, view, orientation):
    width, height = view["width"], view["height"]
    if orientation == "landscape":
        width, height = max(width, height), min(width, height)
    key = f"{engine}-{view['name']}-{orientation}"

    context = await browser.new_context(
        viewport={"width": width, "height": height}, reduced_motion="reduce"
    )
    page = await context.new_page()
    await page.goto(TARGET_URL, wait_until="networkidle")
    await stabilize(page)

    measurements, failures = [], []
    for section, selectors in TARGETS.items():
        res, fails = await measure_section(page, section, selectors, key, width)
        measurements.extend(res)
        failures.extend(fails)

    await context.close()
    worst = min((m["ratio"] for m in measurements), default=None)
    print(
        f"{key}: samples={len(measurements)} worst={worst} "
        f"{'OK' if not failures else 'FAIL'}"
    )
    return {
        "key": key,
        "engine": engine,
        "viewport": view["name"],
        "orientation": orientation,
        "width": width,
        "height": height,
        "worstRatio": worst,
        "measurements": measurements,
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
                "suite": "section-contrast",
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
        for f in sorted(set(failures)):
            print(" -", f)
        return 1
    print(f"\nPASS — {len(results)} cases")
    return 0


raise SystemExit(asyncio.run(main()))
