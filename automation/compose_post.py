#!/usr/bin/env python3
"""Compose a TikTok photo post: base image + theme title + movie list overlay.

Usage:
    python3 compose_post.py --image <path-or-url> --title "THEME" \
        --movies "Movie 1|Movie 2|Movie 3" --out /tmp/post.jpg
"""
import argparse
import io
import urllib.request
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

CANVAS_SIZE = (1080, 1920)
FONT_DIR = Path(__file__).parent / "fonts"
TITLE_FONT_PATH = FONT_DIR / "DejaVuSans-Bold.ttf"
MOVIE_FONT_PATH = FONT_DIR / "DejaVuSans-Bold.ttf"


def load_image(source: str) -> Image.Image:
    if source.startswith("http://") or source.startswith("https://"):
        with urllib.request.urlopen(source) as resp:
            data = resp.read()
        return Image.open(io.BytesIO(data)).convert("RGB")
    return Image.open(source).convert("RGB")


def fit_to_canvas(img: Image.Image, size=CANVAS_SIZE) -> Image.Image:
    target_w, target_h = size
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


def draw_text_block(draw, lines, font, x, y, fill, line_spacing, stroke_width, stroke_fill):
    ascent, descent = font.getmetrics()
    line_h = int((ascent + descent) * line_spacing)
    for i, line in enumerate(lines):
        draw.text((x, y + i * line_h), line, font=font, fill=fill,
                   stroke_width=stroke_width, stroke_fill=stroke_fill)
    return y + len(lines) * line_h


def build_bottom_gradient(width, height):
    gradient = Image.new("L", (1, height), color=0)
    for y in range(height):
        alpha = int(255 * (y / height) ** 1.4)
        gradient.putpixel((0, y), min(alpha, 235))
    gradient = gradient.resize((width, height))
    black = Image.new("RGBA", (width, height), (0, 0, 0, 255))
    black.putalpha(gradient)
    return black


def compose(image_source, title, movies, out_path):
    base = fit_to_canvas(load_image(image_source))

    grad_h = int(base.height * 0.62)
    shade = build_bottom_gradient(base.width, grad_h)

    canvas = base.convert("RGBA")
    canvas.paste(shade, (0, base.height - grad_h), shade)

    draw = ImageDraw.Draw(canvas)
    margin = 72
    content_width = base.width - 2 * margin

    title_font = ImageFont.truetype(str(TITLE_FONT_PATH), 70)
    movie_font = ImageFont.truetype(str(MOVIE_FONT_PATH), 52)

    title_lines = wrap_text(draw, title.upper(), title_font, content_width)
    movie_lines = [f"{i + 1}. {m}" for i, m in enumerate(movies)]

    t_ascent, t_descent = title_font.getmetrics()
    title_block_h = int((t_ascent + t_descent) * 1.2) * len(title_lines)
    m_ascent, m_descent = movie_font.getmetrics()
    movie_block_h = int((m_ascent + m_descent) * 1.35) * len(movie_lines)

    bottom_pad = 110
    total_h = title_block_h + 40 + movie_block_h
    start_y = base.height - bottom_pad - total_h

    y = draw_text_block(draw, title_lines, title_font, margin, start_y,
                         fill=(255, 255, 255, 255), line_spacing=1.2,
                         stroke_width=3, stroke_fill=(0, 0, 0, 255))
    y += 40
    draw_text_block(draw, movie_lines, movie_font, margin, y,
                     fill=(255, 214, 64, 255), line_spacing=1.35,
                     stroke_width=2, stroke_fill=(0, 0, 0, 255))

    canvas.convert("RGB").save(out_path, "JPEG", quality=92)
    return out_path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", required=True, help="Local path or URL of the base image")
    parser.add_argument("--title", required=True, help="Overlay headline (theme)")
    parser.add_argument("--movies", required=True, help="Movie titles separated by '|'")
    parser.add_argument("--out", required=True, help="Output JPEG path")
    args = parser.parse_args()

    movies = [m.strip() for m in args.movies.split("|") if m.strip()]
    compose(args.image, args.title, movies, args.out)
    print(args.out)


if __name__ == "__main__":
    main()
