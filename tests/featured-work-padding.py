#!/usr/bin/env python3
"""Layout assertion: the FeaturedWork carousel must start at the same left
padding edge as the section heading, at every configured viewport.

Shares tests/hero.config.json (profiles + viewports + tolerance) so it runs
against either the TanStack Start app or the Next.js harness:

    python3 tests/featured-work-padding.py                        # tanstack (default)
    python3 tests/featured-work-padding.py --profile nextjs
    python3 tests/featured-work-padding.py --only 375,1280        # fast local subset
    python3 tests/featured-work-padding.py --padding-tolerance 1.5
    python3 tests/featured-work-padding.py --update-baseline      # re-record offsets

Every run writes annotated screenshots (a red guide line on the heading's left
edge, the card's edge, and the measured delta) plus an HTML gallery for CI:

    tests/screenshots/featured-work/<profile>-<viewport>.png
    tests/report/featured-work-gallery-<profile>.html
"""

import argparse
import asyncio
import html
import json
import sys
from pathlib import Path

from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parent
CONFIG_PATH = ROOT / "hero.config.json"

MEASURE_JS = """
() => {
  const section = document.querySelector('#work');
  if (!section) return { error: 'no #work section' };
  const label = section.querySelector('p');
  const heading = section.querySelector('h2');
  const card = section.querySelector('article');
  const row = card ? card.parentElement : null;
  if (!label || !heading || !card || !row) return { error: 'missing heading or card nodes' };
  const cs = getComputedStyle(row);
  const sr = section.getBoundingClientRect();
  return {
    label: label.getBoundingClientRect().left,
    heading: heading.getBoundingClientRect().left,
    card: card.getBoundingClientRect().left,
    rowPaddingLeft: parseFloat(cs.paddingLeft),
    rowScrollLeft: row.scrollLeft,
    sectionTop: sr.top + window.scrollY,
    sectionHeight: sr.height,
  };
}
"""

# Draws the measured guides straight onto the page before the screenshot.
ANNOTATE_JS = """
({ heading, card, delta, baselineDelta, tolerance, viewport, status }) => {
  const overlay = document.createElement('div');
  overlay.id = '__fw_overlay';
  overlay.style.cssText =
    'position:absolute;inset:0;pointer-events:none;z-index:2147483647;font:12px/1.4 monospace;';
  const section = document.querySelector('#work');
  section.style.position = 'relative';

  const guide = (x, color, label, top) => {
    const line = document.createElement('div');
    line.style.cssText =
      `position:absolute;left:${x}px;top:0;bottom:0;width:1px;background:${color};opacity:.9;`;
    overlay.appendChild(line);
    const tag = document.createElement('div');
    tag.textContent = label;
    tag.style.cssText =
      `position:absolute;left:${x + 4}px;top:${top}px;color:#fff;background:${color};` +
      'padding:2px 6px;white-space:nowrap;letter-spacing:.06em;';
    overlay.appendChild(tag);
  };

  guide(heading, '#d92b1c', `heading ${heading.toFixed(1)}px`, 8);
  guide(card, '#1b6ef3', `card ${card.toFixed(1)}px`, 30);

  const badge = document.createElement('div');
  const base = baselineDelta === null || baselineDelta === undefined
    ? 'baseline —'
    : `baseline ${baselineDelta.toFixed(2)}px`;
  badge.textContent =
    `${viewport} · ${status} · delta ${delta.toFixed(2)}px · ${base} · tol ${tolerance}px`;
  badge.style.cssText =
    'position:absolute;right:8px;top:8px;padding:6px 10px;color:#fff;letter-spacing:.06em;' +
    `background:${status === 'pass' ? '#1a7f37' : '#d92b1c'};`;
  overlay.appendChild(badge);
  section.appendChild(overlay);
}
"""


# Draws a baseline-vs-current comparison band for the failing/current delta.
DIFF_JS = """
({ heading, card, baselineCard, delta, baselineDelta, drift, tolerance, viewport, status }) => {
  const prev = document.getElementById('__fw_overlay');
  if (prev) prev.remove();
  const section = document.querySelector('#work');
  section.style.position = 'relative';
  const overlay = document.createElement('div');
  overlay.id = '__fw_overlay';
  overlay.style.cssText =
    'position:absolute;inset:0;pointer-events:none;z-index:2147483647;font:12px/1.4 monospace;';

  const line = (x, color, dashed) => {
    const el = document.createElement('div');
    el.style.cssText =
      `position:absolute;left:${x}px;top:0;bottom:0;width:0;border-left:2px ${dashed ? 'dashed' : 'solid'} ${color};`;
    overlay.appendChild(el);
  };
  const tag = (x, top, color, text) => {
    const el = document.createElement('div');
    el.textContent = text;
    el.style.cssText =
      `position:absolute;left:${x + 6}px;top:${top}px;color:#fff;background:${color};` +
      'padding:2px 6px;white-space:nowrap;letter-spacing:.06em;';
    overlay.appendChild(el);
  };

  line(heading, '#d92b1c', false);
  tag(heading, 8, '#d92b1c', `heading ${heading.toFixed(1)}px`);

  if (baselineCard !== null && baselineCard !== undefined) {
    line(baselineCard, '#8a6d00', true);
    tag(baselineCard, 30, '#8a6d00', `baseline card ${baselineCard.toFixed(1)}px`);
    const lo = Math.min(baselineCard, card);
    const band = document.createElement('div');
    band.style.cssText =
      `position:absolute;left:${lo}px;top:0;bottom:0;width:${Math.max(Math.abs(card - baselineCard), 1)}px;` +
      'background:repeating-linear-gradient(45deg,rgba(217,43,28,.35) 0 6px,rgba(217,43,28,.12) 6px 12px);';
    overlay.appendChild(band);
  }

  line(card, '#1b6ef3', false);
  tag(card, 52, '#1b6ef3', `card ${card.toFixed(1)}px`);

  const badge = document.createElement('div');
  badge.textContent =
    `DIFF · ${viewport} · ${status} · delta ${delta.toFixed(2)}px · ` +
    `baseline ${baselineDelta === null || baselineDelta === undefined ? '—' : baselineDelta.toFixed(2) + 'px'} · ` +
    `drift ${drift === null || drift === undefined ? '—' : drift.toFixed(2) + 'px'} · tol ${tolerance}px`;
  badge.style.cssText =
    'position:absolute;right:8px;top:8px;padding:6px 10px;color:#fff;letter-spacing:.06em;' +
    `background:${status === 'pass' ? '#1a7f37' : '#d92b1c'};`;
  overlay.appendChild(badge);
  section.appendChild(overlay);
}
"""

# Friendly group aliases for --viewports.
GROUPS = {
    "mobile": ("mobile",),
    "phone": ("mobile",),
    "tablet": ("tablet",),
    "laptop": ("laptop",),
    "desktop": ("desktop",),
    "all": (),
}


def select_viewports(viewports, only):
    if not only:
        return viewports
    wanted = [t.strip().lower() for t in only.split(",") if t.strip()]
    if any(t == "all" for t in wanted):
        return viewports
    picked = []
    for vp in viewports:
        name = vp["name"].lower()
        for t in wanted:
            prefixes = GROUPS.get(t)
            hit = (
                any(name.startswith(p) for p in prefixes)
                if prefixes
                else (t == name or t == str(vp["width"]) or t in name)
            )
            if hit:
                picked.append(vp)
                break
    return picked


def write_gallery(gallery_path: Path, report: dict) -> None:
    gallery_path.parent.mkdir(parents=True, exist_ok=True)
    rows = sorted(report["results"], key=lambda r: (r["status"] == "pass", r.get("width", 0)))
    cards = []
    for r in rows:
        ok = r["status"] == "pass"
        shot = r.get("screenshot")
        img = (
            f'<img src="../screenshots/featured-work/{html.escape(Path(shot).name)}" alt="{html.escape(r["viewport"])}" />'
            if shot
            else "<p>no screenshot</p>"
        )
        diff = r.get("diffImage")
        diff_img = (
            f'<figure><figcaption>baseline vs current</figcaption>'
            f'<img src="../diffs/featured-work/{html.escape(Path(diff).name)}" alt="{html.escape(r["viewport"])} diff" /></figure>'
            if diff
            else ""
        )
        base = r.get("baselineDelta")
        cards.append(
            f"""
      <section class="card {'pass' if ok else 'fail'}">
        <h2>{html.escape(r['viewport'])} <span>{r['status'].upper()}</span></h2>
        <dl>
          <div><dt>heading left</dt><dd>{r.get('headingLeft', '—')}</dd></div>
          <div><dt>card left</dt><dd>{r.get('cardLeft', '—')}</dd></div>
          <div><dt>current delta</dt><dd>{r.get('deltaHeading', '—')}px</dd></div>
          <div><dt>baseline delta</dt><dd>{'—' if base is None else str(base) + 'px'}</dd></div>
          <div><dt>drift vs baseline</dt><dd>{r.get('baselineDrift', '—')}</dd></div>
          <div><dt>tolerance</dt><dd>{r.get('tolerance', '—')}px</dd></div>
        </dl>
        <div class="shots"><figure><figcaption>measured</figcaption>{img}</figure>{diff_img}</div>
      </section>"""
        )
    gallery_path.write_text(
        f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8" />
<title>FeaturedWork padding — {html.escape(report['profile'])}</title>
<style>
 body{{font:14px/1.5 system-ui,sans-serif;margin:0;padding:24px;background:#f6f3ec;color:#111}}
 h1{{margin:0 0 4px}} .meta{{color:#555;margin-bottom:24px}}
 .card{{background:#fff;border-left:6px solid #1a7f37;padding:16px;margin-bottom:24px}}
 .card.fail{{border-color:#d92b1c}}
 .card h2{{margin:0 0 12px;font-size:16px}}
 .card h2 span{{font-size:12px;padding:2px 8px;background:#1a7f37;color:#fff;margin-left:8px}}
 .card.fail h2 span{{background:#d92b1c}}
 dl{{display:flex;flex-wrap:wrap;gap:8px 24px;margin:0 0 12px}}
 dl div{{min-width:120px}} dt{{font-size:11px;text-transform:uppercase;color:#666}} dd{{margin:0;font-weight:600}}
 img{{max-width:100%;border:1px solid #ddd}}
 .shots{{display:grid;gap:16px;grid-template-columns:repeat(auto-fit,minmax(320px,1fr))}}
 figure{{margin:0}} figcaption{{font-size:11px;text-transform:uppercase;color:#666;margin-bottom:4px}}
</style></head><body>
<h1>FeaturedWork carousel padding</h1>
<p class="meta">profile <b>{html.escape(report['profile'])}</b> · {html.escape(report['url'])} ·
 {sum(1 for r in rows if r['status'] == 'pass')}/{len(rows)} aligned · failures first</p>
{''.join(cards)}
</body></html>"""
    )
    print(f"gallery written to {gallery_path}")


async def run(args):
    config = json.loads(CONFIG_PATH.read_text())
    profile_name = args.profile or config.get("defaultProfile", "tanstack")
    profile = config["profiles"][profile_name]
    url = profile["baseUrl"].rstrip("/") + profile.get("path", "/")
    viewports = select_viewports(config["viewports"], args.only)
    tol = args.tolerance if args.tolerance is not None else config.get("paddingTolerance", 6)

    shots_dir = ROOT / "screenshots" / "featured-work"
    shots_dir.mkdir(parents=True, exist_ok=True)
    diffs_dir = ROOT / "diffs" / "featured-work"
    if not args.no_diff_images:
        diffs_dir.mkdir(parents=True, exist_ok=True)
    baseline_path = ROOT / "baselines" / f"featured-work-offsets-{profile_name}.json"
    baselines = json.loads(baseline_path.read_text()) if baseline_path.exists() else {}
    new_baselines = dict(baselines)

    results = []
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        for vp in viewports:
            context = await browser.new_context(
                viewport={"width": vp["width"], "height": vp["height"]}
            )
            page = await context.new_page()
            await page.goto(url, wait_until="networkidle")
            await page.evaluate("document.fonts.ready")
            await page.evaluate(
                "() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))"
            )
            m = await page.evaluate(MEASURE_JS)

            if m.get("error"):
                results.append({"viewport": vp["name"], "status": "fail", "reason": m["error"]})
                print(f"FAIL {vp['name']:>13}  {m['error']}")
                await context.close()
                continue

            d_heading = round(abs(m["card"] - m["heading"]), 2)
            d_label = round(abs(m["card"] - m["label"]), 2)
            baseline_delta = baselines.get(vp["name"])
            drift = (
                None if baseline_delta is None else round(abs(d_heading - baseline_delta), 2)
            )
            ok = d_heading <= tol and d_label <= tol and m["rowScrollLeft"] == 0
            if drift is not None and drift > tol:
                ok = False

            await page.evaluate(
                ANNOTATE_JS,
                {
                    "heading": m["heading"],
                    "card": m["card"],
                    "delta": d_heading,
                    "baselineDelta": baseline_delta,
                    "tolerance": tol,
                    "viewport": vp["name"],
                    "status": "pass" if ok else "fail",
                },
            )
            shot = shots_dir / f"{profile_name}-{vp['name']}.png"
            await page.locator("#work").screenshot(path=str(shot))

            # Per-viewport diff image: current card edge vs the baseline edge.
            diff_path = None
            if not args.no_diff_images:
                baseline_card = (
                    None if baseline_delta is None else m["heading"] + baseline_delta
                )
                await page.evaluate(
                    DIFF_JS,
                    {
                        "heading": m["heading"],
                        "card": m["card"],
                        "baselineCard": baseline_card,
                        "delta": d_heading,
                        "baselineDelta": baseline_delta,
                        "drift": drift,
                        "tolerance": tol,
                        "viewport": vp["name"],
                        "status": "pass" if ok else "fail",
                    },
                )
                diff_path = diffs_dir / f"{profile_name}-{vp['name']}-diff.png"
                await page.locator("#work").screenshot(path=str(diff_path))

            await context.close()

            if args.update_baseline:
                new_baselines[vp["name"]] = d_heading

            results.append(
                {
                    "viewport": vp["name"],
                    "width": vp["width"],
                    "status": "pass" if ok else "fail",
                    "headingLeft": round(m["heading"], 2),
                    "cardLeft": round(m["card"], 2),
                    "deltaHeading": d_heading,
                    "deltaLabel": d_label,
                    "baselineDelta": baseline_delta,
                    "baselineDrift": drift,
                    "rowScrollLeft": m["rowScrollLeft"],
                    "tolerance": tol,
                    "screenshot": str(shot.relative_to(ROOT.parent)),
                    "diffImage": None if diff_path is None else str(diff_path.relative_to(ROOT.parent)),
                }
            )
            print(
                f"{'PASS' if ok else 'FAIL'} {vp['name']:>13}  heading={m['heading']:.0f}px "
                f"card={m['card']:.0f}px delta={d_heading:.2f}px "
                f"baseline={'—' if baseline_delta is None else f'{baseline_delta:.2f}px'} "
                f"scrollLeft={m['rowScrollLeft']}"
            )
        await browser.close()

    if args.update_baseline:
        baseline_path.parent.mkdir(parents=True, exist_ok=True)
        baseline_path.write_text(json.dumps(new_baselines, indent=2, sort_keys=True))
        print(f"baseline offsets written to {baseline_path}")

    failures = [r for r in results if r["status"] == "fail"]
    report = {
        "suite": "featured-work-padding",
        "profile": profile_name,
        "url": url,
        "tolerance": tol,
        "passed": not failures,
        "results": results,
    }
    gallery = (
        Path(args.gallery)
        if args.gallery
        else ROOT / "report" / f"featured-work-gallery-{profile_name}.html"
    )
    if not args.no_gallery:
        write_gallery(gallery, report)
        report["gallery"] = str(gallery.relative_to(ROOT.parent))
    if args.report:
        Path(args.report).parent.mkdir(parents=True, exist_ok=True)
        Path(args.report).write_text(json.dumps(report, indent=2))
        print(f"report written to {args.report}")

    # Machine-readable summary shipped next to the HTML gallery in CI artifacts.
    summary_path = (
        Path(args.summary)
        if args.summary
        else ROOT / "report" / f"featured-work-summary-{profile_name}.json"
    )
    summary = {
        "suite": "featured-work-padding",
        "profile": profile_name,
        "url": url,
        "tolerance": tol,
        "passed": not failures,
        "total": len(results),
        "failed": len(failures),
        "gallery": report.get("gallery"),
        "viewports": [
            {
                "viewport": r["viewport"],
                "width": r.get("width"),
                "leftEdge": r.get("cardLeft"),
                "headingLeft": r.get("headingLeft"),
                "delta": r.get("deltaHeading"),
                "baselineDelta": r.get("baselineDelta"),
                "drift": r.get("baselineDrift"),
                "tolerance": r.get("tolerance", tol),
                "status": r["status"],
                "reason": r.get("reason"),
                "screenshot": r.get("screenshot"),
                "diffImage": r.get("diffImage"),
            }
            for r in results
        ],
    }
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, indent=2))
    print(f"summary written to {summary_path}")

    print(f"\n{len(results) - len(failures)}/{len(results)} viewports aligned (tolerance {tol}px)")
    return 1 if failures else 0


EXAMPLES = """
examples:
  # full run (all viewports, annotated shots + diffs + gallery + JSON summary)
  python3 tests/featured-work-padding.py

  # only some breakpoints — group aliases or exact names/widths
  python3 tests/featured-work-padding.py --viewports mobile,tablet
  python3 tests/featured-work-padding.py --viewports desktop-1440,375

  # allow small sub-pixel drift
  python3 tests/featured-work-padding.py --padding-tolerance 1.5
  python3 tests/featured-work-padding.py --tolerance 1.5      # same flag

  # re-record the per-viewport baseline offsets after an intentional change
  python3 tests/featured-work-padding.py --update-baseline

  # run it through the hero suite entrypoint instead
  python3 tests/hero-headline.py --only-featured-work

  # Next.js harness
  python3 tests/featured-work-padding.py --profile nextjs --viewports desktop

outputs:
  tests/screenshots/featured-work/<profile>-<viewport>.png       annotated measurement
  tests/diffs/featured-work/<profile>-<viewport>-diff.png        baseline vs current edge
  tests/report/featured-work-gallery-<profile>.html              HTML gallery (CI artifact)
  tests/report/featured-work-summary-<profile>.json              machine-readable summary
  tests/report-featured-work.json                                full run report
"""


def main():
    ap = argparse.ArgumentParser(
        prog="featured-work-padding.py",
        description=(
            "Assert the FeaturedWork carousel starts at the same left padding edge as the "
            "section heading at every viewport, writing annotated screenshots, per-viewport "
            "diff images, an HTML gallery and a JSON summary."
        ),
        epilog=EXAMPLES,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument(
        "--profile",
        default=None,
        help="profile from tests/hero.config.json (tanstack | nextjs); default: tanstack",
    )
    ap.add_argument(
        "--viewports",
        "--only",
        dest="only",
        default=None,
        metavar="LIST",
        help=(
            "comma-separated breakpoints to run: group aliases (mobile, tablet, laptop, "
            "desktop, all), exact names (desktop-1440) or widths (375). Default: all"
        ),
    )
    ap.add_argument(
        "--padding-tolerance",
        "--tolerance",
        dest="tolerance",
        type=float,
        default=None,
        help="allowed left-edge drift in px (default from hero.config.json paddingTolerance)",
    )
    ap.add_argument(
        "--update-baseline",
        action="store_true",
        help=(
            "re-record the per-viewport baseline offsets in "
            "tests/baselines/featured-work-offsets-<profile>.json"
        ),
    )
    ap.add_argument("--gallery", default=None, help="path for the annotated HTML gallery")
    ap.add_argument("--no-gallery", action="store_true", help="skip the HTML gallery")
    ap.add_argument(
        "--no-diff-images",
        action="store_true",
        help="skip the per-viewport baseline-vs-current diff images",
    )
    ap.add_argument(
        "--summary",
        default=None,
        metavar="PATH",
        help="path for the machine-readable JSON summary (default: tests/report/featured-work-summary-<profile>.json)",
    )
    ap.add_argument(
        "--report",
        default=str(ROOT / "report-featured-work.json"),
        help="path for the full JSON run report",
    )
    args = ap.parse_args()
    sys.exit(asyncio.run(run(args)))


if __name__ == "__main__":
    main()
