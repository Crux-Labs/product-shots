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


def composite(run_dir: Path, shadow_reach_px: int = 120, shadow_gain: float = 1.0) -> dict:
    layer = np.asarray(Image.open(run_dir / "layer.png").convert("RGBA")).astype(np.float64) / 255
    mask = np.asarray(Image.open(run_dir / "mask.png").getchannel("A")).astype(np.float64) / 255
    H, W = mask.shape
    env = np.asarray(Image.open(run_dir / "repaint.png").convert("RGB").resize((W, H), Image.LANCZOS)).astype(np.float64) / 255
    out8, check = composite_arrays(env, layer, mask, shadow_reach_px, shadow_gain)
    Image.fromarray(out8).save(run_dir / "plate.png")
    check["verify"] = verify(run_dir / "plate.png", run_dir)
    (run_dir / "composite.json").write_text(json.dumps(check, indent=1))
    return check
