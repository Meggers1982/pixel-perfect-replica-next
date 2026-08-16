"""Head metadata assertions.

Verifies the server-rendered <head> of each route (title, description, og:*,
twitter:*, canonical) matches tests/head-metadata.expected.json. The same
expectations run against the TanStack Start app and the Next.js harness, so
SEO output can't drift between them.

Usage:
    python3 tests/head-metadata.py                    # tanstack profile
    python3 tests/head-metadata.py --profile nextjs
    python3 tests/head-metadata.py http://localhost:3000
    python3 tests/head-metadata.py --report /tmp/head.json

Reuses profiles/baseUrl from tests/hero.config.json.
"""

import argparse
import json
import sys
from html import unescape
from pathlib import Path
from urllib.request import urlopen

import re

TESTS_DIR = Path(__file__).parent

parser = argparse.ArgumentParser()
parser.add_argument("base_url", nargs="?")
parser.add_argument("--profile", default=None)
parser.add_argument("--config", default=str(TESTS_DIR / "hero.config.json"))
parser.add_argument("--expected", default=str(TESTS_DIR / "head-metadata.expected.json"))
parser.add_argument("--report", default=None)
args = parser.parse_args()

CONFIG = json.loads(Path(args.config).read_text())
PROFILE_NAME = args.profile or CONFIG.get("defaultProfile", "tanstack")
BASE_URL = (args.base_url or CONFIG["profiles"][PROFILE_NAME]["baseUrl"]).rstrip("/")
EXPECTED = json.loads(Path(args.expected).read_text())

TAG_RE = re.compile(r"<(meta|title|link)\b([^>]*)>(?:([^<]*)</title>)?", re.I)
ATTR_RE = re.compile(r"([a-zA-Z:\-]+)\s*=\s*\"([^\"]*)\"")


def fetch_head(path: str) -> tuple[str | None, dict[str, str], str | None]:
    with urlopen(BASE_URL + path) as response:
        html = response.read().decode("utf-8", "replace").replace("\x00", "")
    head = html.split("</head>", 1)[0]

    title: str | None = None
    metas: dict[str, str] = {}
    canonical: str | None = None

    for tag, raw_attrs, text in TAG_RE.findall(head):
        attrs = {k.lower(): unescape(v) for k, v in ATTR_RE.findall(raw_attrs)}
        tag = tag.lower()
        if tag == "title":
            title = unescape(text.strip())
        elif tag == "meta":
            key = "name:" + attrs["name"] if "name" in attrs else (
                "property:" + attrs["property"] if "property" in attrs else None
            )
            if key:
                metas[key] = attrs.get("content", "")
        elif tag == "link" and attrs.get("rel") == "canonical":
            canonical = attrs.get("href")

    return title, metas, canonical


def main() -> int:
    failures: list[str] = []
    results = []

    for route in EXPECTED["routes"]:
        path = route["path"]
        title, metas, canonical = fetch_head(path)
        route_failures: list[str] = []

        if title != route["title"]:
            route_failures.append(f"title: {title!r} != {route['title']!r}")

        for key, want in route["meta"].items():
            got = metas.get(key)
            if got != want:
                route_failures.append(f"{key}: {got!r} != {want!r}")

        want_canonical = route.get("canonical")
        if want_canonical and canonical != want_canonical:
            route_failures.append(f"canonical: {canonical!r} != {want_canonical!r}")

        # A leaf with og:image must also carry twitter:image, and vice versa.
        has_og_image = "property:og:image" in metas
        has_tw_image = "name:twitter:image" in metas
        if has_og_image != has_tw_image:
            route_failures.append("og:image and twitter:image must both be present or both absent")

        status = "PASS" if not route_failures else "FAIL"
        print(f"{status} {path} ({len(route['meta']) + 2} assertions)")
        for f in route_failures:
            print("   -", f)
        failures += [f"{path}: {f}" for f in route_failures]
        results.append({"path": path, "passed": not route_failures, "failures": route_failures})

    report = {
        "suite": "head-metadata",
        "profile": PROFILE_NAME,
        "url": BASE_URL,
        "passed": not failures,
        "results": results,
    }
    if args.report:
        Path(args.report).parent.mkdir(parents=True, exist_ok=True)
        Path(args.report).write_text(json.dumps(report, indent=2))

    if failures:
        print(f"\nFAIL: {len(failures)} metadata mismatch(es) on profile {PROFILE_NAME}")
        return 1
    print(f"\nPASS: head metadata matches expectations on profile {PROFILE_NAME}")
    return 0


sys.exit(main())
