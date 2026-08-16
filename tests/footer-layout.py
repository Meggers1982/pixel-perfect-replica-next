"""Per-section visual regression for the SiteFooter across every breakpoint.

The footer is checked as three INDEPENDENT blocks so a failure names the
exact block that regressed instead of one opaque whole-footer diff:

  * links     -- the four link columns below the divider
                 (column count per row, left padding-edge alignment,
                  dynamic copyright year)
  * divider   -- the horizontal rule above the link columns
                 (spans the full container content width)
  * watermark -- the "MADE IN OMAHA" display line
                 (stays on one line, never overflows the content box)

Each block gets its own screenshot, its own baseline, its own diff image and
its own entry in the JSON report, so blocks fail (and get re-baselined)
independently of each other.

Usage:
    python3 tests/footer-layout.py                       # verify vs baselines
    python3 tests/footer-layout.py --update-baseline     # (re-)record
    python3 tests/footer-layout.py --section links       # one block only
    python3 tests/footer-layout.py --only 320,desktop-1440
    python3 tests/footer-layout.py http://localhost:3000

Requires the app running plus Pillow + Playwright.
"""

import argparse
import asyncio
import datetime
import json
import shutil
import sys
from pathlib import Path

from PIL import Image, ImageChops
from playwright.async_api import async_playwright

TESTS_DIR = Path(__file__).parent
BASELINES = TESTS_DIR / "baselines" / "footer"
SHOTS = TESTS_DIR / "screenshots" / "footer"
DIFFS = TESTS_DIR / "diffs" / "footer"
# Self-contained bundle uploaded as a CI artifact when a comparison fails:
# baseline + current + highlighted diff for each failing section/viewport.
FAILURES = TESTS_DIR / "report" / "footer-failures"

PIXEL_THRESHOLD = 12  # per-channel noise ignored
MAX_DIFF_RATIO = 0.005  # 0.5% of pixels may differ (AA jitter)
RETRIES = 2

SECTIONS = ("links", "divider", "watermark")

VIEWPORTS = [
    {"name": "mobile-320", "width": 320, "height": 900, "columns": 1},
    {"name": "mobile-375", "width": 375, "height": 900, "columns": 1},
    {"name": "mobile-414", "width": 414, "height": 900, "columns": 1},
    {"name": "tablet-768", "width": 768, "height": 1024, "columns": 2},
    {"name": "laptop-1024", "width": 1024, "height": 900, "columns": 4},
    {"name": "desktop-1280", "width": 1280, "height": 900, "columns": 4},
    {"name": "desktop-1440", "width": 1440, "height": 900, "columns": 4},
    {"name": "desktop-1920", "width": 1920, "height": 1080, "columns": 4},
]

parser = argparse.ArgumentParser()
parser.add_argument("base_url", nargs="?", default="http://localhost:3000")
parser.add_argument("--update-baseline", action="store_true")
parser.add_argument("--only", default=None, help="comma-separated names or widths")
parser.add_argument(
    "--section",
    default=None,
    help=f"comma-separated blocks to check ({', '.join(SECTIONS)})",
)
parser.add_argument(
    "--report",
    default=str(TESTS_DIR / "report-footer-layout.json"),
    help="JSON report path (artifact index of screenshots/diffs)",
)
args = parser.parse_args()

TARGET_URL = args.base_url.rstrip("/") + "/"

selected = VIEWPORTS
if args.only:
    wanted = {t.strip() for t in args.only.split(",") if t.strip()}
    selected = [
        v for v in VIEWPORTS if v["name"] in wanted or str(v["width"]) in wanted
    ]
    if not selected:
        sys.exit(f"no viewport matches --only {args.only}")

sections = SECTIONS
if args.section:
    wanted = {s.strip() for s in args.section.split(",") if s.strip()}
    unknown = wanted - set(SECTIONS)
    if unknown:
        sys.exit(f"unknown section(s): {', '.join(sorted(unknown))}")
    sections = tuple(s for s in SECTIONS if s in wanted)

STABILIZE_CSS = """
  *, *::before, *::after {
    animation-duration: 0s !important;
    animation-delay: 0s !important;
    transition-duration: 0s !important;
    transition-delay: 0s !important;
    scroll-behavior: auto !important;
  }
  html { caret-color: transparent !important; }
"""


async def stabilize(page) -> None:
    await page.add_style_tag(content=STABILIZE_CSS)
    await page.evaluate(
        """async () => {
          document.getAnimations?.().forEach(a => { try { a.finish(); } catch {} });
          await document.fonts.ready;
          if (!document.documentElement.hasAttribute('data-fonts-ready')) {
            await new Promise(resolve => {
              const obs = new MutationObserver(() => {
                if (document.documentElement.hasAttribute('data-fonts-ready')) {
                  obs.disconnect(); resolve();
                }
              });
              obs.observe(document.documentElement,
                { attributes: true, attributeFilter: ['data-fonts-ready'] });
              setTimeout(() => { obs.disconnect(); resolve(); }, 5000);
            });
          }
          await Promise.all([...document.images]
            .filter(img => !img.complete)
            .map(img => img.decode().catch(() => {})));
        }"""
    )
    try:
        await page.wait_for_load_state("networkidle", timeout=10_000)
    except Exception:
        pass
    await page.evaluate(
        "() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))"
    )


# --- geometry shared by every section check -------------------------------

MEASURE_JS = """() => {
  const footer = document.querySelector('footer#contact');
  const inner = footer.firstElementChild;
  const grid = [...footer.querySelectorAll('div')]
    .find(d => d.className.includes('border-t'));
  const cols = [...grid.children];
  const rows = new Set(cols.map(c => Math.round(c.getBoundingClientRect().top)));
  const mark = [...footer.querySelectorAll('p')]
    .find(p => p.textContent.includes('MADE IN OMAHA'));
  const copy = [...footer.querySelectorAll('p')]
    .find(p => p.textContent.includes('\\u00a9'));
  const cs = getComputedStyle(inner);
  const box = inner.getBoundingClientRect();
  const contentLeft = box.left + parseFloat(cs.paddingLeft);
  const contentRight = box.right - parseFloat(cs.paddingRight);
  const gridBox = grid.getBoundingClientRect();
  const markBox = mark.getBoundingClientRect();
  const markLh = parseFloat(getComputedStyle(mark).lineHeight);
  const borderTop = parseFloat(getComputedStyle(grid).borderTopWidth) || 1;
  const r = n => Math.round(n);
  return {
    perRow: cols.length / rows.size,
    colLefts: cols.map(c => r(c.getBoundingClientRect().left)),
    contentLeft: r(contentLeft),
    contentRight: r(contentRight),
    gridLeft: r(gridBox.left),
    gridRight: r(gridBox.right),
    markLines: Math.round(markBox.height / markLh),
    markOverflow: markBox.right > contentRight + 1,
    copyText: copy.textContent.trim(),
    dividerWidth: borderTop,
  };
}"""


def check_links(data, view) -> list[str]:
    problems = []
    if round(data["perRow"]) != view["columns"]:
        problems.append(
            f"link columns per row = {data['perRow']}, want {view['columns']}"
        )
    first_row = data["colLefts"][: view["columns"]]
    if first_row and first_row[0] != data["contentLeft"]:
        problems.append(
            f"first link column left {first_row[0]} != content edge {data['contentLeft']}"
        )
    year = datetime.date.today().year
    if data["copyText"] != f"© {year} Brand Ledger":
        problems.append(
            f"copyright reads {data['copyText']!r}, want '© {year} Brand Ledger'"
        )
    return problems


def check_divider(data, view) -> list[str]:
    if data["gridLeft"] != data["contentLeft"] or data["gridRight"] != data["contentRight"]:
        return [
            f"divider rule spans {data['gridLeft']}-{data['gridRight']}, "
            f"want {data['contentLeft']}-{data['contentRight']}"
        ]
    return []


def check_watermark(data, view) -> list[str]:
    problems = []
    if data["markLines"] != 1:
        problems.append(f"watermark wrapped onto {data['markLines']} lines")
    if data["markOverflow"]:
        problems.append("watermark overflows the content box")
    return problems


CHECKS = {"links": check_links, "divider": check_divider, "watermark": check_watermark}


def collect_failure_artifacts(section: str, name: str, shot: Path, diff: Path | None) -> dict:
    """Copy the baseline/current/diff triplet into one CI-artifact folder."""
    out_dir = FAILURES / section
    out_dir.mkdir(parents=True, exist_ok=True)
    baseline = BASELINES / section / f"{section}-{name}.png"
    bundle: dict[str, str] = {}
    for label, src in (("baseline", baseline), ("current", shot), ("diff", diff)):
        if src and src.exists():
            dest = out_dir / f"{section}-{name}-{label}.png"
            shutil.copyfile(src, dest)
            bundle[label] = str(dest.relative_to(TESTS_DIR))
    return bundle


def compare(section: str, name: str, shot: Path) -> tuple[str | None, float, Path | None]:
    baseline = BASELINES / section / f"{section}-{name}.png"
    if args.update_baseline or not baseline.exists():
        baseline.parent.mkdir(parents=True, exist_ok=True)
        Image.open(shot).save(baseline)
        return None, 0.0, None

    expected = Image.open(baseline).convert("RGB")
    current = Image.open(shot).convert("RGB")
    if expected.size != current.size:
        return f"size changed {expected.size} -> {current.size}", 1.0, None

    diff = ImageChops.difference(expected, current).convert("L")
    mask = diff.point(lambda p: 255 if p > PIXEL_THRESHOLD else 0)
    changed = sum(1 for p in mask.getdata() if p)
    ratio = changed / (current.width * current.height)
    if ratio <= MAX_DIFF_RATIO:
        return None, ratio, None

    out_dir = DIFFS / section
    out_dir.mkdir(parents=True, exist_ok=True)
    dimmed = Image.blend(current, Image.new("RGB", current.size, (255, 255, 255)), 0.6)
    highlight = Image.new("RGB", current.size, (255, 0, 0))
    composite = Image.composite(highlight, dimmed, mask)
    triptych = Image.new("RGB", (current.width * 3, current.height), (255, 255, 255))
    triptych.paste(expected, (0, 0))
    triptych.paste(current, (current.width, 0))
    triptych.paste(composite, (current.width * 2, 0))
    out = out_dir / f"{section}-{name}-diff.png"
    triptych.save(out)
    return (f"{changed} px ({ratio:.2%}) differ from baseline -> {out}", ratio, out)


async def capture_sections(page, view) -> tuple[dict, dict[str, Path]]:
    """Measure once, then screenshot each section block separately."""
    data = await page.evaluate(MEASURE_JS)

    grid = page.locator("footer#contact div.border-t").first
    mark = page.locator("footer#contact p", has_text="MADE IN OMAHA").first
    box = await grid.bounding_box()
    rule_h = max(6, round(data["dividerWidth"]) + 4)

    targets = {
        "links": (grid, None),
        "divider": (grid, {"x": 0, "y": 0, "width": box["width"], "height": rule_h}),
        "watermark": (mark, None),
    }

    shots: dict[str, Path] = {}
    for section in sections:
        locator, clip = targets[section]
        out_dir = SHOTS / section
        out_dir.mkdir(parents=True, exist_ok=True)
        shot = out_dir / f"{section}-{view['name']}.png"
        await locator.screenshot(path=str(shot))
        if clip:
            # crop the grid capture down to just the horizontal rule
            img = Image.open(shot)
            scale = img.width / max(1, clip["width"])
            img.crop((0, 0, img.width, max(1, round(clip["height"] * scale)))).save(shot)
        shots[section] = shot
    return data, shots


async def run_viewport(browser, view) -> tuple[list[str], list[dict]]:
    name = view["name"]
    results = {
        section: {
            "section": section,
            "viewport": name,
            "width": view["width"],
            "height": view["height"],
            "columns": view["columns"],
            "passed": False,
            "diffRatio": 0.0,
            "attempts": 0,
            "failures": [],
            "artifacts": {},
        }
        for section in sections
    }
    pending = list(sections)

    for attempt in range(1, RETRIES + 2):
        context = await browser.new_context(
            viewport={"width": view["width"], "height": view["height"]},
            reduced_motion="reduce",
        )
        page = await context.new_page()
        await page.goto(TARGET_URL, wait_until="networkidle")
        await stabilize(page)

        footer = page.locator("footer#contact")
        await footer.scroll_into_view_if_needed()
        await stabilize(page)

        data, shots = await capture_sections(page, view)
        await context.close()

        still_failing = []
        for section in pending:
            result = results[section]
            problems = [f"{section}/{name}: {p}" for p in CHECKS[section](data, view)]
            diff_msg, ratio, diff_path = compare(section, name, shots[section])
            if diff_msg:
                problems.append(f"{section}/{name}: {diff_msg}")

            result["attempts"] = attempt
            result["diffRatio"] = ratio
            result["screenshot"] = str(shots[section].relative_to(TESTS_DIR))
            result["failures"] = problems

            if problems:
                result["artifacts"] = collect_failure_artifacts(
                    section, name, shots[section], diff_path
                )
                still_failing.append(section)
            else:
                result["passed"] = True
                result["artifacts"] = {}
                print(f"{section}/{name}: OK (diff {ratio:.3%}) attempts={attempt}")

        pending = still_failing
        if not pending:
            break
        if attempt <= RETRIES:
            print(
                f"{name}: retrying {', '.join(pending)} — "
                f"{results[pending[0]]['failures'][0]}"
            )
            await asyncio.sleep(0.75)

    failures = [f for section in sections for f in (
        results[section]["failures"] if not results[section]["passed"] else []
    )]
    return failures, [results[s] for s in sections]


async def main() -> int:
    failures: list[str] = []
    results: list[dict] = []

    if FAILURES.exists():
        shutil.rmtree(FAILURES)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        for view in selected:
            problems, section_results = await run_viewport(browser, view)
            failures += problems
            results += section_results
        await browser.close()

    by_section = {
        section: {
            "passed": all(
                r["passed"] for r in results if r["section"] == section
            ),
            "failedViewports": [
                r["viewport"] for r in results if r["section"] == section and not r["passed"]
            ],
        }
        for section in sections
    }

    report = {
        "suite": "footer-layout",
        "url": TARGET_URL,
        "passed": not failures,
        "maxDiffRatio": MAX_DIFF_RATIO,
        "artifactDir": str(FAILURES.relative_to(TESTS_DIR)),
        "sections": by_section,
        "results": results,
    }
    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2) + "\n")
    print(f"\nreport -> {report_path}")

    for section, summary in by_section.items():
        status = "PASS" if summary["passed"] else (
            "FAIL @ " + ", ".join(summary["failedViewports"])
        )
        print(f"  {section:<9} {status}")

    if failures:
        print("\nFAIL")
        for f in failures:
            print(" -", f)
        print(f"\nDiff images (baseline | current | highlighted): {DIFFS}")
        print(f"Failure bundle per section: {FAILURES}")
        return 1

    verb = "recorded" if args.update_baseline else "matches baseline"
    print(f"\nPASS: footer sections {verb} at every breakpoint")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
