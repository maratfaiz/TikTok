#!/usr/bin/env python3
"""Compose TikTok photo-post images from a base photo.

Two modes:
  hero  - base image + headline overlay (font depends on --font-style, see
          config.json fonts.headline_styles). This is the first/cover image.
  plain - base image resized/cropped to canvas and saved as JPEG, no text.
          Used for the extra carousel images.

Usage:
    python3 compose_post.py hero --image <path-or-url> --title "THEME" \
        --font-style romance --out /tmp/post_1.jpg
    python3 compose_post.py plain --image <path-or-url> --out /tmp/post_2.jpg
"""
import argparse
import io
import json
import urllib.request
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

# TikTok photo posts must fit within 1920x1080 or 1080x1920 - portrait,
# square and landscape are all fine as long as neither dimension exceeds
# that bound. We snap each source photo to whichever of these three shapes
# is closest to its own aspect ratio, instead of always force-cropping to
# a vertical "story" frame.
CANVAS_CHOICES = [
    (1080, 1350),  # portrait - Instagram-post ratio (4:5), not a 9:16 story
    (1080, 1080),  # square
    (1920, 1080),  # landscape
]
AUTOMATION_DIR = Path(__file__).parent
FONT_DIR = AUTOMATION_DIR / "fonts"
CONFIG_PATH = AUTOMATION_DIR / "config.json"


def load_config() -> dict:
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def load_image(source: str) -> Image.Image:
    if source.startswith("http://") or source.startswith("https://"):
        with urllib.request.urlopen(source) as resp:
            data = resp.read()
        return Image.open(io.BytesIO(data)).convert("RGB")
    return Image.open(source).convert("RGB")


def best_canvas_for(img: Image.Image) -> tuple[int, int]:
    src_ratio = img.width / img.height
    return min(CANVAS_CHOICES, key=lambda wh: abs((wh[0] / wh[1]) - src_ratio))


def fit_to_canvas(img: Image.Image, size=None) -> Image.Image:
    target_w, target_h = size or best_canvas_for(img)
    src_w, src_h = img.size
    scale = max(target_w / src_w, target_h / src_h)
    new_w, new_h = round(src_w * scale), round(src_h * scale)
    img = img.resize((new_w, new_h), Image.LANCZOS)
    left = (new_w - target_w) // 2
    top = (new_h - target_h) // 2
    return img.crop((left, top, left + target_w, top + target_h))


def wrap_text(draw, text, font, max_width):
    words = text.split()
    lines, current = [], ""
    for word in words:
        trial = f"{current} {word}".strip()
        if draw.textlength(trial, font=font) <= max_width:
            current = trial
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def draw_centered_text_block(draw, lines, font, canvas_width, y, fill, line_spacing, stroke_width, stroke_fill):
    ascent, descent = font.getmetrics()
    line_h = int((ascent + descent) * line_spacing)
    for i, line in enumerate(lines):
        w = draw.textlength(line, font=font)
        x = (canvas_width - w) / 2
        draw.text((x, y + i * line_h), line, font=font, fill=fill,
                   stroke_width=stroke_width, stroke_fill=stroke_fill)
    return y + len(lines) * line_h


def resolve_font(path_name: str, size: int) -> ImageFont.FreeTypeFont:
    path = FONT_DIR / path_name
    return ImageFont.truetype(str(path), size)


def compose_hero(image_source, title, font_style, out_path, config):
    base = fit_to_canvas(load_image(image_source))
    canvas = base.convert("RGBA")
    draw = ImageDraw.Draw(canvas)

    margin = 72
    content_width = base.width - 2 * margin

    fonts_cfg = config["fonts"]
    style = fonts_cfg["headline_styles"].get(font_style, fonts_cfg["headline_styles"]["default"])
    try:
        title_font = resolve_font(style["file"], style["size"])
    except OSError:
        title_font = resolve_font(fonts_cfg["fallback_font"], style["size"])

    title_lines = wrap_text(draw, title, title_font, content_width)
    ascent, descent = title_font.getmetrics()
    line_spacing = 1.3
    line_h = int((ascent + descent) * line_spacing)
    title_block_h = line_h * len(title_lines)

    start_y = (base.height - title_block_h) / 2

    draw_centered_text_block(draw, title_lines, title_font, base.width, start_y,
                              fill=(255, 255, 255, 255), line_spacing=line_spacing,
                              stroke_width=0, stroke_fill=None)

    canvas.convert("RGB").save(out_path, "JPEG", quality=92)
    return out_path


def compose_plain(image_source, out_path):
    base = fit_to_canvas(load_image(image_source))
    base.save(out_path, "JPEG", quality=92)
    return out_path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="mode", required=True)

    hero = sub.add_parser("hero")
    hero.add_argument("--image", required=True)
    hero.add_argument("--title", required=True)
    hero.add_argument("--font-style", default="default")
    hero.add_argument("--out", required=True)

    plain = sub.add_parser("plain")
    plain.add_argument("--image", required=True)
    plain.add_argument("--out", required=True)

    args = parser.parse_args()
    config = load_config()

    if args.mode == "hero":
        compose_hero(args.image, args.title, args.font_style, args.out, config)
    else:
        compose_plain(args.image, args.out)
    print(args.out)


if __name__ == "__main__":
    main()
