"""Render a markdown PR comment summarizing the hero visual + metadata suites.

Reads tests/report-hero.json and tests/report-head.json (written by the test
scripts with --report) and prints markdown to stdout.
"""

import json
import os
from pathlib import Path

MARKER = "<!-- hero-visual-regression -->"
ARTIFACT_URL = os.environ.get("ARTIFACT_URL", "")
RUN_URL = os.environ.get("RUN_URL", "")

hero_path = Path("tests/report-hero.json")
head_path = Path("tests/report-head.json")

lines = [MARKER, "## Hero visual regression", ""]

if not hero_path.exists():
    lines += ["The hero screenshot suite did not produce a report — it likely crashed before running.", ""]
else:
    hero = json.loads(hero_path.read_text())
    results = hero["results"]
    failed = [r for r in results if r.get("blocking", not r["passed"])]
    quarantined = [r for r in results if r.get("quarantined") and not r["passed"]]
    status = "✅ all viewports match the baseline" if not failed else (
        f"❌ {len(failed)} of {len(results)} viewports changed"
    )
    lines += [f"**{status}** — profile `{hero['profile']}`, {len(results)} viewports checked.", ""]

    if failed:
        lines += ["| Viewport | Size | What changed |", "| --- | --- | --- |"]
        for r in failed:
            why = "<br>".join(f.split(": ", 1)[-1] for f in r["failures"])
            lines.append(f"| `{r['viewport']}` | {r['width']}×{r['height']} | {why} |")
        lines += [
            "",
            "Diff images are three panels: **baseline | current | changed pixels (magenta)**.",
            "",
            "If the change is intended, re-record just these viewports: "
            "`python tests/hero-headline.py --update-only-failures`.",
            "",
        ]
    else:
        lines += ["<details><summary>Viewports checked</summary>", ""]
        lines += ["| Viewport | Size | Lines |", "| --- | --- | --- |"]
        for r in results:
            lines.append(f"| `{r['viewport']}` | {r['width']}×{r['height']} | {r['lines']} |")
        lines += ["", "</details>", ""]

    if quarantined:
        names = ", ".join(f"`{r['viewport']}`" for r in quarantined)
        lines += [f"🟣 Quarantined (reported, not blocking): {names}", ""]

    flaky = [r for r in results if r.get("flaky")]
    if flaky:
        names = ", ".join(f"`{r['viewport']}` ({r['attempts']} attempts)" for r in flaky)
        lines += [f"⚠️ Recovered on retry: {names}", ""]

    if hero.get("gallery"):
        lines += [
            f"Open `{hero['gallery']}` from the artifact for the full HTML gallery "
            "(failed viewports listed first, with inline diffs).",
            "",
        ]

fw_path = Path("tests/report-featured-work.json")
if fw_path.exists():
    fw = json.loads(fw_path.read_text())
    fw_failed = [r for r in fw["results"] if r["status"] != "pass"]
    lines.append("### FeaturedWork padding")
    if not fw_failed:
        lines += [
            f"✅ carousel is flush with the section heading at all {len(fw['results'])} "
            f"viewports (tolerance {fw['tolerance']}px).",
            "",
        ]
    else:
        lines += ["❌ left-edge drift detected:", ""]
        for r in fw_failed:
            base = r.get("baselineDelta")
            base_txt = "—" if base is None else f"{base}px"
            diff = r.get("diffImage")
            diff_txt = f" · diff `{diff}`" if diff else ""
            lines.append(
                f"- `{r['viewport']}` — heading {r.get('headingLeft')}px vs card "
                f"{r.get('cardLeft')}px · delta {r.get('deltaHeading')}px "
                f"(baseline {base_txt}, drift {r.get('baselineDrift')}){diff_txt}"
            )
        lines.append("")
    if fw.get("gallery"):
        lines += [
            f"Annotated overlay gallery (measured left-edge guides + baseline delta): "
            f"`{fw['gallery']}` in the artifact.",
            "",
        ]
    fw_summary = Path(f"tests/report/featured-work-summary-{fw['profile']}.json")
    if fw_summary.exists():
        lines += [
            f"Machine-readable summary (per-viewport left edge, baseline, delta, tolerance, "
            f"pass/fail): `{fw_summary}` in the same artifact.",
            "",
        ]

hl_path = Path("tests/report-header-logo.json")
if hl_path.exists():
    hl = json.loads(hl_path.read_text())
    hl_failed = [c for c in hl["checks"] if c["status"] != "pass"]
    lines.append("### Header word mark (Brand Ledger)")
    if not hl_failed:
        lines += [
            f"\u2705 {len(hl['checks'])} checks passed across "
            f"{', '.join(hl.get('browsers', ['chromium']))} \u2014 accessible name, focus indicator, "
            "axe-core/contrast, resize overlap sweep, 1x + retina (2x) snapshots, "
            "125%/150% zoom snapshots and mobile/desktop tap-target sizing.",
            "",
        ]
    else:
        lines += ["\u274c header word mark issues:", ""]
        for c in hl_failed:
            detail = f" \u2014 {c['detail']}" if c.get("detail") else ""
            lines.append(f"- {c['name']}{detail}")
        lines.append("")
    snap_failed = [
        s_
        for s_ in hl.get("snapshots", []) + hl.get("zoom", [])
        if s_.get("status") == "fail"
    ]
    for s_ in snap_failed:
        lines.append(
            f"- snapshot `{s_.get('browser', 'chromium')}/{s_['viewport']}` diff {s_['diffRatio'] * 100:.3f}% "
            f"\u00b7 `{s_.get('diffImage')}`"
        )
    if snap_failed:
        lines.append("")

mn_path = Path("tests/report-mobile-nav.json")
if mn_path.exists():
    mn = json.loads(mn_path.read_text())
    cases = mn.get("cases", [])
    blocking = [c for c in cases if c.get("blocking")]
    flaky = [c for c in cases if c.get("flaky")]
    quarantined_failed = [c for c in cases if c.get("quarantined") and not c.get("passed")]
    checks = mn.get("results", [])
    lines.append("### Mobile navigation")
    if not blocking:
        lines += [
            f"\u2705 {len([c for c in checks if c['status'] == 'pass'])}/{len(checks)} checks passed "
            f"across {len(cases)} case(s) \u2014 retries {mn.get('retries', 0)}, "
            f"flake rate this run {mn.get('flakeRate', 0) * 100:.0f}%.",
            "",
        ]
    else:
        lines += [f"\u274c {len(blocking)} case(s) failed after retries:", ""]
        for c in blocking:
            lines.append(f"- `{c['case']}` ({c['attempts']} attempts) \u2014 " + ", ".join(c["failures"][:4]))
        lines.append("")
    if flaky:
        names = ", ".join(f"`{c['case']}` ({c['attempts']} attempts)" for c in flaky)
        lines += [f"\u26a0\ufe0f Recovered on retry: {names}", ""]
    if quarantined_failed:
        names = ", ".join(f"`{c['case']}`" for c in quarantined_failed)
        lines += [f"\U0001f7e3 Quarantined (reported, not blocking): {names}", ""]
    per_case = mn.get("history", {}).get("perCase", {})
    if per_case:
        lines += [
            f"<details><summary>Flake rate over the last "
            f"{mn['history'].get('runsTracked', 0)} run(s)</summary>",
            "",
            "| Case | Runs | Flaky | Failed | Flake rate |",
            "| --- | --- | --- | --- | --- |",
        ]
        for case, stat in sorted(per_case.items()):
            lines.append(
                f"| `{case}` | {stat['runs']} | {stat['flaky']} | {stat['failed']} | "
                f"{stat['flakeRate'] * 100:.0f}% |"
            )
        lines += ["", "</details>", ""]

if head_path.exists():
    head = json.loads(head_path.read_text())
    head_failed = [r for r in head["results"] if not r["passed"]]
    lines.append("### Head metadata")
    if not head_failed:
        lines += [f"✅ title, description, `og:*`, `twitter:*` and canonical match for all {len(head['results'])} route(s).", ""]
    else:
        lines += ["❌ metadata mismatches:", ""]
        for r in head_failed:
            for f in r["failures"]:
                lines.append(f"- `{r['path']}` — {f}")
        lines.append("")

fc_path = Path("tests/report-footer-contact.json")
if fc_path.exists():
    fc = json.loads(fc_path.read_text())
    fc_failed = [r for r in fc["results"] if not r["passed"]]
    lines.append("### Footer contact")
    if not fc_failed:
        lines += [
            f"✅ email, mailto link, location and no-phone-number assertions pass at all "
            f"{len(fc['results'])} viewport(s).",
            "",
        ]
    else:
        lines += ["❌ footer contact regression issue(s):", ""]
        for r in fc_failed:
            for f in r["failures"]:
                lines.append(f"- `{r['viewport']}` — {f}")
        lines.append("")

if ARTIFACT_URL:
    lines.append(f"[Download screenshots & diffs]({ARTIFACT_URL})")
if RUN_URL:
    lines.append(f" · [Workflow run]({RUN_URL})")

print("\n".join(lines))

for suite_file, heading in [
    ("tests/report-section-semantics.json", "Section semantics (headings, landmarks, axe)"),
    ("tests/report-section-contrast.json", "Sitewide contrast (AA, pixel-sampled)"),
    ("tests/report-section-transitions.json", "Section-to-section transitions"),
]:
    path = Path(suite_file)
    if not path.exists():
        continue
    data = json.loads(path.read_text())
    results = data.get("results", [])
    failed = [r for r in results if not r.get("passed")]
    lines.append(f"### {heading}")
    if not failed:
        lines += [f"\u2705 {len(results)} cases passed.", ""]
    else:
        lines += [f"\u274c {len(failed)}/{len(results)} cases failed:", ""]
        for r in failed:
            for f in r["failures"][:6]:
                lines.append(f"- {f}")
        lines.append("")
