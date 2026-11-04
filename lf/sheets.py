"""Check sheet: the model's renders beside the product photos, for a person (or Claude) to compare."""
from pathlib import Path

from PIL import Image, ImageDraw

PHOTO_TYPES = {".png", ".jpg", ".jpeg", ".webp"}


def _tile(path: Path, label: str, h: int) -> Image.Image:
    im = Image.open(path).convert("RGB")
    # Long label strips are capped in width so they don't stretch the sheet.
    s = min(h / im.height, 2.5 * h / im.width)
    im = im.resize((max(1, round(im.width * s)), max(1, round(im.height * s))), Image.LANCZOS)
    tile = Image.new("RGB", (im.width, h + 36), "white")
    tile.paste(im, (0, 36))
    ImageDraw.Draw(tile).text((8, 12), label, fill=(20, 20, 20))
    return tile


def _row(tiles: list[Image.Image], gap=12) -> Image.Image:
    w = sum(t.width for t in tiles) + gap * (len(tiles) - 1)
    row = Image.new("RGB", (max(w, 1), max(t.height for t in tiles)), "white")
    x = 0
    for t in tiles:
        row.paste(t, (x, 0))
        x += t.width + gap
    return row


def check_sheet(product_dir: Path, views: list[dict], out: Path, h: int = 420) -> Path:
    photos = sorted(p for p in (product_dir / "kit").glob("*") if p.suffix.lower() in PHOTO_TYPES)
    rows = [_row([_tile(Path(v["file"]), f"model · {v['view'].replace('_', ' ')}", h) for v in views])]
    if photos:
        rows.append(_row([_tile(p, f"photo · {p.name}", h) for p in photos[:4]]))
    sheet = Image.new("RGB", (max(r.width for r in rows) + 24, sum(r.height for r in rows) + 24 * len(rows) + 12), "white")
    y = 12
    for r in rows:
        sheet.paste(r, (12, y))
        y += r.height + 24
    out.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out, quality=88)
    return out
