#!/usr/bin/env python3
"""Regression checks for the SiteFooter contact column.

Verifies:
  - the Contact email reads "hello@thebrandledger.com";
  - the email is a clickable mailto: link;
  - the phone number reads "(402) 957-2262" and is a tel: link;
  - the location reads "Omaha, NE";
  - the contact column renders without visual drift against the baseline.

Usage:
    python3 tests/footer-contact.py
    python3 tests/footer-contact.py --base-url http://localhost:3000
    python3 tests/footer-contact.py --update-baseline
    python3 tests/footer-contact.py --report tests/report-footer-contact.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parent
BASELINES = ROOT / "baselines" / "footer-contact"
SCREENSHOTS = ROOT / "screenshots" / "footer-contact"
DIFFS = ROOT / "diffs" / "footer-contact"
REPORTS = ROOT / "report"

EXPECTED_EMAIL = "hello@thebrandledger.com"
EXPECTED_MAILTO = "mailto:hello@thebrandledger.com"
EXPECTED_PHONE = "(402) 957-2262"
EXPECTED_TEL = "tel:+14029572262"
# Must match `contact` / `addressLines` in lib/site.ts. The footer published
# only "Omaha, Nebraska" until the studio's street address was added; asserting
# both lines means the suite now guards the real address rather than just the
# city, and a half-applied change to lib/site.ts fails here instead of shipping.
EXPECTED_STREET = "6311 Ames Ave, Unit 198"
EXPECTED_LOCATION = "Omaha, NE 68104"

# These must match the projects exported from lib/projects.ts.
EXPECTED_WORK_PROJECTS = [
    ("Heartland Plein Air Festival", "heartland-plein-air-festival"),
]
EXPECTED_ABOUT_ITEMS = ["The Studio"]

VIEWPORTS = [
    ("mobile-375", 375, 812),
    ("desktop-1280", 1280, 900),
]

parser = argparse.ArgumentParser(description="SiteFooter contact regression checks")
parser.add_argument("base_url", nargs="?", default="http://localhost:3000")
parser.add_argument("--update-baseline", action="store_true")
parser.add_argument("--baseline-dir", default=str(BASELINES))
parser.add_argument("--screenshot-dir", default=str(SCREENSHOTS))
parser.add_argument("--diff-dir", default=str(DIFFS))
parser.add_argument("--report", default=None)
parser.add_argument("--tolerance", type=float, default=0.01)
args = parser.parse_args()

BASE_URL = args.base_url.rstrip("/")
BASELINE_DIR = Path(args.baseline_dir)
SCREENSHOT_DIR = Path(args.screenshot_dir)
DIFF_DIR = Path(args.diff_dir)


def ensure_dirs() -> None:
    BASELINE_DIR.mkdir(parents=True, exist_ok=True)
    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
    DIFF_DIR.mkdir(parents=True, exist_ok=True)


async def stabilize(page) -> None:
    await page.add_style_tag(
        content="*,*::before,*::after{animation:none!important;transition:none!important}"
    )
    await page.evaluate("document.fonts ? document.fonts.ready : null")
    await page.wait_for_load_state("networkidle")
    await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    # Give the footer a moment to settle into the viewport after the scroll.
    await page.wait_for_timeout(150)


async def run_assertions(page) -> list[str]:
    failures: list[str] = []

    contact_column = await page.query_selector('footer p:text-is("Contact") + ul')
    if contact_column is None:
        failures.append("Could not locate the Contact column in the footer")
        return failures

    text = await contact_column.inner_text() or ""

    if EXPECTED_EMAIL not in text:
        failures.append(f"Expected email {EXPECTED_EMAIL!r}, got {text!r}")

    if EXPECTED_PHONE not in text:
        failures.append(f"Expected phone {EXPECTED_PHONE!r}, got {text!r}")

    if EXPECTED_STREET not in text:
        failures.append(f"Expected street {EXPECTED_STREET!r}, got {text!r}")

    if EXPECTED_LOCATION not in text:
        failures.append(f"Expected location {EXPECTED_LOCATION!r}, got {text!r}")

    email_link = await contact_column.query_selector(f'a[href="{EXPECTED_MAILTO}"]')
    if email_link is None:
        # Try a broader selector in case the mailto has extra params.
        email_link = await contact_column.query_selector('a[href^="mailto:"]')
        if email_link is None:
            failures.append("Email is not rendered as a mailto: link")
        else:
            href = await email_link.get_attribute("href") or ""
            if EXPECTED_EMAIL not in href:
                failures.append(f"mailto link points to wrong address: {href!r}")
    else:
        link_text = await email_link.inner_text() or ""
        if link_text.strip() != EXPECTED_EMAIL:
            failures.append(f"mailto link text is {link_text!r}, expected {EXPECTED_EMAIL!r}")

    phone_link = await contact_column.query_selector(f'a[href="{EXPECTED_TEL}"]')
    if phone_link is None:
        failures.append("Phone number is not rendered as a tel: link")
    else:
        link_text = await phone_link.inner_text() or ""
        if link_text.strip() != EXPECTED_PHONE:
            failures.append(f"tel link text is {link_text!r}, expected {EXPECTED_PHONE!r}")

    return failures


async def run_work_assertions(page) -> list[str]:
    failures: list[str] = []

    work_column = await page.query_selector('footer p:text-is("Work") + ul')
    if work_column is None:
        failures.append("Could not locate the Work column in the footer")
        return failures

    text = await work_column.inner_text() or ""
    for name, _slug in EXPECTED_WORK_PROJECTS:
        if name not in text:
            failures.append(f"Expected work project {name!r} in footer Work column, got {text!r}")

    for name, slug in EXPECTED_WORK_PROJECTS:
        link = await work_column.query_selector(f'a[href="/?work={slug}#work"]')
        if link is None:
            failures.append(f"Work project {name!r} is missing link /?work={slug}#work")
            continue
        link_text = await link.inner_text() or ""
        if link_text.strip() != name:
            failures.append(f"Work link text is {link_text!r}, expected {name!r}")

    return failures


async def run_about_assertions(page) -> list[str]:
    failures: list[str] = []

    about_column = await page.query_selector('footer p:text-is("About") + ul')
    if about_column is None:
        failures.append("Could not locate the About column in the footer")
        return failures

    text = await about_column.inner_text() or ""
    for item in EXPECTED_ABOUT_ITEMS:
        if item not in text:
            failures.append(f"Expected About item {item!r}, got {text!r}")

    unexpected = {"Team", "Recognition", "Careers"}
    for item in unexpected:
        if item in text:
            failures.append(f"About column still contains removed item {item!r}")

    studio_link = await about_column.query_selector('a[href="#about"]')
    if studio_link is None:
        failures.append("The Studio is not rendered as a link to #about")

    return failures


async def capture_contact_screenshot(page, name: str) -> Path:
    footer = await page.query_selector("footer")
    assert footer is not None
    path = SCREENSHOT_DIR / f"{name}.png"
    await footer.screenshot(path=str(path))
    return path


async def compare_baseline(current: Path, baseline: Path) -> tuple[bool, Path | None, float]:
    from PIL import Image, ImageChops

    if not baseline.exists():
        return False, None, 0.0

    current_img = Image.open(current).convert("RGB")
    baseline_img = Image.open(baseline).convert("RGB")

    if current_img.size != baseline_img.size:
        return False, None, 1.0

    diff = ImageChops.difference(current_img, baseline_img)
    bbox = diff.getbbox()
    if bbox is None:
        return True, None, 0.0

    diff_pixels = sum(1 for p in diff.getdata() if any(c != 0 for c in p))
    total_pixels = current_img.size[0] * current_img.size[1]
    ratio = diff_pixels / total_pixels

    diff_path = DIFF_DIR / f"{current.stem}-diff.png"
    # Highlight changed pixels in magenta over the current image.
    overlay = current_img.copy()
    mask = diff.convert("L").point(lambda v: 255 if v else 0)
    magenta = Image.new("RGB", current_img.size, (255, 0, 255))
    overlay = Image.composite(magenta, overlay, mask)
    overlay.save(diff_path)

    return ratio <= args.tolerance, diff_path, ratio


async def main() -> int:
    ensure_dirs()
    results: list[dict] = []
    all_failures: list[str] = []

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        for viewport_name, width, height in VIEWPORTS:
            context = await browser.new_context(viewport={"width": width, "height": height})
            page = await context.new_page()
            await page.goto(BASE_URL + "/")
            await stabilize(page)

            assertion_failures = (
                await run_assertions(page)
                + await run_work_assertions(page)
                + await run_about_assertions(page)
            )
            screenshot = await capture_contact_screenshot(page, f"footer-contact-{viewport_name}")
            baseline = BASELINE_DIR / f"footer-contact-{viewport_name}.png"

            # Record when the baseline is absent instead of failing. Every
            # other visual suite in this directory already does this, and the
            # workflow's "recorded-baselines" artifact depends on it: a fresh
            # baseline set can only be produced by a run that goes green, gets
            # uploaded, and is then committed to become a real comparison.
            # footer-contact was the sole holdout, so retiring its baselines
            # alongside the others failed CI on "missing baseline" while the
            # rest recorded and passed.
            if args.update_baseline or not baseline.exists():
                baseline.parent.mkdir(parents=True, exist_ok=True)
                screenshot.replace(baseline)
                visual_ok = True
                diff_path = None
                diff_ratio = 0.0
            else:
                visual_ok, diff_path, diff_ratio = await compare_baseline(screenshot, baseline)

            combined_failures = assertion_failures[:]
            if not visual_ok:
                combined_failures.append(
                    f"visual drift {diff_ratio * 100:.3f}% (tolerance {args.tolerance * 100:.3f}%)"
                )

            passed = not combined_failures
            all_failures.extend(f"{viewport_name}: {f}" for f in combined_failures)
            results.append(
                {
                    "viewport": viewport_name,
                    "width": width,
                    "height": height,
                    "passed": passed,
                    "failures": combined_failures,
                    "screenshot": str(screenshot.relative_to(ROOT)),
                    "baseline": str(baseline.relative_to(ROOT)),
                    "diff": str(diff_path.relative_to(ROOT)) if diff_path else None,
                    "diffRatio": diff_ratio,
                }
            )
            status = "PASS" if passed else "FAIL"
            print(f"{status} {viewport_name}")
            for f in combined_failures:
                print(f"   - {f}")

            await context.close()

        await browser.close()

    report = {
        "suite": "footer-contact",
        "url": BASE_URL,
        "passed": not all_failures,
        "tolerance": args.tolerance,
        "results": results,
    }
    if args.report:
        report_path = Path(args.report)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, indent=2))

    if all_failures:
        print(f"\nFAIL: {len(all_failures)} issue(s) in footer contact")
        return 1
    print("\nPASS: footer contact is correct and matches baseline")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
