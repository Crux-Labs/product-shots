"""Turns product photos into flat textures. Pixels are only warped and cropped, never redrawn."""
import math
from pathlib import Path

import numpy as np
from PIL import Image


def rectify(photo: Path, corners: list[tuple[float, float]], out: Path, size: tuple[int, int]) -> Path:
    """Straightens one flat face. corners are the face's top-left, top-right, bottom-right, bottom-left in photo pixels."""
    tl, tr, br, bl = corners
    # PIL's QUAD takes the source corners in the order top-left, bottom-left, bottom-right, top-right.
    quad = (*tl, *bl, *br, *tr)
    face = Image.open(photo).convert("RGBA").transform(size, Image.QUAD, quad, Image.BICUBIC)
    out.parent.mkdir(parents=True, exist_ok=True)
    face.save(out)
    return out


def unwrap(photo: Path, box: tuple[int, int, int, int], out: Path, wrap_deg: float = 150, width: int | None = None) -> Path:
    """Unwraps the label of a round product seen straight from the front.

    box is the body's left, top, right, bottom edges in the photo. The middle wrap_deg of the visible half becomes a flat strip;
    use the same wrap_deg as side.wrap_deg in product.json. Near the silhouette the label is too foreshortened to keep, so
    stay at or under about 150.
    """
    img = np.asarray(Image.open(photo).convert("RGBA"))
    left, top, right, bottom = box
    cx, radius = (left + right) / 2, (right - left) / 2
    out_h = bottom - top
    out_w = width or round(radius * math.radians(wrap_deg))
    u = (np.arange(out_w) + 0.5) / out_w
    phi = np.radians((u - 0.5) * wrap_deg)
    xs = np.clip(cx + radius * np.sin(phi), 0, img.shape[1] - 1)
    x0 = np.floor(xs).astype(int)
    x1 = np.minimum(x0 + 1, img.shape[1] - 1)
    t = (xs - x0)[None, :, None]
    rows = img[top:bottom].astype(np.float64)
    strip = rows[:, x0] * (1 - t) + rows[:, x1] * t
    out.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(np.round(strip).astype(np.uint8)).save(out)
    return out
