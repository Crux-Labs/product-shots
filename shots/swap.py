"""Model first, exact product swapped in: start from an ad the image model drew, put our exact product where it put its own.

    1. find:    a vision model marks each product in the ad: which side faces the camera and the four corners of that face;
    2. pose:    the corners and the face's real size give each product's position and angle, and the camera's focal length;
    3. render:  Blender renders our product at those poses (layer and mask, same page size);
    4. rebuild: whatever of the model's product ours doesn't cover is repainted as background (an image-model edit outside our mask);
    5. composite and the usual pixel check.

The model's drawing decides where the product stands and how the room meets it; every product pixel still comes from the 3D model.
"""
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

from .config import setting

FIND_PROMPT = """This advert shows {count} {noun}(s): {name}. The reference image shows the real product.{note}
For each {noun} in the advert, from left to right, give:
- side: which face of the product faces the camera: {sides}. Decide by matching the face's printed design to the reference.
- corners: the four corners of that face in the advert, as [x, y] on a 0-1000 scale (0, 0 top-left of the image, 1000, 1000 bottom-right), in this order: the face's own top-left, top-right, bottom-right, bottom-left (top meaning the top of its printed design, left as you look at that face).{cylinder}
- box: [x_min, y_min, x_max, y_max] of the whole product on the same 0-1000 scale, including any part drawn wrongly.
Be precise: corners within a few pixels."""

CYLINDER_NOTE = """ For a round product, use the label's visible front: its left and right edges where the label meets the top band, and where it meets the bottom band."""

FIND_SCHEMA = {
    "type": "object",
    "properties": {"products": {"type": "array", "items": {"type": "object", "properties": {
        "side": {"type": "string"},
        "corners": {"type": "array", "items": {"type": "array", "items": {"type": "number"}}},
        "box": {"type": "array", "items": {"type": "number"}}},
        "required": ["side", "corners", "box"]}}},
    "required": ["products"],
}


def find(image: Path, reference: Path, spec: dict, count: int, model: str | None = None) -> list[dict]:
    from google import genai
    from google.genai import types
    model = model or setting("SHOTS_JUDGE_MODEL") or "gemini-3.1-pro-preview"
    im = Image.open(image).convert("RGB")
    cfg = spec.get("bench", {})
    sides = {"slab": '"front" or "back"', "box": '"front", "back", "left" or "right" (the widest visible printed face)'}.get(spec["template"], '"front"')
    note = f" {cfg['reference_note']}" if cfg.get("reference_note") else ""
    text = FIND_PROMPT.format(note=note, count=count, noun=cfg.get("noun", "product"), name=spec.get("display_name", spec["name"]), sides=sides,
                              cylinder=CYLINDER_NOTE if spec["template"] == "cylinder" else "")
    client = genai.Client(api_key=setting("GEMINI_API_KEY"))
    r = client.models.generate_content(model=model, contents=[Image.open(reference).convert("RGB"), im, text],
                                       config=types.GenerateContentConfig(response_mime_type="application/json", response_schema=FIND_SCHEMA, temperature=0.1))
    found = json.loads(r.text)["products"]
    sx, sy = im.width / 1000, im.height / 1000
    for f in found:  # to pixels
        f["corners"] = [[x * sx, y * sy] for x, y in f["corners"]]
        f["box"] = [f["box"][0] * sx, f["box"][1] * sy, f["box"][2] * sx, f["box"][3] * sy]
    return found


def upright(corners: list) -> list:
    """Top-left, top-right, bottom-right, bottom-left as they sit in the image. Products in ads stand upright, and a face the
    camera sees is never mirrored, so image position is more reliable than a model's labels (it mixes up a back face's left)."""
    pts = sorted(corners, key=lambda c: c[1])
    top, bottom = sorted(pts[:2], key=lambda c: c[0]), sorted(pts[2:], key=lambda c: c[0])
    return [top[0], top[1], bottom[1], bottom[0]]


def face_rect(spec: dict, side: str) -> tuple[np.ndarray, np.ndarray, float, float]:
    """The face that faces the camera, in product coordinates (mm, base centre at 0, front towards -Y): its centre, its in-plane
    axes (u to the right and v up, as you look at that face) and its width and height."""
    if spec["template"] == "cylinder":
        prof = spec.get("profile_mm") or [[spec["dimensions_mm"]["diameter"] / 2, 0], [spec["dimensions_mm"]["diameter"] / 2, spec["dimensions_mm"]["height"]]]
        r = max(p[0] for p in prof)
        side_spec = spec.get("side", {})
        z0, z1 = side_spec.get("z_from_mm", prof[0][1]), side_spec.get("z_to_mm", prof[-1][1])
        return np.array([0, 0, (z0 + z1) / 2]), np.array([[1, 0, 0], [0, 0, 1]]), 2 * r, z1 - z0
    d = spec["dimensions_mm"]
    w, h, t = d["width"], d["height"], d["depth"]
    if side == "back":
        return np.array([0, t / 2, h / 2]), np.array([[-1, 0, 0], [0, 0, 1]]), w, h
    if side == "left":
        return np.array([-w / 2, 0, h / 2]), np.array([[0, -1, 0], [0, 0, 1]]), t, h
    if side == "right":
        return np.array([w / 2, 0, h / 2]), np.array([[0, 1, 0], [0, 0, 1]]), t, h
    return np.array([0, -t / 2, h / 2]), np.array([[1, 0, 0], [0, 0, 1]]), w, h


def homography(src: np.ndarray, dst: np.ndarray) -> np.ndarray:
    """3x3 H with dst ~ H src, from four point pairs (direct linear transform)."""
    rows = []
    for (x, y), (u, v) in zip(src, dst):
        rows.append([-x, -y, -1, 0, 0, 0, u * x, u * y, u])
        rows.append([0, 0, 0, -x, -y, -1, v * x, v * y, v])
    H = np.linalg.svd(np.array(rows))[2][-1].reshape(3, 3)
    return H / H[2, 2]


def focal_from(H: np.ndarray, size: tuple[int, int]) -> float | None:
    """Focal length in pixels from one plane's homography, principal point at the centre (Zhang's two constraints)."""
    cx, cy = size[0] / 2, size[1] / 2
    Hc = np.array([[1, 0, -cx], [0, 1, -cy], [0, 0, 1]]) @ H
    (a1, a2), (b1, b2), (c1, c2) = Hc[0, :2], Hc[1, :2], Hc[2, :2]
    guesses = []
    if abs(c1 * c2) > 1e-12:
        guesses.append(-(a1 * a2 + b1 * b2) / (c1 * c2))
    if abs(c2 * c2 - c1 * c1) > 1e-12:
        guesses.append((a1 * a1 + b1 * b1 - a2 * a2 - b2 * b2) / (c2 * c2 - c1 * c1))
    good = [g for g in guesses if g > 0]
    return float(np.sqrt(np.median(good))) if good else None


def pose(corners: list, spec: dict, side: str, f: float, size: tuple[int, int]) -> np.ndarray:
    """4x4 product-to-camera transform (OpenCV camera: x right, y down, z forward; mm) from the face's four image corners."""
    centre, (u, v), fw, fh = face_rect(spec, side)
    plane = np.array([[-fw / 2, fh / 2], [fw / 2, fh / 2], [fw / 2, -fh / 2], [-fw / 2, -fh / 2]])  # TL, TR, BR, BL in (u, v)
    H = homography(plane, np.array(corners, dtype=float))
    K = np.array([[f, 0, size[0] / 2], [0, f, size[1] / 2], [0, 0, 1]])
    B = np.linalg.inv(K) @ H
    lam = 2 / (np.linalg.norm(B[:, 0]) + np.linalg.norm(B[:, 1]))
    if (lam * B[:, 2])[2] < 0:
        lam = -lam
    r1, r2, t = lam * B[:, 0], lam * B[:, 1], lam * B[:, 2]
    U, _, Vt = np.linalg.svd(np.stack([r1, r2, np.cross(r1, r2)], axis=1))
    R_face = U @ Vt  # columns: the face's u, v and normal, in camera coordinates
    # Product axes in camera coordinates: u and v are known product directions, so solve R with R @ [u, v, u x v] = R_face.
    P = np.stack([u, v, np.cross(u, v)], axis=1)
    R = R_face @ P.T
    T = np.eye(4)
    T[:3, :3], T[:3, 3] = R, t - R @ centre
    return T


REBUILD_PROMPT = """This advert photo has a product in it that must stay exactly as it is. In the masked area round it are leftovers of a slightly different, earlier version of the product (a wider outline, a lid or edge that doesn't belong, a second copy). Remove every leftover: continue the surface, background and props naturally through the masked area, keeping a soft, natural contact shadow under the product where it touches the surface. If the surface is glossy, leave only a soft, blurred hint of reflection with no readable text or logo in it. Do not draw any product, packaging, label, logo or text. Keep the light, colours and focus of the photo. No watermark."""


def render_spec(found: list[dict], poses: list[np.ndarray], f: float, size: tuple[int, int], product: dict, exposure: float = 0.0,
                environment: str | None = None) -> dict:
    """A Blender layout spec that puts our product at each measured pose. The world is the first product's own frame, so its base
    sits on the floor at z = 0 and the usual studio light falls on it from the front left."""
    flip = np.diag([1.0, -1.0, -1.0, 1.0])  # OpenCV camera axes to Blender's (y up, looking down -z)
    to_m = lambda T: np.vstack([np.hstack([T[:3, :3], T[:3, 3:] / 1000]), [0, 0, 0, 1]])
    world_from_cam = np.linalg.inv(to_m(poses[0]))
    items = [{"product": product, "matrix": (world_from_cam @ to_m(T)).tolist()} for T in poses]
    # The studio key sits 55 degrees to the camera's left, wherever the camera is (a back view must not be lit from behind).
    cx, cy = world_from_cam[0, 3], world_from_cam[1, 3]
    camera_az = float(np.degrees(np.arctan2(cx, -cy)))
    return {"mode": "layout", "page": list(size), "products": items, "no_guide": True,
            "camera": {"matrix": (world_from_cam @ flip).tolist(), "lens_mm": f * 36 / max(size)},
            "set": {"floor": False}, "light": {"key_azimuth_deg": camera_az - 55, "key_elevation_deg": 35, "fill": 0.35, "ambient": 0.25},
            "render": {"samples": 64, "exposure": exposure, "denoise": True},
            # The photo itself, wrapped round as a blurred world: metal and gloss reflect the room the product stands in.
            **({"environment": environment, "environment_strength": 0.5} if environment else {})}


def rebuild_region(found: list[dict], mask: np.ndarray, grow: float = 0.06, below: float = 0.3) -> np.ndarray:
    """Where the model's own product may still show: each product's box, grown a little (and further down, where a glossy surface
    reflects it), minus our product."""
    H, W = mask.shape
    region = np.zeros((H, W), bool)
    for f in found:
        x0, y0, x1, y1 = f["box"]
        gx, gy = (x1 - x0) * grow, (y1 - y0) * grow
        region[max(0, int(y0 - gy)):min(H, int(y1 + (y1 - y0) * below)), max(0, int(x0 - gx)):min(W, int(x1 + gx))] = True
    return region & (mask < 255)


def swap(brief_dir: Path, product_name: str) -> dict:
    """brief_dir has full_model.png and ad.json. Writes brief_dir/swap/out/ and returns the pixel check."""
    import shutil
    import time
    from . import blender, composite, repaint
    from .config import find_product
    folder = find_product(product_name)
    spec = json.loads((folder / "product.json").read_text())
    out = brief_dir / "swap" / "out"
    out.mkdir(parents=True, exist_ok=True)
    base = Image.open(brief_dir / "full_model.png").convert("RGB")
    size = base.size
    t0 = time.time()
    count = len(json.loads((brief_dir / "ad.json").read_text())["products"])
    found_path = out / "find.json"
    found = json.loads(found_path.read_text()) if found_path.exists() else find(brief_dir / "full_model.png", folder / spec["reference_photo"], spec, count)
    for p in found:
        p["corners"] = upright(p["corners"])
    found_path.write_text(json.dumps(found, indent=1))
    # One focal length for the whole photo: the median of what each product's face says, else a 50 mm lens.
    fs = [focal_from(homography(np.array([[-1, 1], [1, 1], [1, -1], [-1, -1]]) * np.array(face_rect(spec, f["side"])[2:]) / 2,
                                np.array(f["corners"], float)), size) for f in found]
    fs = [x for x in fs if x and 0.3 * max(size) < x < 6 * max(size)]
    f = float(np.median(fs)) if fs else 50 / 36 * max(size)
    poses = [pose(p["corners"], spec, p["side"], f, size) for p in found]
    product = blender.load_product(str(folder))
    from .relight import panorama
    env = str(panorama(brief_dir / "full_model.png", out / "environment.png"))
    info = blender.run(render_spec(found, poses, f, size, product, spec.get("bench", {}).get("exposure", 0.0), env), out, "swap")
    mask = np.asarray(Image.open(out / "mask.png").getchannel("A"))
    layer = Image.open(out / "layer.png").convert("RGBA")
    # Rebuild what's left of the model's product, with ours already in place so the room is continued round it.
    region = rebuild_region(found, mask)
    shown = base.copy()
    shown.paste(layer.convert("RGB"), (0, 0), Image.fromarray(mask))
    shown.save(out / "guide.png")
    keep = Image.fromarray(np.where(region, 0, 255).astype(np.uint8))
    keep.save(out / "rebuild_keep.png")
    # The rebuild only depends on where our product sits; a rerun with the same poses reuses it.
    meta = {"cost_usd": 0.0} if (out / "edited.png").exists() else repaint.edit(shown, keep, REBUILD_PROMPT, out / "edited.png")
    edited = np.asarray(Image.open(out / "edited.png").convert("RGB"), dtype=np.float64)
    soft = np.asarray(Image.fromarray((region * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(2)), dtype=np.float64)[..., None] / 255
    room = np.asarray(base, dtype=np.float64) * (1 - soft) + edited * soft
    Image.fromarray(np.round(room).astype(np.uint8)).save(out / "repaint.png")
    check = composite.composite(out, shadow_gain=0.0)
    shutil.copy(out / "plate.png", brief_dir / "swap.png")
    result = {"focal_px": f, "found": found, "verify": check["verify"], "cost_usd": round(meta["cost_usd"] + 0.01, 4),
              "seconds": round(time.time() - t0, 1), "blender": info}
    (out / "swap.json").write_text(json.dumps(result, indent=1, default=str))
    return result
