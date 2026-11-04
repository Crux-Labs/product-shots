"""Draws the label art for the two made-up demo products, so the repo ships no real brand's artwork.

    python examples/make_kits.py

For a real product you put photos in products/<name>/kit/ instead; nothing here is needed.
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent


def font(size):
    return ImageFont.load_default(size=size)


def centred(draw, xy, text, size, fill):
    draw.text(xy, text, font=font(size), fill=fill, anchor="mm")


def tin():
    """Northfield Peppermints: a 70 mm round tin, red side band, cream lid with a mint leaf."""
    kit = HERE / "demo-tin" / "kit"
    kit.mkdir(parents=True, exist_ok=True)
    red, cream, green = (196, 42, 46), (246, 238, 222), (38, 120, 82)
    side = Image.new("RGB", (2200, 260), red)
    d = ImageDraw.Draw(side)
    d.rectangle([0, 18, 2200, 30], fill=cream)
    d.rectangle([0, 230, 2200, 242], fill=cream)
    centred(d, (1100, 130), "NORTHFIELD PEPPERMINTS", 78, cream)
    centred(d, (330, 130), "SUGAR FREE", 52, cream)
    centred(d, (1870, 130), "40 g", 52, cream)
    side.save(kit / "side.png")
    lid = Image.new("RGBA", (1200, 1200), (0, 0, 0, 0))
    d = ImageDraw.Draw(lid)
    d.ellipse([0, 0, 1199, 1199], fill=cream)
    d.ellipse([40, 40, 1159, 1159], outline=red, width=26)
    d.ellipse([450, 250, 750, 560], fill=green)
    d.line([600, 270, 600, 545], fill=cream, width=10)
    centred(d, (600, 690), "NORTHFIELD", 130, red)
    centred(d, (600, 830), "PEPPERMINTS", 84, green)
    centred(d, (600, 950), "est. 1931", 52, red)
    lid.save(kit / "top.png")


def box():
    """Kettle & Fern Green Tea: a 70 x 70 x 120 mm carton."""
    kit = HERE / "demo-box" / "kit"
    kit.mkdir(parents=True, exist_ok=True)
    green, ivory, gold = (44, 86, 64), (244, 240, 228), (196, 160, 82)

    def face(w, h, title, sub):
        im = Image.new("RGB", (w, h), green)
        d = ImageDraw.Draw(im)
        d.rectangle([24, 24, w - 24, h - 24], outline=gold, width=8)
        centred(d, (w // 2, h * 0.28), "KETTLE & FERN", int(w * 0.12), ivory)
        centred(d, (w // 2, h * 0.5), title, int(w * 0.16), gold)
        centred(d, (w // 2, h * 0.62), sub, int(w * 0.07), ivory)
        centred(d, (w // 2, h * 0.86), "20 tea bags · 40 g", int(w * 0.06), ivory)
        return im

    face(700, 1200, "GREEN TEA", "sencha & mint").save(kit / "front.png")
    face(700, 1200, "GREEN TEA", "steep 2-3 min at 80 °C").save(kit / "back.png")
    face(700, 1200, "SENCHA", "& garden mint").save(kit / "left.png")
    face(700, 1200, "SENCHA", "& garden mint").save(kit / "right.png")
    top = Image.new("RGB", (700, 700), green)
    centred(ImageDraw.Draw(top), (350, 350), "K&F", 160, gold)
    top.save(kit / "top.png")


if __name__ == "__main__":
    tin()
    box()
    print("demo kits written")
