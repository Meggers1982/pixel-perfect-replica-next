#!/usr/bin/env python3
"""Generate public/og.jpg — the 1200x630 Open Graph / Twitter card.

Built as a static asset rather than a runtime `next/og` route: Satori (which
backs ImageResponse) cannot read woff2, and the brand's display face is only
distributed here as a woff2 subset. Rendering it once with Pillow keeps the
real Anton letterforms and costs nothing per request.

Run after changing the hero image, the headline, or the brand palette:

    python3 scripts/build-og-image.py

Requires: pillow, fonttools[woff]  (pip install pillow fonttools brotli)
"""

import io
import pathlib

from fontTools.ttLib import TTFont
from PIL import Image, ImageDraw, ImageFont

ROOT = pathlib.Path(__file__).resolve().parent.parent
PUBLIC = ROOT / "public"
OUT = PUBLIC / "og.jpg"

W, H = 1200, 630

# Resolved from the oklch custom properties in app/globals.css.
CREAM = (248, 244, 234)
INK = (13, 13, 13)
ACCENT_ON_DARK = (255, 104, 92)

HEADLINE = ["WE BUILD BRANDS", "THAT BEHAVE", "LIKE BUSINESSES"]
WORDMARK = ("BRAND ", "LEDGER")
FOOTER_LEFT = "BRAND & DIGITAL STUDIO"
FOOTER_RIGHT = "OMAHA, NEBRASKA"


def load_font(woff2: pathlib.Path, size: int) -> ImageFont.FreeTypeFont:
    """Pillow cannot open woff2; decompress to an in-memory TTF first."""
    font = TTFont(str(woff2), fontNumber=0)
    buf = io.BytesIO()
    font.flavor = None
    font.save(buf)
    buf.seek(0)
    return ImageFont.truetype(buf, size)


def tracked_text(draw, xy, text, font, fill, tracking=0):
    """Pillow has no letter-spacing; step glyph by glyph."""
    x, y = xy
    for char in text:
        draw.text((x, y), char, font=font, fill=fill)
        x += draw.textlength(char, font=font) + tracking
    return x


def tracked_width(draw, text, font, tracking=0):
    return sum(draw.textlength(c, font=font) + tracking for c in text) - tracking


def main() -> None:
    hero = Image.open(PUBLIC / "images" / "hero.jpg").convert("RGB")

    # Cover-crop the hero to the card ratio, matching the site's object-cover.
    scale = max(W / hero.width, H / hero.height)
    hero = hero.resize((round(hero.width * scale), round(hero.height * scale)), Image.LANCZOS)
    left = (hero.width - W) // 2
    top = (hero.height - H) // 2
    card = hero.crop((left, top, left + W, top + H))

    # The hero's directional scrim: dense behind the copy on the left, clearing
    # to the right so the photograph still reads.
    scrim = Image.new("L", (W, 1))
    for x in range(W):
        t = x / (W - 1)
        scrim.putpixel((x, 0), int(242 - 132 * t))  # 0.95 -> 0.43 alpha
    scrim = scrim.resize((W, H))
    card = Image.composite(Image.new("RGB", (W, H), INK), card, scrim)

    # A bottom-up wash so the footer rule keeps contrast over a bright photo.
    bottom = Image.new("L", (1, H))
    for y in range(H):
        t = y / (H - 1)
        bottom.putpixel((0, y), int(0 if t < 0.55 else 150 * ((t - 0.55) / 0.45) ** 1.6))
    card = Image.composite(Image.new("RGB", (W, H), INK), card, bottom.resize((W, H)))

    draw = ImageDraw.Draw(card)
    anton = lambda s: load_font(PUBLIC / "fonts" / "anton-400.woff2", s)
    barlow = lambda s: load_font(PUBLIC / "fonts" / "barlow-500.woff2", s)

    margin = 64

    # Wordmark, top left — Barlow 500, uppercase, tracked, "Ledger" in accent.
    mark = barlow(30)
    x = tracked_text(draw, (margin, margin - 6), WORDMARK[0], mark, CREAM, tracking=4.8)
    tracked_text(draw, (x, margin - 6), WORDMARK[1], mark, ACCENT_ON_DARK, tracking=4.8)

    # Headline, Anton, three lines, optically flush to the left margin.
    size = 92
    head = anton(size)
    while max(draw.textlength(line, font=head) for line in HEADLINE) > W - margin * 2:
        size -= 2
        head = anton(size)

    line_height = round(size * 0.93)  # matches the .display utility
    block_h = line_height * len(HEADLINE)
    y = H - margin - 74 - block_h
    for line in HEADLINE:
        draw.text((margin - round(size * 0.045), y), line, font=head, fill=CREAM)
        y += line_height

    # Footer rule + standfirst.
    rule_y = H - margin - 34
    draw.line([(margin, rule_y), (W - margin, rule_y)], fill=ACCENT_ON_DARK, width=3)

    foot = barlow(21)
    tracked_text(draw, (margin, rule_y + 16), FOOTER_LEFT, foot, CREAM, tracking=3.4)
    right_w = tracked_width(draw, FOOTER_RIGHT, foot, tracking=3.4)
    tracked_text(draw, (W - margin - right_w, rule_y + 16), FOOTER_RIGHT, foot, CREAM, tracking=3.4)

    card.save(OUT, "JPEG", quality=88, optimize=True, progressive=True)
    print(f"wrote {OUT.relative_to(ROOT)} ({OUT.stat().st_size // 1024} KB, {W}x{H})")


if __name__ == "__main__":
    main()
