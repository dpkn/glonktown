"""Draw the Glonktown home-screen icons (icon-180/192/512.png) into web/web."""
import os

from PIL import Image, ImageDraw, ImageFilter, ImageFont

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "web", "web")
FONT = "/System/Library/Fonts/Supplemental/Arial Rounded Bold.ttf"
SIZE = 1024
SKY_TOP, SKY_BOTTOM = (89, 166, 255), (28, 76, 196)
LETTER, OUTLINE, SHADOW = (255, 217, 38), (115, 56, 5), (10, 30, 90, 150)
CLOUDS = ((150, 200, 90), (250, 170, 110), (360, 210, 80), (700, 820, 100), (820, 790, 120), (930, 840, 90), (800, 120, 70), (880, 140, 60))


def sky():
    img = Image.new("RGB", (SIZE, SIZE))
    for y in range(SIZE):
        t = y / (SIZE - 1)
        img.paste(tuple(round(a + (b - a) * t) for a, b in zip(SKY_TOP, SKY_BOTTOM)), (0, y, SIZE, y + 1))
    clouds = Image.new("L", (SIZE, SIZE), 0)
    draw = ImageDraw.Draw(clouds)
    for cx, cy, r in CLOUDS:
        draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=70)
    img.paste((255, 255, 255), (0, 0), clouds.filter(ImageFilter.GaussianBlur(12)))
    return img.convert("RGBA")


def letter():
    font = ImageFont.truetype(FONT, 760)
    stroke = 40
    box = ImageDraw.Draw(Image.new("L", (1, 1))).textbbox((0, 0), "G", font=font, stroke_width=stroke)
    x = (SIZE - (box[2] - box[0])) / 2 - box[0]
    y = (SIZE - (box[3] - box[1])) / 2 - box[1] - 10
    shadow = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).text((x + 18, y + 26), "G", font=font, fill=SHADOW, stroke_width=stroke, stroke_fill=SHADOW)
    layer = shadow.filter(ImageFilter.GaussianBlur(10))
    ImageDraw.Draw(layer).text((x, y), "G", font=font, fill=LETTER, stroke_width=stroke, stroke_fill=OUTLINE)
    return layer


icon = Image.alpha_composite(sky(), letter()).convert("RGB")
for size in (180, 192, 512):
    icon.resize((size, size), Image.LANCZOS).save(os.path.join(OUT, "icon-%d.png" % size), optimize=True)
print("icons written to", os.path.normpath(OUT))
