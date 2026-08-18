#!/usr/bin/env python3
"""Mobile Featured Work carousel checks.

Covers:
  1. arrow navigation moves the visible project and updates the "01 / 04" counter;
  2. wraparound in both directions;
  3. ARIA labelling of arrows, slides and the live counter;
  4. keyboard left/right arrow navigation inside the track;
  5. reduced-motion disables smooth scrolling / thumbnail transitions.

Usage:
  python3 tests/featured-work-carousel.py
  python3 tests/featured-work-carousel.py --base-url http://localhost:3000 \
      --report tests/report-carousel.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parent

MOBILE = {"width": 393, "height": 851}
COUNT = 4
FIRST = "Heartland Plein Air Festival"
SECOND = "Hollow Roasters"
LAST = "Meridian Health"

_SUITE = "featured-work-carousel"

def _project_count() -> int:
    """Read the shared projects array so this suite tracks lib/projects.ts."""
    import json as _json, subprocess as _sub
    out = _sub.run(
        ["node", "--input-type=module", "-e",
         'const m = await import("./lib/projects.ts"); console.log(JSON.stringify(m.projects));'],
        cwd=ROOT.parent, capture_output=True, text=True, check=True,
    )
    return len(_json.loads(out.stdout.strip().splitlines()[-1]))


# Everything below steps between projects. With a single project the carousel
# nav is not rendered at all, so there is nothing here to exercise — skip
# loudly rather than assert against UI that is absent by design. The deep-link,
# focus and history behaviour this suite overlaps on is covered by the
# footer-work-* suites, which read the project list dynamically.
_COUNT = _project_count()
if _COUNT < 2:
    print(f"SKIP: {_SUITE} needs at least 2 projects to step between; lib/projects.ts has {_COUNT}.")
    raise SystemExit(0)


class Results:
    def __init__(self) -> None:
        self.rows: list[dict] = []

    def check(self, name: str, ok: bool, detail: str = "") -> None:
        self.rows.append({"name": name, "status": "pass" if ok else "fail", "detail": detail})
        print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"  — {detail}" if detail else ""))

    @property
    def failed(self) -> list[dict]:
        return [r for r in self.rows if r["status"] != "pass"]


async def settle(page) -> None:
    await page.wait_for_timeout(700)


async def current_slide(page) -> int:
    """Index of the slide nearest the track's inline edge (LTR and RTL safe)."""
    return await page.evaluate(
        """() => {
          const track = document.getElementById('featured-work-track');
          const left = track.getBoundingClientRect().left;
          let best = Infinity, idx = 0;
          [...track.children].forEach((c, i) => {
            const d = Math.abs(c.getBoundingClientRect().left - left);
            if (d < best) { best = d; idx = i; }
          });
          return idx;
        }"""
    )



async def counter_text(page) -> str:
    return (await page.get_by_test_id("carousel-counter").inner_text()).strip()


async def live_text(page) -> str:
    return (await page.locator("#work [role=status]").inner_text()).strip()


async def open_page(context, base_url: str):
    page = await context.new_page()
    await page.goto(base_url, wait_until="domcontentloaded")
    await page.locator("#featured-work-track").scroll_into_view_if_needed()
    try:
        await page.wait_for_load_state("networkidle", timeout=10000)
    except Exception:
        pass
    # Wait for hydration: the arrows only mutate state once React attaches.
    for _ in range(40):
        if await page.evaluate(
            "() => !!document.querySelector('[data-testid=carousel-next]')?.onclick"
            " || !!Object.keys(document.querySelector('[data-testid=carousel-next]') ?? {})"
            ".find((k) => k.startsWith('__react'))"
        ):
            break
        await page.wait_for_timeout(150)
    await settle(page)
    return page


async def navigation_case(context, base_url: str, res: Results) -> None:
    page = await open_page(context, base_url)
    nxt = page.get_by_test_id("carousel-next")
    prev = page.get_by_test_id("carousel-prev")

    res.check("counter starts at 01 / 04", await counter_text(page) == f"01 / 0{COUNT}")
    res.check("first slide visible", await current_slide(page) == 0)

    await nxt.click()
    await settle(page)
    res.check("next moves to slide 2", await current_slide(page) == 1)
    res.check("counter reads 02 / 04", await counter_text(page) == f"02 / 0{COUNT}")
    res.check(
        "live region announces the active project",
        SECOND in await live_text(page),
        await live_text(page),
    )

    await prev.click()
    await settle(page)
    res.check("prev returns to slide 1", await current_slide(page) == 0)
    res.check("counter back to 01 / 04", await counter_text(page) == f"01 / 0{COUNT}")

    # Wraparound backwards: first -> last.
    await prev.click()
    await settle(page)
    res.check("prev wraps to the last slide", await current_slide(page) == COUNT - 1)
    res.check("counter wraps to 04 / 04", await counter_text(page) == f"0{COUNT} / 0{COUNT}")
    res.check("live region announces last project", LAST in await live_text(page))

    # Wraparound forwards: last -> first.
    await nxt.click()
    await settle(page)
    res.check("next wraps to the first slide", await current_slide(page) == 0)
    res.check("counter wraps to 01 / 04", await counter_text(page) == f"01 / 0{COUNT}")
    res.check("live region announces first project", FIRST in await live_text(page))
    await page.close()


async def aria_case(context, base_url: str, res: Results) -> None:
    page = await open_page(context, base_url)
    track = page.locator("#featured-work-track")
    res.check(
        "track is labelled as a carousel",
        await track.get_attribute("aria-roledescription") == "carousel"
        and bool(await track.get_attribute("aria-label")),
    )
    slides = page.locator("#featured-work-track > article")
    res.check("all slides present", await slides.count() == COUNT)
    labels = []
    for i in range(await slides.count()):
        s = slides.nth(i)
        labels.append(await s.get_attribute("aria-label"))
        if await s.get_attribute("aria-roledescription") != "slide":
            res.check(f"slide {i + 1} has slide roledescription", False)
    res.check(
        "slides announce position and name",
        labels[0] == f"1 of {COUNT}: {FIRST}" and labels[-1] == f"{COUNT} of {COUNT}: {LAST}",
        str(labels[0]),
    )

    nxt = page.get_by_test_id("carousel-next")
    prev = page.get_by_test_id("carousel-prev")
    res.check(
        "arrows name their target project",
        (await nxt.get_attribute("aria-label") or "").endswith(SECOND)
        and (await prev.get_attribute("aria-label") or "").endswith(LAST),
    )
    res.check(
        "arrows control the track",
        await nxt.get_attribute("aria-controls") == "featured-work-track"
        and await prev.get_attribute("aria-controls") == "featured-work-track",
    )
    live = page.locator("#work [role=status]")
    res.check(
        "counter has a polite atomic live region",
        await live.get_attribute("aria-live") == "polite"
        and await live.get_attribute("aria-atomic") == "true",
    )
    res.check(
        "decorative counter hidden from screen readers",
        await page.get_by_test_id("carousel-counter").get_attribute("aria-hidden") == "true",
    )
    await page.close()


async def keyboard_case(context, base_url: str, res: Results) -> None:
    page = await open_page(context, base_url)
    # Focus lands inside the track, then arrow keys step the carousel.
    await page.locator("#featured-work-track article:first-child button").focus()
    await page.keyboard.press("ArrowRight")
    await settle(page)
    res.check("ArrowRight advances the carousel", await current_slide(page) == 1)
    res.check("counter updates on keyboard nav", await counter_text(page) == f"02 / 0{COUNT}")
    await page.keyboard.press("ArrowLeft")
    await settle(page)
    res.check("ArrowLeft steps back", await current_slide(page) == 0)

    # Focus moves logically to the arrow controls.
    await page.get_by_test_id("carousel-prev").focus()
    await page.keyboard.press("Tab")
    focused = await page.evaluate("() => document.activeElement?.dataset?.testid ?? ''")
    res.check("tab order goes prev -> next", focused == "carousel-next", focused)
    await page.keyboard.press("Enter")
    await settle(page)
    res.check("Enter on next arrow advances", await current_slide(page) == 1)
    res.check(
        "focus stays on the next arrow",
        await page.evaluate("() => document.activeElement?.dataset?.testid ?? ''")
        == "carousel-next",
    )
    await page.close()


async def reduced_motion_case(browser, base_url: str, res: Results) -> None:
    context = await browser.new_context(viewport=MOBILE, reduced_motion="reduce")
    page = await open_page(context, base_url)
    track = page.locator("#featured-work-track")
    try:
        await page.wait_for_selector(
            '#featured-work-track[data-reduced-motion="true"]', timeout=5000
        )
        flagged = True
    except Exception:
        flagged = False
    res.check("track flags reduced motion", flagged)
    res.check(
        "scroll behaviour is instant",
        await track.evaluate("(el) => getComputedStyle(el).scrollBehavior") == "auto",
    )
    thumb = page.locator("#featured-work-track article:first-child img").first
    transition = await thumb.evaluate("(el) => getComputedStyle(el).transitionDuration")
    res.check(
        "thumbnail transitions disabled",
        all(float(v.strip().rstrip("s")) <= 0.001 for v in transition.split(",")),
        transition,
    )
    await page.get_by_test_id("carousel-next").click()
    await page.wait_for_timeout(150)
    res.check("instant jump to slide 2", await current_slide(page) == 1)
    await context.close()


async def swipe(page, dx: int) -> None:
    """Synthesised horizontal touch swipe across the carousel track."""
    box = await page.locator("#featured-work-track").bounding_box()
    cx = box["x"] + box["width"] / 2
    cy = box["y"] + box["height"] / 2
    await page.evaluate(
        """([cx, cy, dx]) => {
          const el = document.getElementById('featured-work-track');
          const t = (x) => new Touch({ identifier: 1, target: el, clientX: x, clientY: cy });
          const fire = (type, x) => el.dispatchEvent(new TouchEvent(type, {
            bubbles: true, cancelable: true,
            touches: type === 'touchend' ? [] : [t(x)],
            changedTouches: [t(x)],
          }));
          fire('touchstart', cx);
          fire('touchmove', cx + dx / 2);
          fire('touchend', cx + dx);
        }""",
        [cx, cy, dx],
    )


async def swipe_case(context, base_url: str, res: Results) -> None:
    page = await open_page(context, base_url)
    await swipe(page, -160)
    await settle(page)
    res.check("swipe left advances a slide", await current_slide(page) == 1)
    res.check("counter follows the swipe", await counter_text(page) == f"02 / 0{COUNT}")
    await swipe(page, 160)
    await settle(page)
    res.check("swipe right goes back", await current_slide(page) == 0)
    await swipe(page, 160)
    await settle(page)
    res.check("swipe right wraps to the last slide", await current_slide(page) == COUNT - 1)
    await swipe(page, -20)
    await settle(page)
    res.check("short flick is ignored", await current_slide(page) == COUNT - 1)
    # Arrows still work after swiping.
    await page.get_by_test_id("carousel-next").click()
    await settle(page)
    res.check("arrows still work after a swipe", await current_slide(page) == 0)
    await page.close()


async def focus_case(context, base_url: str, res: Results) -> None:
    """Tab order and focus styling survive wraparound and slide changes."""
    page = await open_page(context, base_url)
    prev = page.get_by_test_id("carousel-prev")
    nxt = page.get_by_test_id("carousel-next")

    await prev.focus()
    await page.keyboard.press("Enter")  # wrap backwards to the last slide
    await settle(page)
    res.check("wraparound via keyboard", await current_slide(page) == COUNT - 1)
    res.check(
        "focus remains on prev after wraparound",
        await page.evaluate("() => document.activeElement?.dataset?.testid ?? ''")
        == "carousel-prev",
    )
    res.check("both arrows stay enabled after wraparound", not await prev.is_disabled() and not await nxt.is_disabled())
    outline = await prev.evaluate(
        "(el) => { const s = getComputedStyle(el); return s.outlineStyle + ' ' + s.outlineWidth; }"
    )
    res.check("focused arrow has a visible focus ring", "none" not in outline, outline)

    await page.keyboard.press("Tab")
    res.check(
        "tab from prev reaches next after wraparound",
        await page.evaluate("() => document.activeElement?.dataset?.testid ?? ''")
        == "carousel-next",
    )
    await page.keyboard.press("Tab")
    res.check(
        "counter is not a tab stop",
        await page.evaluate("() => document.activeElement?.dataset?.testid ?? ''")
        != "carousel-counter",
    )
    await nxt.focus()
    await page.keyboard.press("Enter")
    await settle(page)
    res.check(
        "focus survives a slide change",
        await page.evaluate("() => document.activeElement?.dataset?.testid ?? ''")
        == "carousel-next",
    )
    await page.close()


async def rtl_case(context, base_url: str, res: Results) -> None:
    """dir="rtl": arrows stay logical, swipe/key direction mirrors, counter tracks."""
    page = await open_page(context, base_url)
    await page.evaluate("() => document.documentElement.setAttribute('dir', 'rtl')")
    await settle(page)
    res.check(
        "track computes as rtl",
        await page.locator("#featured-work-track").evaluate(
            "(el) => getComputedStyle(el).direction"
        )
        == "rtl",
    )
    res.check("rtl starts on slide 1", await current_slide(page) == 0)
    res.check("rtl counter starts at 01 / 04", await counter_text(page) == f"01 / 0{COUNT}")

    # Logical arrows are unchanged: "next" always advances the project order.
    await page.get_by_test_id("carousel-next").click()
    await settle(page)
    res.check("rtl next advances to slide 2", await current_slide(page) == 1)
    res.check("rtl counter reads 02 / 04", await counter_text(page) == f"02 / 0{COUNT}")
    res.check("rtl live region announces project 2", SECOND in await live_text(page))
    await page.get_by_test_id("carousel-prev").click()
    await settle(page)
    res.check("rtl prev returns to slide 1", await current_slide(page) == 0)
    await page.get_by_test_id("carousel-prev").click()
    await settle(page)
    res.check("rtl prev wraps to the last slide", await current_slide(page) == COUNT - 1)
    await page.get_by_test_id("carousel-next").click()
    await settle(page)
    res.check("rtl next wraps to the first slide", await current_slide(page) == 0)

    # Physical directions mirror: swiping right moves forward in RTL.
    await swipe(page, 160)
    await settle(page)
    res.check("rtl swipe right advances a slide", await current_slide(page) == 1)
    res.check("rtl counter follows the swipe", await counter_text(page) == f"02 / 0{COUNT}")
    await swipe(page, -160)
    await settle(page)
    res.check("rtl swipe left goes back", await current_slide(page) == 0)
    await swipe(page, 20)
    await settle(page)
    res.check("rtl short flick is ignored", await current_slide(page) == 0)

    await page.locator("#featured-work-track article:first-child button").focus()
    await page.keyboard.press("ArrowLeft")
    await settle(page)
    res.check("rtl ArrowLeft advances the carousel", await current_slide(page) == 1)
    await page.keyboard.press("ArrowRight")
    await settle(page)
    res.check("rtl ArrowRight steps back", await current_slide(page) == 0)
    await page.evaluate("() => document.documentElement.setAttribute('dir', 'ltr')")
    await page.close()


async def repeated_swipe_case(context, base_url: str, res: Results) -> None:
    """Tab order, focus styling and the counter survive many consecutive swipes."""
    page = await open_page(context, base_url)
    sequence = [-160, -160, 160, -160, 160, 160, -160]
    expected = 0
    for i, dx in enumerate(sequence, start=1):
        await swipe(page, dx)
        await settle(page)
        expected = (expected + (1 if dx < 0 else -1)) % COUNT
        res.check(
            f"swipe {i} lands on slide {expected + 1}",
            await current_slide(page) == expected,
        )
        res.check(
            f"counter after swipe {i}",
            await counter_text(page) == f"0{expected + 1} / 0{COUNT}",
        )
    res.check(
        "live region matches the final project",
        (await live_text(page)).endswith(
            (await page.locator("#featured-work-track > article").nth(expected).get_attribute(
                "aria-label"
            )).split(": ", 1)[1]
        ),
        await live_text(page),
    )

    prev = page.get_by_test_id("carousel-prev")
    await prev.focus()
    outline = await prev.evaluate(
        "(el) => { const s = getComputedStyle(el); return s.outlineStyle + ' ' + s.outlineWidth; }"
    )
    res.check("focus ring still visible after swipes", "none" not in outline, outline)
    await page.keyboard.press("Tab")
    res.check(
        "tab order stays prev -> next after swipes",
        await page.evaluate("() => document.activeElement?.dataset?.testid ?? ''")
        == "carousel-next",
    )
    await page.keyboard.press("Enter")
    await settle(page)
    expected = (expected + 1) % COUNT
    res.check("arrows still step after swipes", await current_slide(page) == expected)
    res.check(
        "counter still correct after arrow use",
        await counter_text(page) == f"0{expected + 1} / 0{COUNT}",
    )
    res.check(
        "focus stays on next arrow after swipes",
        await page.evaluate("() => document.activeElement?.dataset?.testid ?? ''")
        == "carousel-next",
    )
    await page.close()


async def compare_snapshot(page, res: Results, name: str, label: str, update: bool) -> None:
    from PIL import Image, ImageChops

    shots = ROOT / "screenshots"
    diffs = ROOT / "diffs"
    baselines = ROOT / "baselines"
    for d in (shots, diffs, baselines):
        d.mkdir(parents=True, exist_ok=True)

    await page.evaluate("() => document.fonts.ready")
    await page.wait_for_timeout(400)
    current = shots / f"{name}.png"
    await page.locator("#work").screenshot(path=str(current))
    baseline = baselines / f"{name}.png"

    if update or not baseline.exists():
        baseline.write_bytes(current.read_bytes())
        res.check(f"{label} baseline recorded", True, str(baseline))
        return
    a = Image.open(baseline).convert("RGB")
    b = Image.open(current).convert("RGB")
    if a.size != b.size:
        res.check(f"{label} snapshot matches baseline", False, f"{a.size} vs {b.size}")
        return
    diff = ImageChops.difference(a, b)
    changed = sum(1 for px in diff.getdata() if px != (0, 0, 0))
    ratio = changed / (a.size[0] * a.size[1])
    if ratio > 0.002:
        diff.save(diffs / f"{name}.png")
    res.check(f"{label} snapshot matches baseline", ratio <= 0.002, f"{ratio:.4%} differs")


async def snapshot_case(browser, base_url: str, res: Results, update: bool) -> None:
    """Visual regression: reduced-motion carousel must render identically."""
    context = await browser.new_context(viewport=MOBILE, reduced_motion="reduce")
    page = await open_page(context, base_url)
    await page.wait_for_selector('#featured-work-track[data-reduced-motion="true"]', timeout=5000)
    await compare_snapshot(
        page, res, "featured-work-carousel-reduced-motion", "reduced-motion", update
    )
    await context.close()


async def default_motion_snapshot_case(browser, base_url: str, res: Results, update: bool) -> None:
    """Visual regression for the default (animated) carousel state."""
    context = await browser.new_context(viewport=MOBILE, reduced_motion="no-preference")
    page = await open_page(context, base_url)
    await page.wait_for_selector('#featured-work-track[data-reduced-motion="false"]', timeout=5000)
    thumb = page.locator("#featured-work-track article:first-child img").first
    transition = await thumb.evaluate("(el) => getComputedStyle(el).transitionDuration")
    res.check(
        "default mode keeps thumbnail transitions enabled",
        any(float(v.strip().rstrip("s")) > 0.001 for v in transition.split(",")),
        transition,
    )
    await compare_snapshot(page, res, "featured-work-carousel-default", "default-motion", update)
    await context.close()



async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://localhost:3000")
    parser.add_argument("--report", default="")
    parser.add_argument(
        "--update-baseline",
        action="store_true",
        help="re-record the carousel snapshot baselines",
    )
    args = parser.parse_args()

    res = Results()
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport=MOBILE, has_touch=True)
        await navigation_case(context, args.base_url, res)
        await aria_case(context, args.base_url, res)
        await keyboard_case(context, args.base_url, res)
        await swipe_case(context, args.base_url, res)
        await focus_case(context, args.base_url, res)
        await repeated_swipe_case(context, args.base_url, res)
        await rtl_case(context, args.base_url, res)
        await context.close()
        await reduced_motion_case(browser, args.base_url, res)
        await snapshot_case(browser, args.base_url, res, args.update_baseline)
        await default_motion_snapshot_case(browser, args.base_url, res, args.update_baseline)

        await browser.close()

    total, failed = len(res.rows), len(res.failed)
    print(f"\n{total - failed}/{total} checks passed")
    if args.report:
        Path(args.report).write_text(
            json.dumps({"checks": res.rows, "failed": failed, "total": total}, indent=2)
        )
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
