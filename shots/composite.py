"""Puts the exact Blender product and its shadow back over the repainted room, and proves no model pixel survives inside it."""
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter


class ProductPixelsChanged(AssertionError):
    pass


def _lin(c):
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def _srgb(c):
    return np.where(c <= 0.0031308, c * 12.92, 1.055 * np.clip(c, 0, None) ** (1 / 2.4) - 0.055)


def _box(a: np.ndarray, r: int, axis: int) -> np.ndarray:
    pad = [(0, 0)] * a.ndim
    pad[axis] = (r + 1, r)
    c = np.cumsum(np.pad(a, pad, mode="edge"), axis=axis)
    return (np.take(c, range(2 * r + 1, c.shape[axis]), axis=axis) - np.take(c, range(0, c.shape[axis] - 2 * r - 1), axis=axis)) / (2 * r + 1)


def _blur(a: np.ndarray, sigma: float) -> np.ndarray:
    """Three box passes per axis, close to a Gaussian of this sigma."""
    r = max(1, int(round(sigma * 0.9)))
    for axis in (0, 1):
        for _ in range(3):
            a = _box(a, r, axis)
    return a


def deghost(env: np.ndarray, mask: np.ndarray, px: int, lighter_only: bool = True) -> np.ndarray:
    """Refills a thin ring round the product from the room just beyond it.

    The image model often redraws the product's edge a little bigger or lighter behind ours; after compositing that shows as a
    pale rim (judges call it a gold edge or a pasted-in look). The ring is outside the product, so this never touches a product
    pixel: it rebuilds the room there by averaging outward-in at growing blur sizes. With lighter_only, ring pixels directly under
    the product are replaced only where the model's version is lighter than the rebuilt room, so the contact shadow it painted
    there stays; to the sides and above, the whole ring is rebuilt (the ghost can be darker than a bright room).
    """
    hole = Image.fromarray(((mask > 0) * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(2 * px + 1))
    known = (np.asarray(hole) == 0).astype(np.float64)
    out = env.copy()
    filled = known.copy()
    for sigma in (2, 4, 8, 16, 32, 64):
        blur = lambda a: _blur(a, sigma)
        weight = blur(known)
        take = (filled == 0) & (weight > 1e-3)
        if not take.any():
            continue
        for c in range(3):
            out[..., c][take] = (blur(env[..., c] * known) / np.maximum(weight, 1e-9))[take]
        filled[take] = 1
    if lighter_only:
        lum = lambda a: a @ np.array([0.2126, 0.7152, 0.0722])
        product = mask > 0
        rows = np.arange(mask.shape[0])[:, None]
        bottom = np.where(product.any(0), np.where(product, rows, -1).max(0), mask.shape[0])
        under = rows >= bottom[None, :] - 3
        keep = under & (lum(env) <= lum(out) + 0.015)
        out[keep] = env[keep]
    return out


def composite_arrays(env: np.ndarray, layer: np.ndarray, mask: np.ndarray, shadow_reach_px: int = 120, shadow_gain: float = 1.0):
    """env RGB, layer RGBA (straight alpha) and mask, all float 0-1 at one size. Returns (uint8 RGB, check dict).

    Shadow alpha is kept only within shadow_reach_px of the product, so shadows of the rough CG set never land on the new room.
    The product is copied byte for byte where the mask is full; the 1-2 px anti-aliased edge blends like any cut-out.
    """
    prod = Image.fromarray(((mask > 4 / 255) * 255).astype(np.uint8))
    reach = max(1, shadow_reach_px)
    near = prod.filter(ImageFilter.MaxFilter(2 * (reach // 2) + 1)).filter(ImageFilter.GaussianBlur(reach / 3))
    near = np.maximum(np.asarray(near).astype(np.float64) / 255, mask)
    shadow = np.clip((layer[..., 3] - mask) * shadow_gain, 0, 1) * near
    a = np.clip(mask + shadow, 0, 1)[..., None]
    # Straight-alpha over in linear light: the shadow catcher's alpha is a linear transmittance; in sRGB shadows come out far too dark.
    rgb = _srgb(_lin(layer[..., :3]) * a + _lin(env) * (1 - a))
    out8 = np.round(np.clip(rgb, 0, 1) * 255).astype(np.uint8)
    inside = mask >= 1.0
    lay8 = np.round(layer[..., :3] * 255).astype(np.uint8)
    out8[inside] = lay8[inside]
    return out8, {"product_px": int(inside.sum()), "edge_px": int(((mask > 0) & ~inside).sum())}


def verify(image_path: Path, run_dir: Path) -> dict:
    """Reads a finished image back from disk and compares every full-mask pixel with the Blender product layer."""
    layer = np.asarray(Image.open(run_dir / "layer.png").convert("RGB"))
    inside = np.asarray(Image.open(run_dir / "mask.png").getchannel("A")) == 255
    img = np.asarray(Image.open(image_path).convert("RGB"))
    if img.shape != layer.shape:
        raise ProductPixelsChanged(f"{image_path} is {img.shape[1]}x{img.shape[0]}, the layout is {layer.shape[1]}x{layer.shape[0]}")
    diff = int(np.abs(img[inside].astype(int) - layer[inside].astype(int)).max()) if inside.any() else 0
    changed = int((np.abs(img[inside].astype(int) - layer[inside].astype(int)).max(axis=-1) > 0).sum()) if inside.any() else 0
    result = {"image": str(image_path), "product_px": int(inside.sum()), "changed_px": changed, "max_diff": diff, "pass": changed == 0}
    if changed:
        raise ProductPixelsChanged(f"{changed} product pixels differ from the Blender render: {result}")
    return result


def grain(run_dir: Path, amount: float, seed: int = 0) -> None:
    """Film grain on the Blender product layer, before compositing, so a clean render doesn't stand out in a photo.

    It's a fixed noise pattern added to the render (layer_raw.png keeps the original), not a model's drawing; the pixel check then
    compares the finished ad with this grained layer. amount is the noise's standard deviation in 0-255 levels.
    """
    raw = run_dir / "layer_raw.png"
    if not raw.exists():
        (run_dir / "layer.png").rename(raw)
    im = np.asarray(Image.open(raw).convert("RGBA")).astype(np.float64)
    noise = np.random.default_rng(seed).normal(0, amount, im.shape[:2])[..., None]
    im[..., :3] = np.clip(im[..., :3] + noise, 0, 255)
    Image.fromarray(np.round(im).astype(np.uint8)).save(run_dir / "layer.png")


def composite(run_dir: Path, shadow_reach_px: int = 120, shadow_gain: float = 1.0, deghost_px: int = 0) -> dict:
    layer = np.asarray(Image.open(run_dir / "layer.png").convert("RGBA")).astype(np.float64) / 255
    mask = np.asarray(Image.open(run_dir / "mask.png").getchannel("A")).astype(np.float64) / 255
    H, W = mask.shape
    env = np.asarray(Image.open(run_dir / "repaint.png").convert("RGB").resize((W, H), Image.LANCZOS)).astype(np.float64) / 255
    if deghost_px:
        env = deghost(env, mask, deghost_px)
    out8, check = composite_arrays(env, layer, mask, shadow_reach_px, shadow_gain)
    Image.fromarray(out8).save(run_dir / "plate.png")
    check["verify"] = verify(run_dir / "plate.png", run_dir)
    (run_dir / "composite.json").write_text(json.dumps(check, indent=1))
    return check
