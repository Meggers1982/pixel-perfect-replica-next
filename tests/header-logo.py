#!/usr/bin/env python3
"""Header word mark checks for "Brand Ledger".

Covers three things:
  1. accessibility — the logo link exposes the accessible name "Brand Ledger",
     is keyboard reachable, shows a visible focus indicator, and passes an
     axe-core scan (colour-contrast included) scoped to the <header>;
  2. layout — after a series of window resizes the word mark never overlaps
     the desktop nav items or the hamburger toggle, stays on one line, and
     keeps its left edge aligned with the header container padding;
  3. visual regression — pixel snapshots of the word mark at mobile and
     desktop breakpoints, diffed against tests/baselines/.

Usage:
  python3 tests/header-logo.py
  python3 tests/header-logo.py --only a11y,layout
  python3 tests/header-logo.py --update-baseline
  python3 tests/header-logo.py --report tests/report-header-logo.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

from PIL import Image, ImageChops
from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parent
BASELINES = ROOT / "baselines"
SHOTS = ROOT / "screenshots" / "header-logo"
DIFFS = ROOT / "diffs"
AXE_CDN = "https://cdn.jsdelivr.net/npm/axe-core@4.10.2/axe.min.js"
AXE_TAGS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]

LOGO = 'header a.logo-mark'
TOGGLE = '[aria-controls="mobile-menu"]'

# name -> viewport. Mobile/desktop pairs used for snapshots; the wider set is
# used for the resize/overlap sweep.
SNAPSHOT_VIEWPORTS = {
    "mobile": {"width": 375, "height": 812},
    "desktop": {"width": 1280, "height": 900},
}
RESIZE_SWEEP = [
    {"width": 320, "height": 720},
    {"width": 375, "height": 812},
    {"width": 414, "height": 896},
    {"width": 768, "height": 1024},
    {"width": 900, "height": 900},
    {"width": 1024, "height": 900},
    {"width": 1280, "height": 900},
    {"width": 1600, "height": 1000},
    {"width": 1920, "height": 1080},
    # Bounce back down to catch state that only breaks after shrinking again.
    {"width": 375, "height": 812},
    {"width": 1440, "height": 900},
]


# Snapshots are recorded at 1x and at retina density so the larger word mark is
# verified at the pixel grid real high-DPI displays use.
SNAPSHOT_SCALES = [1, 2]

# Browser-level zoom factors. The word mark must stay on one line and keep its
# container alignment when the user zooms.
ZOOM_LEVELS = [1.25, 1.5]

# WCAG 2.1 AA (2.5.5 / 2.5.8) — 24px is the AA floor, 44px the comfortable
# mobile target we hold ourselves to.
MIN_TAP_TARGET = 44.0
MIN_TAP_TARGET_DESKTOP = 24.0

MAX_DIFF_RATIO = 0.01
PIXEL_THRESHOLD = 12


MEASURE_JS = """
() => {
  const logo = document.querySelector('header a.logo-mark');
  const header = document.querySelector('header');
  if (!logo || !header) return { error: 'header or logo missing' };
  const container = logo.parentElement;
  const cs = getComputedStyle(container);
  const lcs = getComputedStyle(logo);
  const lr = logo.getBoundingClientRect();
  const neighbours = [];
  const nav = header.querySelector('nav[aria-label="Desktop"]');
  if (nav) {
    for (const a of nav.querySelectorAll('a')) {
      const r = a.getBoundingClientRect();
      if (r.width > 0 && r.height > 0) {
        neighbours.push({ label: a.textContent.trim(), ...r.toJSON() });
      }
    }
  }
  const toggle = header.querySelector('[aria-controls="mobile-menu"]');
  if (toggle) {
    const r = toggle.getBoundingClientRect();
    if (r.width > 0 && r.height > 0) {
      neighbours.push({ label: 'menu-toggle', ...r.toJSON() });
    }
  }
  // A single-line word mark is ~1 line-box tall; two stacked words double it.
  const fontSize = parseFloat(lcs.fontSize);
  // Count rendered text lines via a Range so a padded (tap-target sized) link
  // box is not mistaken for wrapped text.
  const range = document.createRange();
  range.selectNodeContents(logo);
  const rects = [...range.getClientRects()].filter((r) => r.width > 0 && r.height > 0);
  // Group rects into vertical bands: rects that overlap vertically belong to
  // the same rendered line, so nested spans don't count as extra lines.
  const bands = [];
  for (const r of rects.sort((a, b) => a.top - b.top)) {
    const band = bands.find((b) => Math.min(b.bottom, r.bottom) - Math.max(b.top, r.top) > 1);
    if (band) {
      band.top = Math.min(band.top, r.top);
      band.bottom = Math.max(band.bottom, r.bottom);
    } else {
      bands.push({ top: r.top, bottom: r.bottom });
    }
  }
  const lineCount = Math.max(1, bands.length);
  return {
    logo: lr.toJSON(),
    text: logo.textContent.replace(/\\s+/g, ' ').trim(),
    fontSize,
    lineCount,
    whiteSpace: lcs.whiteSpace,
    containerPaddingLeft: parseFloat(cs.paddingLeft),
    containerLeft: container.getBoundingClientRect().left,
    headerHeight: header.getBoundingClientRect().height,
    neighbours,
  };
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


async def stabilize(page) -> None:
    await page.add_style_tag(
        content="*,*::before,*::after{animation:none!important;transition:none!important}"
    )
    await page.evaluate("document.fonts ? document.fonts.ready : null")
    await page.wait_for_selector(LOGO)
    await page.wait_for_function(f"() => document.querySelector('{TOGGLE}') !== null")
    await page.wait_for_timeout(500)


def overlap(a: dict, b: dict) -> float:
    """Horizontal+vertical intersection area between two DOMRect dicts."""
    x = max(0.0, min(a["right"], b["right"]) - max(a["left"], b["left"]))
    y = max(0.0, min(a["bottom"], b["bottom"]) - max(a["top"], b["top"]))
    return x * y


# ---------------------------------------------------------------- a11y case


async def a11y_case(context, url: str, results: Results) -> None:
    page = await context.new_page()
    await page.set_viewport_size(SNAPSHOT_VIEWPORTS["desktop"])
    await page.goto(url, wait_until="domcontentloaded")
    await stabilize(page)

    logo = page.locator(LOGO)
    name = (await logo.evaluate("el => el.getAttribute('aria-label') || el.innerText")).strip()
    normalized = " ".join(name.split())
    results.check(
        "logo accessible name starts with 'Brand Ledger'",
        normalized.lower().startswith("brand ledger"),
        f"got {normalized!r}",
    )


    role_info = await logo.evaluate(
        "el => ({ tag: el.tagName, href: el.getAttribute('href'), tabindex: el.getAttribute('tabindex') })"
    )
    results.check(
        "logo is a real link with an href",
        role_info["tag"] == "A" and bool(role_info["href"]),
        json.dumps(role_info),
    )
    results.check(
        "logo does not use a positive tabindex",
        role_info["tabindex"] in (None, "0"),
        f"tabindex={role_info['tabindex']}",
    )

    # Keyboard reachability: the word mark should be the first tab stop.
    await page.keyboard.press("Tab")
    focused_first = await page.evaluate(
        f"() => document.activeElement === document.querySelector('{LOGO}')"
    )
    if not focused_first:
        for _ in range(10):
            await page.keyboard.press("Tab")
            if await page.evaluate(
                f"() => document.activeElement === document.querySelector('{LOGO}')"
            ):
                focused_first = True
                break
    results.check("logo is reachable by keyboard (Tab)", focused_first)

    if focused_first:
        focus_style = await logo.evaluate(
            """el => {
              const cs = getComputedStyle(el);
              return {
                outlineStyle: cs.outlineStyle,
                outlineWidth: parseFloat(cs.outlineWidth) || 0,
                outlineColor: cs.outlineColor,
                boxShadow: cs.boxShadow,
              };
            }"""
        )
        visible = (
            focus_style["outlineStyle"] not in ("none", "")
            and focus_style["outlineWidth"] >= 1
        ) or (focus_style["boxShadow"] not in ("none", ""))
        results.check(
            "focused logo shows a visible focus indicator",
            visible,
            json.dumps(focus_style),
        )

    # axe-core scan scoped to the header (catches colour-contrast + link-name).
    await page.add_script_tag(url=AXE_CDN)
    axe = await page.evaluate(
        """async (tags) => {
          const r = await window.axe.run('header', { runOnly: { type: 'tag', values: tags } });
          return r.violations.map(v => ({
            id: v.id,
            impact: v.impact,
            nodes: v.nodes.map(n => n.target.join(' ')).slice(0, 5),
          }));
        }""",
        AXE_TAGS,
    )
    results.check(
        "header passes axe-core (WCAG 2.1 AA, contrast included)",
        not axe,
        json.dumps(axe) if axe else "",
    )

    contrast_only = [v for v in axe if v["id"] == "color-contrast"]
    results.check(
        "word mark meets WCAG AA colour contrast",
        not contrast_only,
        json.dumps(contrast_only) if contrast_only else "",
    )
    await page.close()


# -------------------------------------------------------------- layout case


async def layout_case(context, url: str, results: Results, browser_name: str = "chromium") -> list[dict]:
    page = await context.new_page()
    await page.set_viewport_size(RESIZE_SWEEP[0])
    await page.goto(url, wait_until="domcontentloaded")
    await stabilize(page)

    rows: list[dict] = []
    for vp in RESIZE_SWEEP:
        await page.set_viewport_size(vp)
        await page.wait_for_timeout(220)
        m = await page.evaluate(MEASURE_JS)
        if m.get("error"):
            results.check(f"[{browser_name}] layout {vp['width']}px measured", False, m["error"])
            continue

        worst = 0.0
        worst_label = ""
        for n in m["neighbours"]:
            area = overlap(m["logo"], n)
            if area > worst:
                worst, worst_label = area, n["label"]
        results.check(
            f"[{browser_name}] logo does not overlap nav/toggle at {vp['width']}px",
            worst == 0.0,
            f"overlaps {worst_label} by {worst:.0f}px²" if worst else "",
        )

        # Word mark must stay on one line: height under ~1.6x the font size.
        single_line = m["lineCount"] == 1
        results.check(
            f"[{browser_name}] word mark stays on one line at {vp['width']}px",
            single_line,
            f"lines={m['lineCount']} height={m['logo']['height']:.1f}px fontSize={m['fontSize']:.1f}px",
        )

        expected_left = m["containerLeft"] + m["containerPaddingLeft"]
        aligned = abs(m["logo"]["left"] - expected_left) <= 1.5
        results.check(
            f"[{browser_name}] word mark honours container padding at {vp['width']}px",
            aligned,
            f"left={m['logo']['left']:.1f}px expected={expected_left:.1f}px",
        )

        inside = m["logo"]["top"] >= -0.5 and m["logo"]["bottom"] <= m["headerHeight"] + 0.5
        results.check(
            f"[{browser_name}] word mark stays inside the header bar at {vp['width']}px",
            inside,
            f"logo {m['logo']['top']:.1f}–{m['logo']['bottom']:.1f} header={m['headerHeight']:.1f}",
        )

        rows.append(
            {
                "width": vp["width"],
                "logo": {k: round(m["logo"][k], 2) for k in ("left", "top", "right", "bottom", "width", "height")},
                "worstOverlap": round(worst, 2),
                "worstOverlapWith": worst_label,
                "singleLine": single_line,
                "text": m["text"],
            }
        )
    await page.close()
    return rows


# ------------------------------------------------------------ snapshot case


def compare(current: Path, baseline: Path, diff_path: Path) -> tuple[bool, float]:
    a = Image.open(current).convert("RGB")
    b = Image.open(baseline).convert("RGB")
    if a.size != b.size:
        return False, 1.0
    diff = ImageChops.difference(a, b).convert("L")
    mask = diff.point(lambda p: 255 if p > PIXEL_THRESHOLD else 0)
    changed = sum(1 for p in mask.getdata() if p)
    ratio = changed / (a.width * a.height)
    if ratio > 0:
        diff_path.parent.mkdir(parents=True, exist_ok=True)
        Image.merge("RGB", (mask, Image.new("L", a.size, 0), Image.new("L", a.size, 0))).save(diff_path)
    return ratio <= MAX_DIFF_RATIO, ratio


async def snapshot_case(
    browser, url: str, results: Results, update: bool, browser_name: str
) -> list[dict]:
    SHOTS.mkdir(parents=True, exist_ok=True)
    BASELINES.mkdir(parents=True, exist_ok=True)
    rows: list[dict] = []
    for name, vp in SNAPSHOT_VIEWPORTS.items():
        for scale in SNAPSHOT_SCALES:
            suffix = "" if scale == 1 else f"@{scale}x"
            key = f"{name}{suffix}"
            ctx = await browser.new_context(viewport=vp, device_scale_factor=scale)
            page = await ctx.new_page()
            await page.goto(url, wait_until="domcontentloaded")
            await stabilize(page)

            shot = SHOTS / f"header-logo-{browser_name}-{key}.png"
            await page.locator(LOGO).screenshot(path=str(shot))
            await ctx.close()

            baseline = BASELINES / f"header-logo-{browser_name}-{key}.png"
            diff_path = DIFFS / f"header-logo-{browser_name}-{key}-diff.png"
            if update or not baseline.exists():
                baseline.write_bytes(shot.read_bytes())
                results.check(
                    f"[{browser_name}] snapshot baseline recorded ({key})", True, baseline.name
                )
                rows.append(
                    {"browser": browser_name, "viewport": key, "scale": scale, "status": "recorded", "diffRatio": 0.0}
                )
                continue

            ok, ratio = compare(shot, baseline, diff_path)
            results.check(
                f"[{browser_name}] word mark snapshot matches baseline ({key})",
                ok,
                f"diff={ratio * 100:.3f}% (max {MAX_DIFF_RATIO * 100:.2f}%)",
            )
            rows.append(
                {
                    "browser": browser_name,
                    "viewport": key,
                    "scale": scale,
                    "status": "pass" if ok else "fail",
                    "diffRatio": round(ratio, 6),
                    "screenshot": str(shot.relative_to(ROOT.parent)),
                    "baseline": str(baseline.relative_to(ROOT.parent)),
                    "diffImage": str(diff_path.relative_to(ROOT.parent)) if diff_path.exists() else None,
                }
            )
    return rows


# ---------------------------------------------------------------- zoom case


async def zoom_case(
    browser, url: str, results: Results, update: bool, browser_name: str
) -> list[dict]:
    """Emulate 125% / 150% browser zoom by shrinking the CSS viewport by the
    zoom factor while rastering at that same device scale factor — the same
    layout + pixel density the browser produces when the user zooms in."""
    SHOTS.mkdir(parents=True, exist_ok=True)
    rows: list[dict] = []
    for name, vp in SNAPSHOT_VIEWPORTS.items():
        for zoom in ZOOM_LEVELS:
            zoomed = {
                "width": max(320, int(vp["width"] / zoom)),
                "height": max(480, int(vp["height"] / zoom)),
            }
            ctx = await browser.new_context(viewport=zoomed, device_scale_factor=zoom)
            page = await ctx.new_page()
            await page.goto(url, wait_until="domcontentloaded")
            await stabilize(page)

            m = await page.evaluate(MEASURE_JS)
            label = f"{name} @{int(zoom * 100)}%"
            if m.get("error"):
                results.check(f"[{browser_name}] zoom {label} measured", False, m["error"])
                await ctx.close()
                continue

            worst, worst_label = 0.0, ""
            for n in m["neighbours"]:
                area = overlap(m["logo"], n)
                if area > worst:
                    worst, worst_label = area, n["label"]
            results.check(
                f"[{browser_name}] logo does not overlap nav/toggle at {label}",
                worst == 0.0,
                f"overlaps {worst_label} by {worst:.0f}px²" if worst else "",
            )

            results.check(
                f"[{browser_name}] word mark stays on one line at {label}",
                m["lineCount"] == 1,
                f"lines={m['lineCount']} height={m['logo']['height']:.1f}px",
            )

            expected_left = m["containerLeft"] + m["containerPaddingLeft"]
            results.check(
                f"[{browser_name}] word mark stays aligned at {label}",
                abs(m["logo"]["left"] - expected_left) <= 1.5,
                f"left={m['logo']['left']:.1f}px expected={expected_left:.1f}px",
            )

            key = f"{name}-zoom{int(zoom * 100)}"
            shot = SHOTS / f"header-logo-{browser_name}-{key}.png"
            await page.locator(LOGO).screenshot(path=str(shot))
            await ctx.close()

            baseline = BASELINES / f"header-logo-{browser_name}-{key}.png"
            diff_path = DIFFS / f"header-logo-{browser_name}-{key}-diff.png"
            if update or not baseline.exists():
                baseline.write_bytes(shot.read_bytes())
                results.check(
                    f"[{browser_name}] zoom baseline recorded ({key})", True, baseline.name
                )
                rows.append({"browser": browser_name, "viewport": key, "zoom": zoom, "status": "recorded", "diffRatio": 0.0})
                continue

            ok, ratio = compare(shot, baseline, diff_path)
            results.check(
                f"[{browser_name}] zoom snapshot matches baseline ({key})",
                ok,
                f"diff={ratio * 100:.3f}%",
            )
            rows.append(
                {
                    "browser": browser_name,
                    "viewport": key,
                    "zoom": zoom,
                    "status": "pass" if ok else "fail",
                    "diffRatio": round(ratio, 6),
                    "screenshot": str(shot.relative_to(ROOT.parent)),
                    "baseline": str(baseline.relative_to(ROOT.parent)),
                    "diffImage": str(diff_path.relative_to(ROOT.parent)) if diff_path.exists() else None,
                }
            )
    return rows


# ----------------------------------------------------------- tap target case


TAP_JS = """
() => {
  const logo = document.querySelector('header a[href="#top"]');
  if (!logo) return { error: 'logo missing' };
  const r = logo.getBoundingClientRect();
  const cs = getComputedStyle(logo);
  // Sample the four corners + centre of the nominal 44x44 target to make sure
  // the link itself (not an overlay) receives the tap.
  const cx = r.left + r.width / 2;
  const cy = r.top + r.height / 2;
  const pts = [[cx, cy], [r.left + 2, cy], [r.right - 2, cy]];
  const hits = pts.map(([x, y]) => {
    const el = document.elementFromPoint(x, y);
    return !!(el && (el === logo || logo.contains(el)));
  });
  return {
    rect: r.toJSON(),
    display: cs.display,
    paddingY: parseFloat(cs.paddingTop) + parseFloat(cs.paddingBottom),
    hittable: hits.every(Boolean),
  };
}
"""


async def tap_target_case(context, url: str, results: Results, browser_name: str) -> list[dict]:
    page = await context.new_page()
    rows: list[dict] = []
    for name, vp in SNAPSHOT_VIEWPORTS.items():
        minimum = MIN_TAP_TARGET if name == "mobile" else MIN_TAP_TARGET_DESKTOP
        await page.set_viewport_size(vp)
        await page.goto(url, wait_until="domcontentloaded")
        await stabilize(page)
        m = await page.evaluate(TAP_JS)
        if m.get("error"):
            results.check(f"[{browser_name}] tap target measured ({name})", False, m["error"])
            continue
        r = m["rect"]
        results.check(
            f"[{browser_name}] word mark tap target is at least {minimum:.0f}px tall ({name})",
            r["height"] >= minimum,
            f"height={r['height']:.1f}px padding={m['paddingY']:.1f}px",
        )
        results.check(
            f"[{browser_name}] word mark tap target is at least {minimum:.0f}px wide ({name})",
            r["width"] >= minimum,
            f"width={r['width']:.1f}px",
        )
        results.check(
            f"[{browser_name}] word mark receives pointer hits across its box ({name})",
            m["hittable"],
        )
        rows.append(
            {
                "browser": browser_name,
                "viewport": name,
                "width": round(r["width"], 2),
                "height": round(r["height"], 2),
                "minimum": minimum,
                "hittable": m["hittable"],
            }
        )
    await page.close()
    return rows


# --------------------------------------------------------------------- main


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default="http://localhost:3000")
    ap.add_argument("--path", default="/")
    ap.add_argument("--only", default="", help="comma list: a11y,layout,snapshot,zoom,tap")
    ap.add_argument(
        "--browsers",
        default="chromium",
        help="comma list: chromium,firefox,webkit (webkit == Safari engine)",
    )
    ap.add_argument("--update-baseline", action="store_true")
    ap.add_argument("--report", default="")
    args = ap.parse_args()

    wanted = {c.strip() for c in args.only.split(",") if c.strip()} or {
        "a11y",
        "layout",
        "snapshot",
        "zoom",
        "tap",
    }
    browsers = [b.strip() for b in args.browsers.split(",") if b.strip()]
    url = args.base_url.rstrip("/") + args.path
    results = Results()
    layout_rows: list[dict] = []
    snapshot_rows: list[dict] = []
    zoom_rows: list[dict] = []
    tap_rows: list[dict] = []

    async with async_playwright() as p:
        for browser_name in browsers:
            try:
                browser = await getattr(p, browser_name).launch(headless=True)
            except Exception as exc:  # engine not installed in this environment
                results.check(
                    f"[{browser_name}] browser engine available", False, str(exc).splitlines()[0]
                )
                continue
            context = await browser.new_context(
                viewport=SNAPSHOT_VIEWPORTS["desktop"], device_scale_factor=1
            )
            # a11y (axe-core) is engine-independent — run it once on chromium.
            if "a11y" in wanted and browser_name == browsers[0]:
                await a11y_case(context, url, results)
            if "layout" in wanted:
                layout_rows += [
                    {**r, "browser": browser_name}
                    for r in await layout_case(context, url, results, browser_name)
                ]
            if "tap" in wanted:
                tap_rows += await tap_target_case(context, url, results, browser_name)
            await context.close()
            if "snapshot" in wanted:
                snapshot_rows += await snapshot_case(
                    browser, url, results, args.update_baseline, browser_name
                )
            if "zoom" in wanted:
                zoom_rows += await zoom_case(
                    browser, url, results, args.update_baseline, browser_name
                )
            await browser.close()

    failed = results.failed
    print(f"\n{len(results.rows) - len(failed)}/{len(results.rows)} checks passed")
    if args.report:
        Path(args.report).parent.mkdir(parents=True, exist_ok=True)
        Path(args.report).write_text(
            json.dumps(
                {
                    "suite": "header-logo",
                    "url": url,
                    "browsers": browsers,
                    "passed": not failed,
                    "checks": results.rows,
                    "layout": layout_rows,
                    "snapshots": snapshot_rows,
                    "zoom": zoom_rows,
                    "tapTargets": tap_rows,
                },
                indent=2,
            )
        )
        print(f"report written to {args.report}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

