"""Re-lights the product to match the repainted room, then puts it back exactly as before.

The repaint never decides a product pixel, so the product can be rendered again after it, under light read from the new room:
    1. a vision model reads the repaint's light (direction, height, colour, hardness, how open the shadows are);
    2. the repaint is wrapped round the scene as a blurred panorama, so the product reflects the room it sits in;
    3. Blender renders the product layer again with that light and world, same camera, same mask;
    4. the usual composite and pixel check run against the new layer, in out/relit/.
"""
import json
import shutil
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

from . import blender, composite
from .config import setting

# One light estimate with Gemini 3.1 Pro: about 1.5k tokens in, a few hundred out (thinking included), at list prices.
ESTIMATE_COST_USD = 0.01

LIGHT_PROMPT = """This is an advertising photograph. Describe its main light the way a lighting technician would, so a 3D product can be lit to match it.
- key_azimuth_deg: where the main light comes FROM, seen from the camera: 0 = from behind the camera (front light), -90 = from the left of the frame, 90 = from the right, 180 or -180 = from behind the subject (back light).
- key_elevation_deg: 0 = level with the subject, 90 = straight overhead.
- key_color: RGB of the main light, e.g. sunset [255, 190, 130], daylight [255, 248, 240], cool shade [210, 225, 255].
- key_hardness: 0 = very soft (overcast sky, big window), 1 = hard (direct sun, bare spotlight), judged from shadow edges.
- key_strength: the main light's brightness on the subject: 0.3 dim or moody, 1 a normal bright interior, 2 direct sun.
- ambient_color: RGB of the light filling the shadows.
- ambient_strength: 0 = deep black shadows, 1 = very open, bright shadows.
- exposure: the photo's overall brightness: -1 dark and moody, 0 normal, 0.5 bright and airy."""

LIGHT_SCHEMA = {
    "type": "object",
    "properties": {
        "key_azimuth_deg": {"type": "number"}, "key_elevation_deg": {"type": "number"},
        "key_color": {"type": "array", "items": {"type": "number"}}, "key_hardness": {"type": "number"},
        "key_strength": {"type": "number"}, "ambient_color": {"type": "array", "items": {"type": "number"}},
        "ambient_strength": {"type": "number"}, "exposure": {"type": "number"},
    },
    "required": ["key_azimuth_deg", "key_elevation_deg", "key_color", "key_hardness", "key_strength", "ambient_color", "ambient_strength", "exposure"],
}


def estimate_light(image: Path, model: str | None = None) -> dict:
    from google import genai
    from google.genai import types
    model = model or setting("SHOTS_LIGHT_MODEL") or "gemini-3.1-pro-preview"
    client = genai.Client(api_key=setting("GEMINI_API_KEY"))  # kept in a variable: a client collected mid-call closes its connection
    r = client.models.generate_content(
        model=model, contents=[Image.open(image).convert("RGB"), LIGHT_PROMPT],
        config=types.GenerateContentConfig(response_mime_type="application/json", response_schema=LIGHT_SCHEMA, temperature=0.2))
    return {"model": model, **json.loads(r.text)}


def _rgb(c) -> list[int]:
    c = list(c)[:3] + [255] * (3 - len(list(c)[:3]))
    return [int(min(255, max(0, v))) for v in c]


def light_spec(est: dict, base: dict) -> dict:
    """The estimate in ad.json light terms, around the bench's calibrated defaults (key_power 1, fill 0.35).

    Like a product photographer, keep the room's light on the side it comes from but never let it fall behind the product: a
    back-lit room still gets its key at most 75 degrees round from the camera, and the fill never drops so low that the label
    goes dark. The label has to read.
    """
    clamp = lambda v, lo, hi: min(hi, max(lo, float(v)))
    hard, amb = clamp(est["key_hardness"], 0, 1), clamp(est["ambient_strength"], 0, 1)
    return {**base, "key_azimuth_deg": clamp(est["key_azimuth_deg"], -75, 75), "key_elevation_deg": clamp(est["key_elevation_deg"], 5, 85),
            "key_color": _rgb(est["key_color"]), "key_size_m": round(1.4 - 1.2 * hard, 2), "key_power": clamp(est["key_strength"], 0.6, 1.6),
            "fill": round(0.22 + 0.25 * amb, 3), "fill_color": _rgb(est["ambient_color"])}


def panorama(image: Path, out: Path, width: int = 2048, blur: float = 18) -> Path:
    """An equirectangular world from one photo: the photo spans the half in front of the camera, its mirror the half behind,
    its top and bottom rows stretch up to the zenith and down to the floor, and the whole thing is blurred so reflections read
    as the room's colours and light, not as a second copy of it."""
    half = width // 2
    photo = np.asarray(Image.open(image).convert("RGB").resize((half, half // 2), Image.LANCZOS))
    front = photo  # Blender's equirect puts +Y (where the camera looks) at u = 0.75 and -Y (behind the camera) at u = 0.25.
    band = np.concatenate([front[:, ::-1], front], axis=1)
    rows = width // 2
    top = np.repeat(band[:1], (rows - band.shape[0]) // 2, axis=0)
    bottom = np.repeat(band[-1:], rows - band.shape[0] - top.shape[0], axis=0)
    pano = Image.fromarray(np.concatenate([top, band, bottom], axis=0)).filter(ImageFilter.GaussianBlur(blur))
    out.parent.mkdir(parents=True, exist_ok=True)
    pano.save(out)
    return out


def relight(ad_path: Path, light: dict | None = None) -> dict:
    """Needs a finished run in out/ (repaint.png and mask.png). Writes out/relit/ with layer, plate and the pixel check."""
    run = ad_path.resolve().parent / "out"
    rel = run / "relit"
    rel.mkdir(parents=True, exist_ok=True)
    est = light or estimate_light(run / "repaint.png")
    spec = blender.resolve_ad(ad_path)
    spec["light"] = light_spec(est, spec.get("light", {}))
    spec["environment"] = str(panorama(run / "repaint.png", rel / "environment.png"))
    spec["environment_strength"] = round(0.25 + 0.6 * min(1.0, max(0.0, float(est["ambient_strength"]))), 3)
    spec["render"] = {**spec.get("render", {}), "exposure": round(spec.get("render", {}).get("exposure", 0.0) + 0.5 * float(est["exposure"]), 2)}
    spec["layer_only"] = True
    info = blender.run(spec, rel, "relight")
    for f in ("mask.png", "repaint.png"):
        shutil.copy(run / f, rel / f)
    check = composite.composite(rel)
    result = {"light_estimate": est, "light": spec["light"], "environment_strength": spec["environment_strength"],
              "exposure": spec["render"]["exposure"], "blender": info, "verify": check["verify"]}
    (rel / "relight.json").write_text(json.dumps(result, indent=1, default=str))
    return result
