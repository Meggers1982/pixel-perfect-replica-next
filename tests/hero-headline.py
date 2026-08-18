"""Visual regression check for the hero headline.

Harness-agnostic: everything app-specific (base URL, path, selectors,
viewports, tolerances) lives in tests/hero.config.json, so the same script
runs against the TanStack Start dev server or a separate Next.js harness by
switching profile — no code edits required.

Confirms the H1 always wraps into exactly three lines (and that the CTA row,
label and headline share the container's left padding) across every viewport,
then pixel-diffs each hero screenshot against a committed baseline. Flaky
renders (fonts settling, image decode) are retried before a viewport fails,
and every run writes an HTML gallery of all viewports for CI review.

Usage:
    python3 tests/hero-headline.py                      # tanstack profile
    python3 tests/hero-headline.py --profile nextjs     # Next.js harness
    python3 tests/hero-headline.py http://localhost:3000
    python3 tests/hero-headline.py --only desktop-1280            # one viewport
    python3 tests/hero-headline.py --only 375,1280                # by width
    python3 tests/hero-headline.py --retries 3
    python3 tests/hero-headline.py --update-baseline

Requires the target app running and Pillow + Playwright installed.
"""

import argparse
import asyncio
import html
import json
import sys
from pathlib import Path

from PIL import Image, ImageChops
from playwright.async_api import async_playwright

TESTS_DIR = Path(__file__).parent
CONFIG_PATH = TESTS_DIR / "hero.config.json"

parser = argparse.ArgumentParser(add_help=True)
parser.add_argument("base_url", nargs="?", help="override the profile's base URL")
parser.add_argument("--profile", default=None, help="profile name from hero.config.json")
parser.add_argument("--config", default=str(CONFIG_PATH), help="path to a config JSON file")
parser.add_argument(
    "--only",
    "--viewports",
    dest="only",
    default=None,
    help="comma-separated viewport names or widths to run (e.g. desktop-1280,375)",
)
parser.add_argument("--update-baseline", action="store_true")
parser.add_argument("--baseline-dir", default=None, help="baseline dir (defaults per profile)")
parser.add_argument("--report", default=None, help="write a JSON result report to this path")
parser.add_argument(
    "--retries",
    type=int,
    default=None,
    help="retry attempts per viewport before failing (default from config)",
)
parser.add_argument("--gallery", default=None, help="path for the HTML report gallery")
parser.add_argument("--no-gallery", action="store_true", help="skip writing the HTML gallery")
parser.add_argument(
    "--update-only-failures",
    action="store_true",
    help="re-record baselines only for viewports that failed in the last report",
)
parser.add_argument(
    "--last-report",
    default=None,
    help="report JSON to read for --update-only-failures (default tests/report-hero.json)",
)
parser.add_argument(
    "--quarantine",
    default=None,
    help="comma-separated viewports whose failures are reported but do not fail the run",
)
parser.add_argument(
    "--only-featured-work",
    action="store_true",
    help="skip the hero suite and run only tests/featured-work-padding.py",
)
parser.add_argument(
    "--padding-tolerance",
    "--tolerance",
    dest="tolerance",
    type=float,
    default=None,
    help="forwarded to the FeaturedWork padding suite with --only-featured-work",
)
args = parser.parse_args()

if args.only_featured_work:
    import subprocess

    cmd = [sys.executable, str(TESTS_DIR / "featured-work-padding.py")]
    if args.profile:
        cmd += ["--profile", args.profile]
    if args.only:
        cmd += ["--only", args.only]
    if args.update_baseline:
        cmd += ["--update-baseline"]
    if args.no_gallery:
        cmd += ["--no-gallery"]
    if getattr(args, "tolerance", None) is not None:
        cmd += ["--padding-tolerance", str(args.tolerance)]
    print("running FeaturedWork padding suite only:", " ".join(cmd))
    sys.exit(subprocess.call(cmd))


CONFIG = json.loads(Path(args.config).read_text())
PROFILE_NAME = args.profile or CONFIG.get("defaultProfile", "tanstack")
PROFILE = CONFIG["profiles"][PROFILE_NAME]
BASE_URL = (args.base_url or PROFILE["baseUrl"]).rstrip("/")
TARGET_URL = BASE_URL + PROFILE.get("path", "/")

SEL = CONFIG["selectors"]
EXPECTED_LINES = [line.upper() for line in CONFIG["expectedLines"]]

# Below the wrap breakpoint the headline spans are allowed to wrap, and how
# many rows they take depends on the width: "Experienced by people." needs two
# rows at 320-413px and one from 414px. There is no single correct count there,
# so the exact-count assertion only applies at and above the breakpoint. The
# span text is still asserted at every width, as is the overflow check below —
# which is the property that actually regressed when the line got longer.
WRAP_BREAKPOINT = CONFIG.get("wrapBreakpoint")


def expected_visual_lines(width: int) -> int | None:
    """Rows the H1 must occupy, or None where wrapping makes it width-dependent."""
    if WRAP_BREAKPOINT is not None and width < WRAP_BREAKPOINT:
        return None
    return len(EXPECTED_LINES)


# getClientRects() on a *block* element returns one rect for the whole box, so
# counting it per span reports the number of spans (always 3) no matter how the
# text wraps. A Range over each span's contents returns one rect per line box,
# which is the number this is meant to be checking.
COUNT_ROWS_JS = """(el, sel) => [...el.querySelectorAll(sel)].reduce((n, s) => {
  const r = document.createRange();
  r.selectNodeContents(s);
  return n + r.getClientRects().length;
}, 0)"""

PADDING_TOLERANCE = CONFIG["paddingTolerance"]
PIXEL_THRESHOLD = CONFIG["pixelThreshold"]
MAX_DIFF_RATIO = CONFIG["maxDiffRatio"]
RETRIES = args.retries if args.retries is not None else CONFIG.get("retries", 2)
RETRY_DELAY_MS = CONFIG.get("retryDelayMs", 750)

# Quarantined viewports still run and still report, they just can't fail the run.
QUARANTINE = {v.strip().lower() for v in (args.quarantine or "").split(",") if v.strip()}
QUARANTINE |= {str(v).lower() for v in CONFIG.get("quarantine", [])}

VIEWPORTS = CONFIG["viewports"]


def _match(view, wanted: set[str]) -> bool:
    name = view["name"].lower()
    return name in wanted or str(view["width"]) in wanted or any(w in name for w in wanted)


def _filter(wanted: set[str], label: str) -> list[dict]:
    unmatched = [w for w in wanted if not any(_match(v, {w}) for v in VIEWPORTS)]
    if unmatched:
        known = ", ".join(f"{v['name']} ({v['width']}px)" for v in VIEWPORTS)
        sys.exit(f"unknown {label} viewport(s): {', '.join(sorted(unmatched))}\nknown: {known}")
    return [v for v in VIEWPORTS if _match(v, wanted)]


if args.only:
    VIEWPORTS = _filter({v.strip().lower() for v in args.only.split(",") if v.strip()}, "requested")

# --update-only-failures narrows the run to whatever failed last time and
# re-records just those baselines, leaving every passing baseline untouched.
UPDATE_BASELINE = args.update_baseline
if args.update_only_failures:
    last = Path(args.last_report) if args.last_report else TESTS_DIR / "report-hero.json"
    if not last.exists():
        sys.exit(f"no previous report at {last} — run the suite with --report first")
    prev = json.loads(last.read_text())
    failed = {r["viewport"].lower() for r in prev.get("results", []) if not r.get("passed")}
    if not failed:
        print(f"{last}: no failing viewports to re-record — nothing to do")
        sys.exit(0)
    VIEWPORTS = _filter(failed, "failing")
    UPDATE_BASELINE = True
    print(f"re-recording baselines for failing viewports: {', '.join(sorted(failed))}")

# Baselines are per-profile: rendering engines/harnesses differ subtly.
SCREENSHOTS = TESTS_DIR / "screenshots" / PROFILE_NAME
BASELINES = Path(args.baseline_dir) if args.baseline_dir else TESTS_DIR / "baselines" / PROFILE_NAME
DIFFS = TESTS_DIR / "diffs" / PROFILE_NAME
GALLERY = Path(args.gallery) if args.gallery else TESTS_DIR / "report" / f"hero-gallery-{PROFILE_NAME}.html"



def pixel_diff(name: str, write_diff: bool) -> tuple[str | None, float]:
    """Compare a fresh screenshot to its baseline. Returns (failure, diff ratio)."""
    shot = SCREENSHOTS / f"hero-{name}.png"
    baseline = BASELINES / f"hero-{name}.png"

    if UPDATE_BASELINE or not baseline.exists():
        BASELINES.mkdir(parents=True, exist_ok=True)
        baseline.write_bytes(shot.read_bytes())
        print(f"{name}: baseline recorded")
        return None, 0.0

    current = Image.open(shot).convert("RGB")
    expected = Image.open(baseline).convert("RGB")

    if current.size != expected.size:
        return f"{name}: size changed {expected.size} -> {current.size} (see {shot})", 1.0

    diff = ImageChops.difference(current, expected)
    mask = diff.convert("L").point(lambda v: 255 if v > PIXEL_THRESHOLD else 0)
    changed = sum(mask.histogram()[255:])
    ratio = changed / (current.width * current.height)

    if ratio <= MAX_DIFF_RATIO:
        return None, ratio

    if write_diff:
        DIFFS.mkdir(parents=True, exist_ok=True)
        # baseline | current | changed pixels highlighted magenta over a dimmed render
        highlight = Image.new("RGB", current.size, (255, 0, 255))
        dimmed = Image.blend(current, Image.new("RGB", current.size, (255, 255, 255)), 0.6)
        composite = Image.composite(highlight, dimmed, mask)

        triptych = Image.new("RGB", (current.width * 3, current.height), (255, 255, 255))
        triptych.paste(expected, (0, 0))
        triptych.paste(current, (current.width, 0))
        triptych.paste(composite, (current.width * 2, 0))
        triptych.save(DIFFS / f"hero-{name}-diff.png")

    out = DIFFS / f"hero-{name}-diff.png"
    return f"{name}: {changed} px ({ratio:.2%}) differ from baseline -> {out}", ratio


# Kill every source of frame-to-frame variation before we capture a pixel.
STABILIZE_CSS = """
  *, *::before, *::after {
    animation-duration: 0s !important;
    animation-delay: 0s !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0s !important;
    transition-delay: 0s !important;
    scroll-behavior: auto !important;
  }
  html { caret-color: transparent !important; }
  video, marquee { animation-play-state: paused !important; }
"""


async def stabilize(page) -> None:
    """Freeze animations, settle the network, and force deterministic fonts/images."""
    await page.add_style_tag(content=STABILIZE_CSS)
    await page.evaluate(
        """async () => {
          document.querySelectorAll('video').forEach(v => { v.pause(); v.currentTime = 0; });
          document.getAnimations?.().forEach(a => { try { a.finish(); } catch {} });
          await document.fonts.ready;
          // The app flags final webfont metrics on <html>; wait for it so we
          // never snapshot a fallback-rendered frame.
          if (!document.documentElement.hasAttribute('data-fonts-ready')) {
            await new Promise(resolve => {
              const done = () => resolve();
              const obs = new MutationObserver(() => {
                if (document.documentElement.hasAttribute('data-fonts-ready')) { obs.disconnect(); done(); }
              });
              obs.observe(document.documentElement, { attributes: true, attributeFilter: ['data-fonts-ready'] });
              setTimeout(() => { obs.disconnect(); done(); }, 5000);
            });
          }
          await Promise.all([...document.images]
            .filter(img => !img.complete)
            .map(img => img.decode().catch(() => {})));
          window.scrollTo(0, 0);
        }"""
    )
    try:
        await page.wait_for_load_state("networkidle", timeout=10_000)
    except Exception:
        pass
    # two rAFs: let layout/paint flush after the style + font work above
    await page.evaluate(
        "() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))"
    )


async def attempt_viewport(browser, view, write_diff: bool) -> tuple[list[str], dict]:
    name, width, height = view["name"], view["width"], view["height"]
    failures: list[str] = []

    context = await browser.new_context(
        viewport={"width": width, "height": height},
        reduced_motion="reduce",
    )
    page = await context.new_page()
    await page.goto(TARGET_URL, wait_until="networkidle")
    await stabilize(page)


    h1 = page.locator(SEL["headline"]).first
    line_sel = SEL["headlineLine"]
    lines = [t.strip().upper() for t in await h1.locator(line_sel).all_inner_texts()]
    heights = await h1.evaluate(
        "(el, sel) => [...el.querySelectorAll(sel)].map(s => s.getBoundingClientRect().height)",
        line_sel,
    )
    visual_lines = await h1.evaluate(COUNT_ROWS_JS, line_sel)

    if lines != EXPECTED_LINES:
        failures.append(f"{name}: headline text {lines} != {EXPECTED_LINES}")
    want_visual = expected_visual_lines(width)
    if want_visual is not None and visual_lines != want_visual:
        failures.append(
            f"{name}: headline rendered on {visual_lines} visual lines, want {want_visual}"
        )
    # Applies at every width, wrapping or not: a headline wider than its measure
    # is clipped by the hero stage's overflow-hidden rather than showing as a
    # page scrollbar, so nothing else here would catch it.
    h1_overflow = await h1.evaluate("el => el.scrollWidth - el.clientWidth")
    if h1_overflow > 1:
        failures.append(f"{name}: headline overflows its measure by {h1_overflow}px")
    # Per-row height, not per-span: below the wrap breakpoint one span occupies
    # two rows and is legitimately twice as tall. Dividing by each span's own
    # row count compares like with like at every width.
    rows = await h1.evaluate(
        """(el, sel) => [...el.querySelectorAll(sel)].map(s => {
             const r = document.createRange();
             r.selectNodeContents(s);
             return r.getClientRects().length;
           })""",
        line_sel,
    )
    row_heights = [h / r for h, r in zip(heights, rows) if r]
    if len(set(round(h) for h in row_heights)) != 1:
        failures.append(f"{name}: uneven line heights {row_heights}")

    boxes = {
        "h1": await h1.bounding_box(),
        "label": await page.locator(SEL["label"]).first.bounding_box(),
        "cta": await page.locator(SEL["cta"]).first.bounding_box(),
    }
    left_edges = {k: v["x"] for k, v in boxes.items() if v}
    spread = max(left_edges.values()) - min(left_edges.values())
    if spread > PADDING_TOLERANCE:
        failures.append(f"{name}: left edges misaligned by {spread:.1f}px {left_edges}")

    await page.locator(SEL["hero"]).screenshot(path=str(SCREENSHOTS / f"hero-{name}.png"))


    diff_failure, ratio = pixel_diff(name, write_diff)
    if diff_failure:
        failures.append(diff_failure)

    await context.close()
    return failures, {"lines": visual_lines, "leftEdges": left_edges, "diffRatio": ratio}


async def check_viewport(browser, view) -> dict:
    """Run a viewport, retrying transient failures before reporting one."""
    name = view["name"]
    attempts = 0
    failures: list[str] = []
    meta: dict = {}

    for attempt in range(RETRIES + 1):
        attempts = attempt + 1
        last = attempt == RETRIES
        failures, meta = await attempt_viewport(browser, view, write_diff=last)
        if not failures:
            if attempt:
                print(f"{name}: passed on retry {attempt}")
            break
        if not last:
            print(f"{name}: attempt {attempts} failed, retrying — {failures[0]}")
            await asyncio.sleep(RETRY_DELAY_MS / 1000)

    edges = {k: round(v, 1) for k, v in meta.get("leftEdges", {}).items()}
    print(f"{name}: lines={meta.get('lines')} left_edges={edges} attempts={attempts}")

    quarantined = _match(view, QUARANTINE) if QUARANTINE else False
    if failures and quarantined:
        print(f"{name}: QUARANTINED — {len(failures)} failure(s) reported but not failing the run")

    diff_path = DIFFS / f"hero-{name}-diff.png"
    return {
        "viewport": name,
        "width": view["width"],
        "height": view["height"],
        "lines": meta.get("lines"),
        "attempts": attempts,
        "flaky": attempts > 1 and not failures,
        "quarantined": quarantined,
        "diffRatio": round(meta.get("diffRatio", 0.0), 6),
        "screenshot": str((SCREENSHOTS / f"hero-{name}.png").relative_to(TESTS_DIR.parent)),
        "diff": str(diff_path.relative_to(TESTS_DIR.parent)) if diff_path.exists() else None,
        "failures": failures,
        "passed": not failures,
        "blocking": bool(failures) and not quarantined,
    }



def write_gallery(report: dict) -> None:
    """Render an HTML gallery of every viewport, failures first."""
    GALLERY.parent.mkdir(parents=True, exist_ok=True)
    root = TESTS_DIR.parent

    def rel(p: str | None) -> str | None:
        if not p:
            return None
        try:
            import os

            return os.path.relpath(root / p, GALLERY.parent)
        except ValueError:
            return p

    order = sorted(report["results"], key=lambda r: (r["passed"], r["width"]))
    cards = []
    for r in order:
        if not r["passed"]:
            status = "QUARANTINED" if r.get("quarantined") else "FAIL"
        else:
            status = "FLAKY" if r["flaky"] else "PASS"
        cls = status.lower()
        shot = rel(r["screenshot"])
        diff = rel(r["diff"])
        fails = "".join(f"<li>{html.escape(f)}</li>" for f in r["failures"])
        images = f'<figure><figcaption>current</figcaption><img src="{shot}" alt="{r["viewport"]} hero"></figure>'
        if diff and not r["passed"]:
            images += (
                f'<figure><figcaption>baseline | current | highlighted diff</figcaption>'
                f'<img src="{diff}" alt="{r["viewport"]} diff"></figure>'
            )
        cards.append(
            f"""<section class="card {cls}" id="{r['viewport']}">
  <header><h2>{r['viewport']} <small>{r['width']}×{r['height']}</small></h2>
  <span class="badge {cls}">{status}</span></header>
  <p class="meta">lines: {r['lines']} · attempts: {r['attempts']} · diff: {r['diffRatio']:.3%}</p>
  {f'<ul class="failures">{fails}</ul>' if fails else ''}
  <div class="shots">{images}</div>
</section>"""
        )

    failed = [r["viewport"] for r in report["results"] if r.get("blocking")]
    flaky = [r["viewport"] for r in report["results"] if r["flaky"]]
    quarantined = [r["viewport"] for r in report["results"] if r.get("quarantined")]
    summary = (
        f'<p class="fail-list"><strong>Failed:</strong> {", ".join(failed)}</p>'
        if failed
        else '<p class="ok">All viewports match their baselines.</p>'
    )
    if flaky:
        summary += f'<p class="flaky-list"><strong>Recovered on retry:</strong> {", ".join(flaky)}</p>'
    if quarantined:
        summary += (
            '<p class="quarantined-list"><strong>Quarantined (non-blocking):</strong> '
            f'{", ".join(quarantined)}</p>'
        )


    GALLERY.write_text(
        f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Hero visual regression — {report['profile']}</title>
<style>
  :root {{ color-scheme: light dark; }}
  body {{ font: 15px/1.5 ui-sans-serif, system-ui, sans-serif; margin: 0; padding: 2rem; background: #f6f5f1; color: #111; }}
  h1 {{ margin: 0 0 .25rem; font-size: 1.5rem; }}
  .sub {{ color: #666; margin: 0 0 1.5rem; }}
  .card {{ background: #fff; border: 1px solid #e4e2dc; border-left: 6px solid #2e9b5b; border-radius: 10px; padding: 1rem 1.25rem; margin-bottom: 1.25rem; }}
  .card.fail {{ border-left-color: #d61f26; }}
  .card.flaky {{ border-left-color: #d9820a; }}
  .card.quarantined {{ border-left-color: #7a5af5; }}
  header {{ display: flex; align-items: center; justify-content: space-between; gap: 1rem; }}
  h2 {{ font-size: 1.1rem; margin: 0; }}
  small {{ color: #888; font-weight: 400; }}
  .badge {{ font-size: .72rem; letter-spacing: .12em; padding: .25rem .55rem; border-radius: 999px; background: #2e9b5b; color: #fff; }}
  .badge.fail {{ background: #d61f26; }}
  .badge.flaky {{ background: #d9820a; }}
  .badge.quarantined {{ background: #7a5af5; }}
  .meta {{ color: #666; font-size: .85rem; margin: .4rem 0 .6rem; }}
  .failures {{ color: #d61f26; margin: 0 0 .75rem; padding-left: 1.1rem; }}
  .shots {{ display: grid; gap: 1rem; }}
  figure {{ margin: 0; }}
  figcaption {{ font-size: .72rem; letter-spacing: .1em; text-transform: uppercase; color: #888; margin-bottom: .35rem; }}
  img {{ max-width: 100%; border: 1px solid #e4e2dc; border-radius: 6px; display: block; }}
  .fail-list {{ color: #d61f26; }} .flaky-list {{ color: #d9820a; }} .quarantined-list {{ color: #7a5af5; }} .ok {{ color: #2e9b5b; }}
</style></head>
<body>
<h1>Hero visual regression — {report['profile']}</h1>
<p class="sub">{html.escape(report['url'])} · {len(report['results'])} viewports · retries: {RETRIES}</p>
{summary}
{''.join(cards)}
</body></html>"""
    )
    print(f"gallery written to {GALLERY}")


async def main() -> int:
    SCREENSHOTS.mkdir(parents=True, exist_ok=True)
    results: list[dict] = []
    print(f"profile={PROFILE_NAME} url={TARGET_URL} viewports={len(VIEWPORTS)} retries={RETRIES}")

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        for view in VIEWPORTS:
            results.append(await check_viewport(browser, view))
        await browser.close()

    blocking = [f for r in results if r["blocking"] for f in r["failures"]]
    quarantined = [f for r in results if r.get("quarantined") for f in r["failures"]]
    report = {
        "suite": "hero-visual-regression",
        "profile": PROFILE_NAME,
        "url": TARGET_URL,
        "passed": not blocking,
        "retries": RETRIES,
        "quarantine": sorted(QUARANTINE),
        "results": results,
        "diffDir": str(DIFFS.relative_to(TESTS_DIR.parent)),
    }
    if not args.no_gallery:
        write_gallery(report)
        report["gallery"] = str(GALLERY.relative_to(TESTS_DIR.parent))
    if args.report:
        Path(args.report).parent.mkdir(parents=True, exist_ok=True)
        Path(args.report).write_text(json.dumps(report, indent=2))
        print(f"report written to {args.report}")

    if quarantined:
        print("\nQUARANTINED (not failing the run)")
        for f in quarantined:
            print(" -", f)

    if blocking:
        print("\nFAIL")
        for f in blocking:
            print(" -", f)
        print(f"\nDiff images (baseline | current | highlighted): {DIFFS}")
        print("Re-record only these baselines: python3 tests/hero-headline.py "
              "--update-only-failures --last-report <report.json>")
        return 1
    print(f"\nPASS: hero holds {len(EXPECTED_LINES)} lines and matches baselines at every viewport")
    return 0


sys.exit(asyncio.run(main()))
