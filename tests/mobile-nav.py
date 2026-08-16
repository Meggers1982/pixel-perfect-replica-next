#!/usr/bin/env python3
"""End-to-end checks for the mobile header navigation.

Covers:
  1. body scroll-lock restoration across viewport resizes, including
     iOS-style address-bar height changes (width unchanged, height shrinks)
     and a rotation / resize past the desktop breakpoint;
  2. navigating to a different page (client-side history navigation) while the
     menu is open closes the menu, returns focus to the hamburger button and
     restores body scroll;
  3. the active nav item exposes aria-current and a screen-reader hint that
     announces the current section inside the mobile menu;
  4. an axe-core accessibility scan of the mobile navigation (closed + open).

Usage:
  python3 tests/mobile-nav.py
  python3 tests/mobile-nav.py --base-url http://localhost:3000
  python3 tests/mobile-nav.py --report tests/report-mobile-nav.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parent
MOBILE = {"width": 390, "height": 844}
AXE_CDN = "https://cdn.jsdelivr.net/npm/axe-core@4.10.2/axe.min.js"
# Generous default: a busy dev server can take tens of seconds for the first
# hydration of a route. Override with --timeout for slower CI machines.
TIMEOUT = 45_000
OPEN_ATTEMPTS = 4

# Only these rules matter for the nav audit; keep the scan scoped to <header>.
AXE_TAGS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "best-practice"]


class Results:
    def __init__(self) -> None:
        self.rows: list[dict] = []
        self.silence = False  # suppress logging for retryable attempts

    def check(self, name: str, ok: bool, detail: str = "") -> None:
        self.rows.append({"name": name, "status": "pass" if ok else "fail", "detail": detail})
        if not self.silence:
            print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"  — {detail}" if detail else ""))

    @property
    def failed(self) -> list[dict]:
        return [r for r in self.rows if r["status"] != "pass"]


async def stabilize(page) -> None:
    await page.add_style_tag(
        content="*,*::before,*::after{animation:none!important;transition:none!important}"
    )
    await page.evaluate("document.fonts ? document.fonts.ready : null")
    # Wait for hydration rather than a fixed sleep: the toggle only reacts to
    # clicks once React has attached, which can take a while when the dev
    # server is busy compiling.
    await page.wait_for_function(
        """() => {
             const t = document.querySelector('[aria-controls="mobile-menu"]');
             return !!t && t.getAttribute('aria-expanded') === 'false';
           }""",
        timeout=TIMEOUT,
    )
    await page.wait_for_load_state("networkidle")


async def body_locked(page) -> bool:
    return await page.evaluate("getComputedStyle(document.body).overflow === 'hidden'")


def toggle(page):
    return page.locator('[aria-controls="mobile-menu"]')


async def open_menu(page) -> None:
    """Open the mobile menu deterministically.

    A single click can land before hydration wires the handler, in which case
    the old fixed wait_for_selector just burned its whole timeout. Instead the
    click is retried until the toggle reports aria-expanded=true and the menu
    panel is actually visible.
    """
    if await page.locator("#mobile-menu").count():
        return
    btn = toggle(page)
    await btn.wait_for(state="visible", timeout=TIMEOUT)
    last: Exception | None = None
    for attempt in range(OPEN_ATTEMPTS):
        try:
            await btn.click(timeout=TIMEOUT // OPEN_ATTEMPTS)
            await page.wait_for_selector(
                "#mobile-menu", state="visible", timeout=TIMEOUT // OPEN_ATTEMPTS
            )
            await page.wait_for_function(
                """() => document.querySelector('[aria-controls="mobile-menu"]')
                          ?.getAttribute('aria-expanded') === 'true'""",
                timeout=TIMEOUT // OPEN_ATTEMPTS,
            )
            return
        except Exception as exc:  # dev server still compiling / not hydrated yet
            last = exc
            await page.wait_for_timeout(250 * (attempt + 1))
    raise AssertionError(f"mobile menu did not open after {OPEN_ATTEMPTS} attempts: {last}")


async def wait_for_server(base_url: str, timeout_s: float = 90.0) -> None:
    """Block until the dev server answers, so a cold/compiling server is not a failure."""
    import urllib.error
    import urllib.request

    deadline = asyncio.get_event_loop().time() + timeout_s
    while asyncio.get_event_loop().time() < deadline:
        try:
            with urllib.request.urlopen(base_url, timeout=5) as r:
                if r.status < 500:
                    return
        except (urllib.error.URLError, OSError):
            pass
        await asyncio.sleep(1)
    raise SystemExit(f"dev server at {base_url} never became ready")


async def new_mobile_page(context, base_url: str):
    page = await context.new_page()
    page.set_default_timeout(TIMEOUT)
    page.set_default_navigation_timeout(TIMEOUT)
    await page.set_viewport_size(MOBILE)
    last: Exception | None = None
    for attempt in range(3):
        try:
            await page.goto(base_url, wait_until="domcontentloaded", timeout=TIMEOUT)
            await stabilize(page)
            return page
        except Exception as exc:  # first hit can time out while Vite compiles
            last = exc
            await page.wait_for_timeout(1000 * (attempt + 1))
    raise AssertionError(f"could not load {base_url}: {last}")


async def resize_case(context, base_url: str, res: Results) -> None:
    """Scroll lock survives address-bar resizes and is restored on breakpoint exit."""
    page = await new_mobile_page(context, base_url)
    await open_menu(page)
    res.check("resize: scroll locked while menu open", await body_locked(page))

    # iOS address bar collapsing: same width, taller viewport.
    await page.set_viewport_size({"width": 390, "height": 900})
    await page.wait_for_timeout(120)
    menu_still_open = await page.locator("#mobile-menu").count() == 1
    res.check(
        "resize: iOS address-bar growth keeps menu open and locked",
        menu_still_open and await body_locked(page),
    )

    # iOS address bar reappearing: same width, shorter viewport.
    await page.set_viewport_size({"width": 390, "height": 780})
    await page.wait_for_timeout(120)
    res.check(
        "resize: iOS address-bar shrink keeps menu open and locked",
        await page.locator("#mobile-menu").count() == 1 and await body_locked(page),
    )

    # Rotation / resize past the desktop breakpoint closes the menu.
    await page.set_viewport_size({"width": 1024, "height": 768})
    await page.wait_for_timeout(200)
    closed = await page.locator("#mobile-menu").count() == 0
    restored = not await body_locked(page)
    res.check("resize: crossing md breakpoint closes menu", closed)
    res.check("resize: body scroll restored after breakpoint resize", restored)

    # Page behind must actually scroll again.
    await page.evaluate("window.scrollTo(0, 400)")
    await page.wait_for_timeout(120)
    scrolled = await page.evaluate("window.scrollY")
    res.check("resize: page scrolls after restore", scrolled > 0, f"scrollY={scrolled}")
    await page.close()


async def navigation_case(context, base_url: str, res: Results) -> None:
    """Navigating away with the menu open closes it, restores focus and scroll."""
    page = await new_mobile_page(context, base_url)
    await open_menu(page)
    res.check("navigation: scroll locked while menu open", await body_locked(page))

    # Client-side navigation to a different URL, then a history navigation back
    # (the same signal an in-app route change emits).
    await page.evaluate("history.pushState({}, '', '/?page=other')")
    await page.go_back()
    await page.wait_for_timeout(250)

    res.check("navigation: menu closed", await page.locator("#mobile-menu").count() == 0)
    res.check("navigation: body scroll restored", not await body_locked(page))

    focused = await page.evaluate(
        "document.activeElement && document.activeElement.getAttribute('aria-label')"
    )
    res.check(
        "navigation: focus returned to hamburger button",
        focused == "Open menu",
        f"activeElement aria-label={focused!r}",
    )
    expanded = await toggle(page).get_attribute("aria-expanded")
    res.check("navigation: toggle reports aria-expanded=false", expanded == "false")
    await page.close()


async def aria_current_case(context, base_url: str, res: Results) -> None:
    """Active section is marked aria-current and announced in the mobile menu."""
    page = await new_mobile_page(context, base_url)

    for section in ("work", "contact"):
        await page.evaluate(
            "(id) => document.getElementById(id)?.scrollIntoView({ block: 'center' })", section
        )
        # Wait for the scroll-spy observer to settle on this section instead
        # of guessing with a fixed sleep.
        try:
            await page.wait_for_function(
                """(id) => {
                     const links = document.querySelectorAll('header a[href^="#"]');
                     const active = [...links].filter(
                       (a) => a.getAttribute('aria-current') === 'true'
                     );
                     return active.length === 1 && active[0].getAttribute('href') === '#' + id;
                   }""",
                arg=section,
                timeout=TIMEOUT,
            )
        except Exception:
            pass  # let the assertion below report the actual state
        await open_menu(page)

        current = page.locator('#mobile-menu a[aria-current="true"]')
        count = await current.count()
        res.check(f"aria-current: exactly one active item for #{section}", count == 1, f"count={count}")

        if count == 1:
            href = await current.first.get_attribute("href")
            res.check(
                f"aria-current: points at #{section}",
                href == f"#{section}",
                f"href={href!r}",
            )
            sr_text = await current.first.inner_text()
            has_hint = await current.first.locator(".sr-only").count() == 1
            res.check(
                f"aria-current: screen-reader hint announced for #{section}",
                has_hint and "current section" in sr_text.lower(),
                f"text={sr_text!r}",
            )

        await page.keyboard.press("Escape")
        await page.wait_for_timeout(150)

    await page.close()


async def axe_case(context, base_url: str, res: Results, report_dir: Path) -> None:
    """axe-core scan of the header nav, both closed and open."""
    page = await new_mobile_page(context, base_url)
    violations_out: dict[str, list] = {}

    async def scan(state: str) -> None:
        try:
            await page.add_script_tag(url=AXE_CDN)
        except Exception as exc:  # offline CI runners
            res.check(f"axe ({state}): axe-core loaded", False, str(exc))
            return
        result = await page.evaluate(
            """async (tags) => await axe.run('header', {
                 runOnly: { type: 'tag', values: tags },
                 resultTypes: ['violations'],
               })""",
            AXE_TAGS,
        )
        violations = [
            {
                "id": v["id"],
                "impact": v.get("impact"),
                "help": v["help"],
                "nodes": [n["target"] for n in v["nodes"]],
            }
            for v in result["violations"]
        ]
        violations_out[state] = violations
        detail = ", ".join(f"{v['id']}({v['impact']})" for v in violations) or "no violations"
        res.check(f"axe ({state}): mobile navigation has no violations", not violations, detail)

    await scan("menu closed")
    await open_menu(page)
    await scan("menu open")

    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / "mobile-nav-axe.json").write_text(json.dumps(violations_out, indent=2))
    await page.close()


async def run_case(name: str, factory, res: Results, retries: int) -> dict:
    """Run one case, retrying transient failures; only the last attempt is kept."""
    attempts = 0
    mark = len(res.rows)
    error = ""
    for attempt in range(retries + 1):
        attempts = attempt + 1
        del res.rows[mark:]  # discard the failed attempt's rows
        res.silence = True
        try:
            await factory()
            error = ""
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
        res.silence = False
        case_failed = error or [r for r in res.rows[mark:] if r["status"] != "pass"]
        if not case_failed:
            break
        if attempt < retries:
            print(f"RETRY {name} (attempt {attempt + 1} failed){' — ' + error if error else ''}")
            await asyncio.sleep(1.5 * (attempt + 1))
    if error:
        res.silence = True
        res.check(f"{name}: case completed", False, error)
        res.silence = False
    for row in res.rows[mark:]:
        row["case"] = name
        print(
            f"{row['status'].upper()}  {row['name']}"
            + (f"  — {row['detail']}" if row["detail"] else "")
        )

    failed = [r for r in res.rows[mark:] if r["status"] != "pass"]
    return {
        "case": name,
        "attempts": attempts,
        "passed": not failed,
        "flaky": attempts > 1 and not failed,
        "failures": [r["name"] for r in failed],
    }


def write_flake_history(path: Path, run: dict, keep: int = 50) -> dict:
    """Append this run to a rolling history and return aggregate flake stats."""
    history: list[dict] = []
    if path.exists():
        try:
            history = json.loads(path.read_text()).get("runs", [])
        except (ValueError, OSError):
            history = []
    history.append(run)
    history = history[-keep:]

    per_case: dict[str, dict] = {}
    for entry in history:
        for case in entry["cases"]:
            stat = per_case.setdefault(case["case"], {"runs": 0, "flaky": 0, "failed": 0})
            stat["runs"] += 1
            stat["flaky"] += 1 if case["flaky"] else 0
            stat["failed"] += 0 if case["passed"] else 1
    for stat in per_case.values():
        stat["flakeRate"] = round((stat["flaky"] + stat["failed"]) / stat["runs"], 3)

    stats = {"runsTracked": len(history), "perCase": per_case}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"runs": history, "stats": stats}, indent=2))
    return stats


async def main() -> int:  # noqa: PLR0915
    global TIMEOUT
    parser = argparse.ArgumentParser(
        description="Mobile navigation behaviour + accessibility checks.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python3 tests/mobile-nav.py\n"
            "  python3 tests/mobile-nav.py --only resize,navigation\n"
            "  python3 tests/mobile-nav.py --retries 2 --quarantine axe\n"
            "  python3 tests/mobile-nav.py --report tests/report-mobile-nav.json\n"
        ),
    )
    parser.add_argument("--base-url", default="http://localhost:3000")
    parser.add_argument(
        "--timeout",
        type=int,
        default=TIMEOUT,
        help="Per-action timeout in ms (raise on slow/loaded CI machines).",
    )
    parser.add_argument("--report", default=str(ROOT / "report-mobile-nav.json"))
    parser.add_argument("--report-dir", default=str(ROOT / "report"))
    parser.add_argument(
        "--only",
        default="",
        help="Comma-separated subset of: resize,navigation,aria-current,axe",
    )
    parser.add_argument(
        "--retries",
        type=int,
        default=2,
        help="Retries per case before it is reported as a real failure (default 2).",
    )
    parser.add_argument(
        "--quarantine",
        default="",
        help="Comma-separated cases reported but never blocking (known flaky).",
    )
    parser.add_argument(
        "--flake-history",
        default=str(ROOT / "report" / "mobile-nav-flake-history.json"),
        help="Rolling per-case flake-rate history file.",
    )
    args = parser.parse_args()

    TIMEOUT = args.timeout

    selected = {s.strip() for s in args.only.split(",") if s.strip()}
    quarantined = {s.strip() for s in args.quarantine.split(",") if s.strip()}
    res = Results()
    await wait_for_server(args.base_url)

    summaries: list[dict] = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport=MOBILE, has_touch=True, is_mobile=True)

        # Lazy factories: an aborted run never leaves un-awaited coroutines.
        cases = [
            ("resize", lambda: resize_case(context, args.base_url, res)),
            ("navigation", lambda: navigation_case(context, args.base_url, res)),
            ("aria-current", lambda: aria_current_case(context, args.base_url, res)),
            ("axe", lambda: axe_case(context, args.base_url, res, Path(args.report_dir))),
        ]
        for name, factory in cases:
            if selected and name not in selected:
                continue
            summary = await run_case(name, factory, res, max(0, args.retries))
            summary["quarantined"] = name in quarantined
            summary["blocking"] = not summary["passed"] and not summary["quarantined"]
            summaries.append(summary)

        await browser.close()

    run_entry = {"cases": summaries}
    stats = write_flake_history(Path(args.flake_history), run_entry)

    flaky = [s for s in summaries if s["flaky"]]
    blocking = [s for s in summaries if s["blocking"]]
    quarantined_failed = [s for s in summaries if s["quarantined"] and not s["passed"]]
    total_attempts = sum(s["attempts"] for s in summaries)
    flake_rate = round(len(flaky) / len(summaries), 3) if summaries else 0.0

    Path(args.report).write_text(
        json.dumps(
            {
                "suite": "mobile-nav",
                "results": res.rows,
                "cases": summaries,
                "retries": args.retries,
                "quarantined": sorted(quarantined),
                "flakeRate": flake_rate,
                "totalAttempts": total_attempts,
                "history": stats,
            },
            indent=2,
        )
    )

    print(f"\n{len(res.rows) - len(res.failed)}/{len(res.rows)} checks passed")
    print(
        f"cases: {len(summaries)} · attempts: {total_attempts} · "
        f"flake rate this run: {flake_rate * 100:.0f}%"
    )
    for s in flaky:
        print(f"  ⚠️  {s['case']} recovered on attempt {s['attempts']}")
    for s in quarantined_failed:
        print(f"  🟣 {s['case']} failed but is quarantined (non-blocking)")
    for case, stat in sorted(stats["perCase"].items()):
        print(
            f"  history {case}: {stat['flakeRate'] * 100:.0f}% flaky/failed "
            f"over {stat['runs']} run(s)"
        )
    return 1 if blocking else 0



if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
