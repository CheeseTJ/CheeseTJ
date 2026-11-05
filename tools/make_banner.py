#!/usr/bin/env python3
"""Render an avatar into a green-phosphor CRT terminal banner (GitHub profile README style).

Usage: python3 tools/make_banner.py <avatar.(png|jpg)> <out.png>
"""
import random
import sys

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

FONT_MONO = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"

# ---- layout -----------------------------------------------------------------
W, H = 1200, 640
BG = (4, 10, 6)

P_X, P_Y = 26, 26          # portrait box origin
COLS, ROWS = 150, 82       # ascii grid
CW, CH = 4.5, 6.55         # cell size in px  -> 675 x 537
P_W, P_H = int(COLS * CW), int(ROWS * CH)

T_X = P_X + P_W + 34       # text column origin

RAMP = " ░▒▓█"            # dark -> bright (block ramp, CRT mosaic feel)

LINES = [
    ("Name:", ["JuneT"]),
    ("Born:", ["2002.06.09"]),
    ("Work:", ["Full-stack Developer"]),
    ("Langs:", ["Go, TypeScript,", "Vue, React, SQL"]),
    ("Focus:", ["Frontend, Backend"]),
    ("Status:", ["always building"]),
]

random.seed(7)


def green(level: float) -> tuple[int, int, int]:
    """Map 0..1 brightness onto a phosphor-green ramp."""
    level = max(0.0, min(1.0, level))
    r = 16 + 120 * level**1.8
    g = 40 + 215 * level**1.15
    b = 22 + 110 * level**1.6
    return (int(r), int(g), int(b))


def portrait_grid(src: Image.Image) -> list[list[float]]:
    g = ImageOps.grayscale(src)
    g = ImageOps.autocontrast(g, cutoff=1)
    # boost local structure so features survive downsampling
    g = g.filter(ImageFilter.UnsharpMask(radius=6, percent=180, threshold=2))
    g = g.resize((COLS, ROWS), Image.LANCZOS)
    g = ImageOps.autocontrast(g, cutoff=1)

    px = g.load()
    vals = [[px[x, y] / 255.0 for x in range(COLS)] for y in range(ROWS)]
    lo = min(map(min, vals))
    hi = max(map(max, vals))
    span = max(1e-6, hi - lo)

    out = []
    for row in vals:
        r = []
        for v in row:
            n = (v - lo) / span
            # S-curve: keep mid-tones bright enough to read as phosphor
            n = n * n * (3 - 2 * n) * 0.75 + n * 0.25
            r.append(n)
        out.append(r)
    return out


def draw_portrait(canvas: Image.Image, grid: list[list[float]]) -> None:
    layer = Image.new("RGB", (P_W, P_H), (0, 0, 0))
    d = ImageDraw.Draw(layer)
    f = ImageFont.truetype(FONT_MONO, 8)

    for y in range(ROWS):
        row = grid[y]
        for x in range(COLS):
            v = row[x]
            # ordered-ish dither keeps the ramp from banding into flat plateaus
            jitter = random.uniform(-0.045, 0.045)
            vv = max(0.0, min(1.0, v + jitter))
            idx = min(len(RAMP) - 1, int(vv * (len(RAMP) - 1) + 0.5))
            cx = x * CW
            cy = y * CH

            # phosphor floor: every cell glows a little, so the panel never looks empty
            floor = 0.08 + vv * 0.30
            d.rectangle([cx, cy, cx + CW - 0.4, cy + CH - 0.4], fill=green(floor))

            ch = RAMP[idx]
            if ch.strip():
                d.text(
                    (cx + CW / 2, cy + CH / 2),
                    ch,
                    font=f,
                    fill=green(0.55 + vv * 0.45),
                    anchor="mm",
                )

    # phosphor bloom
    glow = layer.filter(ImageFilter.GaussianBlur(5))
    glow = Image.eval(glow, lambda p: min(255, int(p * 0.85)))
    base = Image.new("RGB", (P_W, P_H), BG)
    merged = Image.blend(base, glow, 0.5)
    merged = Image.blend(merged, layer, 0.85)

    canvas.paste(merged, (P_X, P_Y))


def draw_scanlines(canvas: Image.Image, box) -> None:
    x0, y0, x1, y1 = box
    d = ImageDraw.Draw(canvas, "RGBA")
    for y in range(y0, y1, 3):
        d.line([(x0, y), (x1, y)], fill=(0, 0, 0, 90))
    # very slow horizontal hum bar, portrait only and barely there
    for i in range(18):
        a = int(9 * (1 - i / 18))
        y = y0 + int((y1 - y0) * 0.34) + i
        d.line([(x0, y), (x1 - 260, y)], fill=(120, 255, 150, a))


def draw_text(canvas: Image.Image) -> None:
    f = ImageFont.truetype(FONT_MONO, 21)
    lab_w = 118
    line_step = 27
    gap = 32

    # vertically balance the block inside the frame
    block_h = line_step * sum(len(v) for _, v in LINES) + gap * (len(LINES) - 1)
    y0 = P_Y + max(14, (P_H - block_h - 78) // 2)

    def walk(draw, mode: str) -> int:
        y = y0
        for label, values in LINES:
            draw.text((T_X, y), label, font=f, anchor="la",
                      fill=140 if mode == "glow" else green(0.62))
            for i, val in enumerate(values):
                draw.text((T_X + lab_w, y + i * line_step), val, font=f, anchor="la",
                          fill=255 if mode == "glow" else (205, 255, 212))
            y += line_step * len(values) + gap
        return y - gap

    # ---- pass 1: glow layer ----
    glow_layer = Image.new("L", canvas.size, 0)
    walk(ImageDraw.Draw(glow_layer), "glow")
    glow_layer = glow_layer.filter(ImageFilter.GaussianBlur(8))
    glow_rgb = Image.new("RGB", canvas.size, (0, 0, 0))
    glow_rgb.paste(Image.new("RGB", canvas.size, (60, 255, 120)), (0, 0), glow_layer)
    canvas.paste(glow_rgb, (0, 0), glow_layer.point(lambda p: int(p * 0.72)))

    # ---- pass 2: crisp text on top ----
    d = ImageDraw.Draw(canvas)
    end_y = walk(d, "crisp")

    # decorative brightness swatches, right under the text block
    sw_y = end_y + 46
    sw_x = T_X + lab_w
    for i in range(8):
        v = i / 7
        d.rectangle([sw_x + i * 30, sw_y, sw_x + i * 30 + 24, sw_y + 20],
                    fill=green(0.25 + v * 0.75))

    # blinking-cursor block at the end of the last line
    cy = end_y + 4
    d.rectangle([T_X + lab_w, cy, T_X + lab_w + 12, cy + 20], fill=green(0.95))


def vignette(canvas: Image.Image) -> None:
    mask = Image.new("L", (W, H), 0)
    md = ImageDraw.Draw(mask)
    md.ellipse([-W * 0.22, -H * 0.34, W * 1.22, H * 1.34], fill=255)
    mask = mask.filter(ImageFilter.GaussianBlur(120))
    dark = Image.new("RGB", (W, H), (0, 0, 0))
    canvas.paste(Image.composite(canvas, dark, mask), (0, 0))


def border(canvas: Image.Image) -> None:
    d = ImageDraw.Draw(canvas)
    d.rectangle([P_X - 8, P_Y - 8, P_X + P_W + 8, P_Y + P_H + 8], outline=green(0.28))
    d.rectangle([P_X - 6, P_Y - 6, W - 20, P_Y + P_H + 6], outline=green(0.16))


def main() -> None:
    src_path = sys.argv[1] if len(sys.argv) > 1 else "/tmp/avatar.png"
    out_path = sys.argv[2] if len(sys.argv) > 2 else "assets/banner.png"

    canvas = Image.new("RGB", (W, H), BG)
    src = Image.open(src_path)

    # square-crop, biased to the top so faces aren't cut, and trim the
    # bottom band (community watermarks sit there on most avatars)
    s = min(src.size)
    left = (src.width - s) // 2
    top = int((src.height - s) * 0.12)
    usable_h = int(s * 0.90)
    src = src.crop((left, top, left + s, top + usable_h))
    src = src.resize((s, s), Image.LANCZOS)

    draw_portrait(canvas, portrait_grid(src))
    draw_text(canvas)
    draw_scanlines(canvas, (P_X, P_Y, W - 16, P_Y + P_H))
    vignette(canvas)
    border(canvas)

    canvas.save(out_path)
    print(f"wrote {out_path} ({W}x{H})")


if __name__ == "__main__":
    main()
