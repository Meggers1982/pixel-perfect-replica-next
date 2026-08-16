"""Section-to-section transition snapshots.

Captures a fixed-height band centred on every section boundary
(hero -> pillars, pillar -> pillar, pillars -> work, work -> capabilities,
capabilities -> about, about -> footer) at every breakpoint and orientation,
and diffs it against a recorded baseline. A boundary that shifts spacing or
loses its contrast edge shows up as a pixel diff on exactly that band.

Alongside the pixels each band records the measured luminance step across the
boundary, so a transition that quietly loses its light/dark contrast fails even
when the pixel diff stays under threshold.

Usage:
    python3 tests/section-transitions.py
    python3 tests/section-transitions.py --update-baseline
    python3 tests/section-transitions.py --update-only-failures
    python3 tests/section-transitions.py --only desktop-1440 --boundaries work-capabilities
    python3 tests/section-transitions.py --retries 3 --quarantine short-812
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
parser.add_argument("--only", default=None, help="comma-separated viewport names or widths")
parser.add_argument("--boundaries", default=None, help="comma-separated boundary ids")
parser.add_argument("--orientation", default="both", choices=["both", "portrait", "landscape"])
parser.add_argument("--band-height", type=int, default=240)
parser.add_argument("--retries", type=int, default=CONFIG.get("retries", 2))
parser.add_argument("--retry-delay-ms", type=int, default=CONFIG.get("retryDelayMs", 750))
parser.add_argument("--quarantine", default=",".join(CONFIG.get("quarantine", [])))
parser.add_argument("--update-baseline", action="store_true")
parser.add_argument("--update-only-failures", action="store_true")
parser.add_argument("--min-luminance-step", type=float, default=0.04)
parser.add_argument("--min-edge-delta", type=float, default=0.01)
parser.add_argument("--report", default=str(TESTS_DIR / "report-section-transitions.json"))
args = parser.parse_args()

PROFILE = CONFIG["profiles"][args.profile]
BASE_URL = (args.base_url or PROFILE["baseUrl"]).rstrip("/")
TARGET_URL = BASE_URL + PROFILE.get("path", "/")

PIXEL_THRESHOLD = CONFIG["pixelThreshold"]
MAX_DIFF_RATIO = CONFIG["maxDiffRatio"]

SHORT_VIEWPORTS = [
    {"name": "short-1280", "width": 1280, "height": 600},
    {"name": "short-812", "width": 812, "height": 375},
]
VIEWPORTS = CONFIG["viewports"] + SHORT_VIEWPORTS
if args.only:
    wanted = {v.strip().lower() for v in args.only.split(",") if v.strip()}
    VIEWPORTS = [v for v in VIEWPORTS if v["name"].lower() in wanted or str(v["width"]) in wanted]

ORIENTATIONS = ["portrait", "landscape"] if args.orientation == "both" else [args.orientation]
QUARANTINED = {q.strip().lower() for q in args.quarantine.split(",") if q.strip()}

# boundary id -> (selector above, selector below, mode). The pillars are three
# stacked <article>s inside #services, so their internal seams get bands too.
#
#   mode "tone" — the two sections use different backgrounds; the band must keep
#                 a measurable luminance step.
#   mode "rule" — both sides are dark photography; separation comes from a
#                 hairline divider, so the band must keep a detectable edge row.
BOUNDARIES = [
    ("hero-pillars", "section#top", "section#services", "rule"),
    ("pillar-1-2", "section#services article:nth-of-type(1)", "section#services article:nth-of-type(2)", "rule"),
    ("pillar-2-3", "section#services article:nth-of-type(2)", "section#services article:nth-of-type(3)", "rule"),
    ("pillars-work", "section#services", "section#work", "tone"),
    ("work-capabilities", "section#work", "section#capabilities", "tone"),
    ("capabilities-about", "section#capabilities", "section#about", "tone"),
    ("about-footer", "section#about", "footer#contact", "tone"),
]
if args.boundaries:
    wanted = {b.strip().lower() for b in args.boundaries.split(",") if b.strip()}
    BOUNDARIES = [b for b in BOUNDARIES if b[0].lower() in wanted]

SCREENSHOTS = TESTS_DIR / "screenshots" / "section-transitions"
BASELINES = TESTS_DIR / "baselines" / "section-transitions"
DIFFS = TESTS_DIR / "diffs" / "section-transitions"
REPORT_DIR = TESTS_DIR / "report"

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
    await page.evaluate(
        "() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))"
    )


def _srgb(c):
    c = c / 255
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def luminance(rgb):
    r, g, b = (_srgb(v) for v in rgb[:3])
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def strongest_edge(png: Path, seam):
    """Largest luminance delta between consecutive rows of the band.

    A hairline divider between two dark photographs shows up here even though
    the two halves have (correctly) near-identical mean luminance.
    """
    img = Image.open(png).convert("RGB")
    # Narrow the search to rows around the seam and keep native vertical
    # resolution — a 1px hairline vanishes if the band is downsampled.
    scale = img.height / max(1, seam["bandHeight"])
    centre = max(0, min(img.height - 1, int(seam["offset"] * scale)))
    window = max(4, int(16 * scale))
    lo, hi = max(0, centre - window), min(img.height, centre + window)
    strip = img.crop((0, lo, img.width, hi)).resize((24, hi - lo))
    px = strip.load()
    rows = [sum(luminance(px[x, y]) for x in range(24)) / 24 for y in range(hi - lo)]
    if len(rows) < 2:
        return 0.0
    return round(max(abs(rows[i + 1] - rows[i]) for i in range(len(rows) - 1)), 4)


def band_luminances(png: Path, seam: float):
    """Mean luminance either side of the seam inside the captured band.

    The seam is not always centred (a boundary near the end of the document
    can't be scrolled to mid-viewport), so both halves are measured relative to
    the seam rather than to the band.
    """
    img = Image.open(png).convert("RGB")
    scale = img.height / max(1, seam["bandHeight"])
    y = max(1, min(img.height - 1, int(seam["offset"] * scale)))
    mean = lambda im: (  # noqa: E731
        sum(luminance(px) for px in im.resize((16, 16)).getdata()) / 256
    )
    top = mean(img.crop((0, 0, img.width, y)))
    bottom = mean(img.crop((0, y, img.width, img.height)))
    return round(top, 4), round(bottom, 4)


async def capture_band(page, above, below, height, view_height):
    """Scroll so the seam sits mid-viewport and grab a band around it."""
    y = await page.evaluate(
        """([a, b]) => {
          const top = document.querySelector(a);
          const bot = document.querySelector(b);
          if (!top || !bot) return null;
          const r = bot.getBoundingClientRect();
          return r.top + window.scrollY;
        }""",
        [above, below],
    )
    if y is None:
        return None
    band = min(height, view_height)
    target = max(0, y - band / 2)
    await page.evaluate("(t) => window.scrollTo(0, t)", target)
    await page.evaluate(
        "() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))"
    )
    scroll_y = await page.evaluate("() => window.scrollY")
    seam_in_view = y - scroll_y
    clip_y = max(0, min(view_height - band, seam_in_view - band / 2))
    return {"y": clip_y, "height": band, "offset": seam_in_view - clip_y, "bandHeight": band}


async def run_case(browser, engine, view, orientation, previous_failures):
    width, height = view["width"], view["height"]
    if orientation == "landscape":
        width, height = max(width, height), min(width, height)
    key = f"{engine}-{view['name']}-{orientation}"
    quarantined = view["name"].lower() in QUARANTINED or key.lower() in QUARANTINED

    context = await browser.new_context(
        viewport={"width": width, "height": height}, reduced_motion="reduce"
    )
    page = await context.new_page()
    await page.goto(TARGET_URL, wait_until="networkidle")
    await stabilize(page)

    SCREENSHOTS.mkdir(parents=True, exist_ok=True)
    bands, failures = [], []

    for bid, above, below, mode in BOUNDARIES:
        band_key = f"{key}-{bid}"
        clip = await capture_band(page, above, below, args.band_height, height)
        if clip is None:
            failures.append(f"{band_key}: boundary selectors not found ({above} / {below})")
            continue

        shot = SCREENSHOTS / f"{band_key}.png"
        await page.screenshot(
            path=str(shot),
            clip={"x": 0, "y": clip["y"], "width": width, "height": clip["height"]},
        )
        top_l, bottom_l = band_luminances(shot, clip)
        step = round(abs(top_l - bottom_l), 4)
        edge = strongest_edge(shot, clip)

        entry = {
            "boundary": bid,
            "mode": mode,
            "topLuminance": top_l,
            "bottomLuminance": bottom_l,
            "luminanceStep": step,
            "edgeDelta": edge,
            "diffRatio": 0.0,
        }
        if mode == "tone" and step < args.min_luminance_step:
            failures.append(
                f"{band_key}: luminance step {step:.3f} below {args.min_luminance_step} "
                "— the sections no longer read as separate blocks"
            )
        if mode == "rule" and edge < args.min_edge_delta:
            failures.append(
                f"{band_key}: edge delta {edge:.3f} below {args.min_edge_delta} "
                "— the divider between the dark sections is gone"
            )

        baseline = BASELINES / f"{band_key}.png"
        should_record = args.update_baseline or not baseline.exists() or (
            args.update_only_failures and band_key in previous_failures
        )
        if should_record:
            BASELINES.mkdir(parents=True, exist_ok=True)
            baseline.write_bytes(shot.read_bytes())
            entry["baseline"] = "recorded"
            print(f"{band_key}: baseline recorded (step={step:.3f})")
        else:
            cur = Image.open(shot).convert("RGB")
            exp = Image.open(baseline).convert("RGB")
            if cur.size != exp.size:
                failures.append(f"{band_key}: band size changed {exp.size} -> {cur.size}")
                entry["diffRatio"] = 1.0
            else:
                mask = (
                    ImageChops.difference(cur, exp)
                    .convert("L")
                    .point(lambda v: 255 if v > PIXEL_THRESHOLD else 0)
                )
                changed = sum(mask.histogram()[255:])
                ratio = changed / (cur.width * cur.height)
                entry["diffRatio"] = round(ratio, 6)
                if ratio > MAX_DIFF_RATIO:
                    DIFFS.mkdir(parents=True, exist_ok=True)
                    trip = Image.new("RGB", (cur.width * 3, cur.height), (255, 255, 255))
                    highlight = Image.new("RGB", cur.size, (255, 0, 255))
                    dimmed = Image.blend(cur, Image.new("RGB", cur.size, (255, 255, 255)), 0.6)
                    trip.paste(exp, (0, 0))
                    trip.paste(cur, (cur.width, 0))
                    trip.paste(Image.composite(highlight, dimmed, mask), (cur.width * 2, 0))
                    out = DIFFS / f"{band_key}-diff.png"
                    trip.save(out)
                    entry["diff"] = str(out)
                    failures.append(f"{band_key}: {ratio:.2%} of pixels differ -> {out}")
        bands.append(entry)

    await context.close()

    if quarantined and failures:
        print(f"{key}: QUARANTINED ({len(failures)} issues ignored)")
        failures = []

    print(
        f"{key}: bands={len(bands)} "
        f"worstStep={min((b['luminanceStep'] for b in bands if b['mode'] == 'tone'), default=0):.3f} "
        f"worstEdge={min((b['edgeDelta'] for b in bands if b['mode'] == 'rule'), default=0):.3f} "
        f"{'OK' if not failures else 'FAIL'}"
    )
    return {
        "key": key,
        "engine": engine,
        "viewport": view["name"],
        "orientation": orientation,
        "width": width,
        "height": height,
        "quarantined": quarantined,
        "bands": bands,
        "failures": failures,
        "passed": not failures,
    }


def write_gallery(results):
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    rows = []
    for r in results:
        for band in r["bands"]:
            band_key = f"{r['key']}-{band['boundary']}"
            failed = any(band_key in f for f in r["failures"])
            img = band.get("diff") or str(SCREENSHOTS / f"{band_key}.png")
            rel = Path(img).resolve().relative_to(TESTS_DIR.resolve())
            rows.append(
                f"<figure class='{'fail' if failed else 'pass'}'>"
                f"<figcaption>{band_key} [{band['mode']}] — step {band['luminanceStep']:.3f}, "
                f"edge {band['edgeDelta']:.3f}, "
                f"diff {band['diffRatio']:.3%}</figcaption>"
                f"<img loading='lazy' src='../{rel}'></figure>"
            )
    html = (
        "<!doctype html><meta charset='utf-8'><title>Section transitions</title>"
        "<style>body{font:14px system-ui;background:#111;color:#eee;margin:24px}"
        "figure{margin:0 0 24px;border:2px solid #333;padding:8px}"
        "figure.fail{border-color:#ff3b6b}figure.pass{border-color:#2c8}"
        "img{max-width:100%;display:block}figcaption{margin-bottom:8px}</style>"
        f"<h1>Section transitions — {args.profile}</h1>" + "".join(rows)
    )
    out = REPORT_DIR / f"section-transitions-{args.profile}.html"
    out.write_text(html)
    print(f"gallery written to {out}")


async def main() -> int:
    engines = [b.strip() for b in args.browsers.split(",") if b.strip()]
    previous_failures = set()
    report_path = Path(args.report)
    if args.update_only_failures and report_path.exists():
        prev = json.loads(report_path.read_text())
        for r in prev.get("results", []):
            for f in r.get("failures", []):
                previous_failures.add(f.split(":")[0])
        print(f"re-recording only: {sorted(previous_failures)}")

    print(
        f"url={TARGET_URL} viewports={len(VIEWPORTS)} orientations={ORIENTATIONS} "
        f"boundaries={len(BOUNDARIES)} retries={args.retries}"
    )
    results = []
    async with async_playwright() as pw:
        for engine in engines:
            browser = await getattr(pw, engine).launch(headless=True)
            for view in VIEWPORTS:
                for orientation in ORIENTATIONS:
                    result = None
                    for attempt in range(args.retries + 1):
                        result = await run_case(
                            browser, engine, view, orientation, previous_failures
                        )
                        if result["passed"]:
                            break
                        if attempt < args.retries:
                            print(f"  retry {attempt + 1}/{args.retries} for {result['key']}")
                            await asyncio.sleep(args.retry_delay_ms / 1000)
                    results.append(result)
            await browser.close()

    failures = [f for r in results for f in r["failures"]]
    report_path.write_text(
        json.dumps(
            {
                "suite": "section-transitions",
                "url": TARGET_URL,
                "browsers": engines,
                "passed": not failures,
                "results": results,
            },
            indent=2,
        )
    )
    print(f"report written to {report_path}")
    write_gallery(results)

    if failures:
        print("\nFAIL")
        for f in failures:
            print(" -", f)
        return 1
    print(f"\nPASS — {len(results)} cases")
    return 0


raise SystemExit(asyncio.run(main()))
