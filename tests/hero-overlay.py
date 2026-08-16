"""Hero H1 overlay suite.

Guarantees the hero headline stays *on* the hero image — never below it —
and that the overlay copy stays readable against the photograph.

Checks per viewport (and per browser):
  1. Semantics  — exactly one <h1> on the page, and it is the hero headline.
  2. Overlay    — the H1 box is fully inside the hero image box, is painted
                  above it (stacking context / elementFromPoint hit test),
                  and its bottom never crosses the image's bottom edge.
  3. Wrapping   — the headline still renders on exactly three visual lines
                  with the eyebrow/CTA sharing its left edge.
  4. Contrast   — text colour vs. the *actual pixels behind it* (text hidden,
                  background sampled from a screenshot) must clear WCAG AA.
  5. Pixels     — hero screenshot diffed against a per-browser baseline for
                  every breakpoint in both portrait and landscape.

Usage:
    python3 tests/hero-overlay.py
    python3 tests/hero-overlay.py --browsers chromium,firefox,webkit
    python3 tests/hero-overlay.py --only mobile-375,short-1280
    python3 tests/hero-overlay.py --orientation portrait
    python3 tests/hero-overlay.py --update-baseline
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path

from PIL import Image, ImageChops
from playwright.async_api import Error as PlaywrightError, async_playwright

TESTS_DIR = Path(__file__).parent
CONFIG = json.loads((TESTS_DIR / "hero.config.json").read_text())

parser = argparse.ArgumentParser(add_help=True)
parser.add_argument("base_url", nargs="?")
parser.add_argument("--profile", default=CONFIG.get("defaultProfile", "tanstack"))
parser.add_argument("--browsers", default="chromium,firefox,webkit")
parser.add_argument("--only", default=None, help="comma-separated viewport names or widths")
parser.add_argument(
    "--orientation", default="both", choices=["both", "portrait", "landscape"]
)
parser.add_argument("--update-baseline", action="store_true")
parser.add_argument("--report", default=str(TESTS_DIR / "report-hero-overlay.json"))
args = parser.parse_args()

PROFILE = CONFIG["profiles"][args.profile]
BASE_URL = (args.base_url or PROFILE["baseUrl"]).rstrip("/")
TARGET_URL = BASE_URL + PROFILE.get("path", "/")

SEL = CONFIG["selectors"]
EXPECTED_LINES = [line.upper() for line in CONFIG["expectedLines"]]
PADDING_TOLERANCE = CONFIG["paddingTolerance"]
PIXEL_THRESHOLD = CONFIG["pixelThreshold"]
MAX_DIFF_RATIO = CONFIG["maxDiffRatio"]

# Short viewports are the risky case: if the H1 ever escapes the image it will
# happen first where the hero stage is least tall.
SHORT_VIEWPORTS = [
    {"name": "short-568", "width": 320, "height": 568},
    {"name": "short-1280", "width": 1280, "height": 600},
    {"name": "short-1440", "width": 1440, "height": 540},
]
VIEWPORTS = CONFIG["viewports"] + SHORT_VIEWPORTS

if args.only:
    wanted = {v.strip().lower() for v in args.only.split(",") if v.strip()}
    VIEWPORTS = [
        v for v in VIEWPORTS if v["name"].lower() in wanted or str(v["width"]) in wanted
    ]
    if not VIEWPORTS:
        sys.exit(f"no viewport matched {sorted(wanted)}")

ORIENTATIONS = ["portrait", "landscape"] if args.orientation == "both" else [args.orientation]

SCREENSHOTS = TESTS_DIR / "screenshots" / "hero-overlay"
BASELINES = TESTS_DIR / "baselines" / "hero-overlay"
DIFFS = TESTS_DIR / "diffs" / "hero-overlay"

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
          window.scrollTo(0, 0);
        }"""
    )
    try:
        await page.wait_for_load_state("networkidle", timeout=10_000)
    except Exception:
        pass
    await page.evaluate("() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))")


# ---------------------------------------------------------------- contrast --

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


def parse_color(css: str):
    nums = [float(n) for n in css.replace(",", " ").replace("(", " ").replace(")", " ").split()
            if n.replace(".", "", 1).replace("-", "", 1).isdigit()]
    return tuple(int(round(n)) for n in nums[:3]) if len(nums) >= 3 else (255, 255, 255)


def _crop(png: Path, box, scale):
    img = Image.open(png).convert("RGB")
    x0 = max(0, int(box["x"] * scale))
    y0 = max(0, int(box["y"] * scale))
    x1 = min(img.width, int((box["x"] + box["width"]) * scale))
    y1 = min(img.height, int((box["y"] + box["height"]) * scale))
    if x1 <= x0 or y1 <= y0:
        return None
    return img.crop((x0, y0, x1, y1))


def worst_contrast(text_png: Path, bg_png: Path, box, fg, scale, glyph_threshold=24):
    """Worst contrast between the text colour and the backdrop *under glyphs*.

    The glyph mask is the pixel-difference between the normal render and the
    render with the copy set to `color: transparent`, so we only sample the
    backdrop the letterforms actually cover — box corners, button padding and
    inter-word gaps can't skew the result.
    """
    fg_img = _crop(text_png, box, scale)
    bg_img = _crop(bg_png, box, scale)
    if fg_img is None or bg_img is None:
        return None, None

    mask = ImageChops.difference(fg_img, bg_img).convert("L").point(
        lambda v: 255 if v > glyph_threshold else 0
    )
    pixels = [
        bg_img.getpixel((x, y))
        for y in range(bg_img.height)
        for x in range(bg_img.width)
        if mask.getpixel((x, y))
    ]
    if not pixels:  # nothing rendered (e.g. purely decorative) — skip
        return None, None

    worst, worst_px = 99.0, None
    for pixel in pixels:
        ratio = contrast(fg, pixel)
        if ratio < worst:
            worst, worst_px = ratio, pixel
    return worst, worst_px


# ------------------------------------------------------------------ checks --

async def run_case(browser, engine, view, orientation):
    name = view["name"]
    width, height = view["width"], view["height"]
    if orientation == "landscape":
        width, height = max(width, height), min(width, height)
    key = f"{engine}-{name}-{orientation}"
    failures, meta = [], {}

    context = await browser.new_context(
        viewport={"width": width, "height": height}, reduced_motion="reduce"
    )
    page = await context.new_page()
    await page.goto(TARGET_URL, wait_until="networkidle")
    await stabilize(page)

    # 1. exactly one H1, and it lives in the hero
    h1_count = await page.locator("h1").count()
    meta["h1Count"] = h1_count
    if h1_count != 1:
        failures.append(f"{key}: page has {h1_count} <h1> elements, want exactly 1")
    in_hero = await page.locator(f'{SEL["hero"]} h1').count()
    if in_hero != 1:
        failures.append(f"{key}: hero contains {in_hero} <h1>, want 1")

    h1 = page.locator("h1").first
    img = page.locator(f'{SEL["hero"]} img').first

    # 2. overlay geometry + paint order
    geom = await page.evaluate(
        """([heroSel]) => {
          const h1 = document.querySelector('h1');
          const img = document.querySelector(heroSel + ' img');
          const hb = h1.getBoundingClientRect();
          const ib = img.getBoundingClientRect();
          const cx = hb.x + hb.width / 2, cy = hb.y + hb.height / 2;
          const hit = document.elementFromPoint(cx, cy);
          let overlaysImage = false, node = hit;
          while (node) { if (node === h1) { overlaysImage = true; break; } node = node.parentElement; }
          const cs = getComputedStyle(h1);
          return {
            h1: {x: hb.x, y: hb.y, width: hb.width, height: hb.height, bottom: hb.bottom, right: hb.right},
            img: {x: ib.x, y: ib.y, width: ib.width, height: ib.height, bottom: ib.bottom, right: ib.right},
            overlaysImage,
            hitTag: hit ? hit.tagName.toLowerCase() : null,
            color: cs.color,
            position: cs.position,
          };
        }""",
        [SEL["hero"]],
    )
    hb, ib = geom["h1"], geom["img"]
    meta["h1Box"] = {k: round(v, 1) for k, v in hb.items()}
    meta["imgBox"] = {k: round(v, 1) for k, v in ib.items()}

    if hb["y"] < ib["y"] - 1 or hb["bottom"] > ib["bottom"] + 1:
        failures.append(
            f"{key}: H1 vertically escapes the hero image "
            f"(h1 {hb['y']:.0f}-{hb['bottom']:.0f} vs img {ib['y']:.0f}-{ib['bottom']:.0f})"
        )
    if hb["x"] < ib["x"] - 1 or hb["right"] > ib["right"] + 1:
        failures.append(f"{key}: H1 horizontally escapes the hero image")
    if hb["y"] >= ib["bottom"]:
        failures.append(f"{key}: H1 renders BELOW the hero image")
    if not geom["overlaysImage"]:
        failures.append(
            f"{key}: H1 is not the painted element at its own centre (hit <{geom['hitTag']}>)"
        )
    meta["position"] = geom["position"]

    # 3. wrapping + left-edge alignment
    lines = [t.strip().upper() for t in await h1.locator(SEL["headlineLine"]).all_inner_texts()]
    visual_lines = await h1.evaluate(
        "(el, s) => [...el.querySelectorAll(s)].reduce((n, x) => n + x.getClientRects().length, 0)",
        SEL["headlineLine"],
    )
    meta["lines"] = visual_lines
    if lines != EXPECTED_LINES:
        failures.append(f"{key}: headline text {lines} != {EXPECTED_LINES}")
    if visual_lines != len(EXPECTED_LINES):
        failures.append(f"{key}: headline on {visual_lines} visual lines, want {len(EXPECTED_LINES)}")

    boxes = {
        "h1": hb,
        "label": await page.locator(SEL["label"]).first.bounding_box(),
        "cta": await page.locator(SEL["cta"]).first.bounding_box(),
    }
    edges = {k: v["x"] for k, v in boxes.items() if v}
    spread = max(edges.values()) - min(edges.values())
    meta["leftEdges"] = {k: round(v, 1) for k, v in edges.items()}
    if spread > PADDING_TOLERANCE:
        failures.append(f"{key}: overlay left edges misaligned by {spread:.1f}px {meta['leftEdges']}")

    # 5. pixels (captured before we tamper with visibility)
    SCREENSHOTS.mkdir(parents=True, exist_ok=True)
    shot = SCREENSHOTS / f"hero-{key}.png"
    await page.locator(SEL["hero"]).screenshot(path=str(shot))

    # 4. contrast against the real backdrop.
    contrast_targets = [
        ("h1", h1, 3.0),  # large text -> AA large
        ("eyebrow", page.locator(SEL["label"]).first, 4.5),
        ("cta", page.locator(SEL["cta"]).first, 4.5),
    ]

    # Resolve computed colours through a canvas (modern colour spaces such as
    # oklch come back as plain sRGB bytes) BEFORE we neutralise the text.
    COLOR_JS = """el => {
      const cv = document.createElement('canvas');
      cv.width = cv.height = 1;
      const ctx = cv.getContext('2d');
      ctx.fillStyle = getComputedStyle(el).color;
      ctx.fillRect(0, 0, 1, 1);
      const d = ctx.getImageData(0, 0, 1, 1).data;
      return [d[0], d[1], d[2]];
    }"""
    fg_colors = {}
    for label, locator, _ in contrast_targets:
        fg_colors[label] = tuple(await locator.evaluate(COLOR_JS))

    # Two viewport screenshots at identical coordinates (element screenshots
    # scroll and clip, which would desync client rects on short viewports):
    # one normal, one with the copy set transparent. Their difference is the
    # glyph mask; the second one supplies the backdrop colours.
    text_shot = SCREENSHOTS / f"text-{key}.png"
    await page.screenshot(path=str(text_shot))

    overlay_sel = f'{SEL["hero"]} h1, {SEL["label"]}, {SEL["hero"]} a'
    await page.evaluate(
        "(sel) => document.querySelectorAll(sel).forEach(e => e.style.color = 'transparent')",
        overlay_sel,
    )
    await page.evaluate("() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))")
    bg_shot = SCREENSHOTS / f"bg-{key}.png"
    await page.screenshot(path=str(bg_shot))
    scale = Image.open(bg_shot).width / width

    meta["contrast"] = {}
    for label, locator, minimum in contrast_targets:
        box = boxes.get(label) or await locator.bounding_box()
        if not box:
            continue
        fg = fg_colors[label]
        rel = {
            "x": box["x"],
            "y": box["y"],
            "width": box["width"],
            "height": box["height"],
        }
        ratio, pixel = worst_contrast(text_shot, bg_shot, rel, fg, scale)
        if ratio is None:
            continue
        meta["contrast"][label] = round(ratio, 2)
        if ratio < minimum:
            failures.append(
                f"{key}: {label} contrast {ratio:.2f}:1 below {minimum}:1 "
                f"(text rgb{fg} over rgb{pixel})"
            )
    bg_shot.unlink(missing_ok=True)
    text_shot.unlink(missing_ok=True)

    await context.close()

    # pixel diff
    baseline = BASELINES / f"hero-{key}.png"
    ratio = 0.0
    if args.update_baseline or not baseline.exists():
        BASELINES.mkdir(parents=True, exist_ok=True)
        baseline.write_bytes(shot.read_bytes())
        print(f"{key}: baseline recorded")
    else:
        cur, exp = Image.open(shot).convert("RGB"), Image.open(baseline).convert("RGB")
        if cur.size != exp.size:
            failures.append(f"{key}: hero size changed {exp.size} -> {cur.size}")
            ratio = 1.0
        else:
            mask = ImageChops.difference(cur, exp).convert("L").point(
                lambda v: 255 if v > PIXEL_THRESHOLD else 0
            )
            changed = sum(mask.histogram()[255:])
            ratio = changed / (cur.width * cur.height)
            if ratio > MAX_DIFF_RATIO:
                DIFFS.mkdir(parents=True, exist_ok=True)
                trip = Image.new("RGB", (cur.width * 3, cur.height), (255, 255, 255))
                highlight = Image.new("RGB", cur.size, (255, 0, 255))
                dimmed = Image.blend(cur, Image.new("RGB", cur.size, (255, 255, 255)), 0.6)
                trip.paste(exp, (0, 0))
                trip.paste(cur, (cur.width, 0))
                trip.paste(Image.composite(highlight, dimmed, mask), (cur.width * 2, 0))
                out = DIFFS / f"hero-{key}-diff.png"
                trip.save(out)
                failures.append(f"{key}: {ratio:.2%} of pixels differ from baseline -> {out}")
    meta["diffRatio"] = round(ratio, 6)

    print(
        f"{key}: h1={meta['h1Count']} lines={meta['lines']} "
        f"contrast={meta['contrast']} diff={ratio:.3%} "
        f"{'OK' if not failures else 'FAIL'}"
    )
    return {
        "key": key,
        "engine": engine,
        "viewport": name,
        "orientation": orientation,
        "width": width,
        "height": height,
        **meta,
        "failures": failures,
        "passed": not failures,
    }


async def main() -> int:
    engines = [b.strip() for b in args.browsers.split(",") if b.strip()]
    results = []
    print(
        f"url={TARGET_URL} browsers={engines} viewports={len(VIEWPORTS)} "
        f"orientations={ORIENTATIONS}"
    )
    async with async_playwright() as pw:
        for engine in engines:
            browser = await getattr(pw, engine).launch(headless=True)
            for view in VIEWPORTS:
                for orientation in ORIENTATIONS:
                    # Engines occasionally tear down the execution context mid-
                    # evaluate (late hydration navigation). Retry the case.
                    for attempt in range(3):
                        try:
                            results.append(
                                await run_case(browser, engine, view, orientation)
                            )
                            break
                        except PlaywrightError as err:
                            if attempt == 2:
                                raise
                            print(
                                f"{engine}-{view['name']}-{orientation}: "
                                f"transient ({err.message.splitlines()[0]}), retrying"
                            )
                            await asyncio.sleep(1)

            await browser.close()

    failures = [f for r in results for f in r["failures"]]
    report = {
        "suite": "hero-h1-overlay",
        "url": TARGET_URL,
        "browsers": engines,
        "passed": not failures,
        "results": results,
    }
    Path(args.report).write_text(json.dumps(report, indent=2))
    print(f"\nreport written to {args.report}")

    if failures:
        print("\nFAIL")
        for f in failures:
            print(" -", f)
        return 1
    print(f"\nPASS: {len(results)} cases — one H1, overlaid on the image, readable everywhere")
    return 0


sys.exit(asyncio.run(main()))
