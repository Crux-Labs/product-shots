"""One image-model edit: repaint everything outside the product mask as a real photo.

Whatever the model returns inside the product is thrown away by composite.py, so the model never decides a product pixel.
"""
import base64
import io
import json
import time
from pathlib import Path

from PIL import Image, ImageFilter

from .config import setting

# List prices per million tokens (text in, image in, image out), used for the cost estimate in run.json.
PRICES = {"openai": (5.0, 8.0, 30.0), "gemini": (2.0, 2.0, 120.0)}
DEFAULT_MODELS = {"openai": "gpt-image-2.5-sunburst", "gemini": "gemini-3-pro-image-preview"}
GEMINI_RATIOS = {"9:16": 9 / 16, "4:5": 0.8, "1:1": 1.0, "16:9": 16 / 9, "3:2": 1.5, "2:3": 2 / 3, "3:4": 0.75, "4:3": 4 / 3, "21:9": 21 / 9, "5:4": 1.25}


def provider_and_model(provider: str | None) -> tuple[str, str]:
    provider = provider or setting("SHOTS_PROVIDER") or ("openai" if setting("OPENAI_API_KEY") else "gemini")
    if provider not in DEFAULT_MODELS:
        raise SystemExit(f"unknown provider {provider!r}; use openai or gemini")
    key = "OPENAI_API_KEY" if provider == "openai" else "GEMINI_API_KEY"
    if not setting(key):
        raise SystemExit(f"{key} is not set. Add it to .env (run /setup).")
    return provider, setting(f"SHOTS_{provider.upper()}_MODEL") or DEFAULT_MODELS[provider]


def openai_size(w: int, h: int) -> str:
    """Largest size near the page aspect that GPT Image takes: edges a multiple of 16, long edge at most 2048."""
    scale = 2048 / max(w, h)
    return f"{int(w * scale) // 16 * 16}x{int(h * scale) // 16 * 16}"


def _png(im: Image.Image) -> io.BytesIO:
    b = io.BytesIO()
    im.save(b, "PNG")
    b.seek(0)
    b.name = "image.png"
    return b


def _openai(model, guide, mask_alpha, prompt):
    from openai import OpenAI
    size = openai_size(*guide.size)
    sw, sh = map(int, size.split("x"))
    # Edit mask: transparent may change; the product, grown about 6 px, stays opaque.
    a = mask_alpha.resize((sw, sh), Image.LANCZOS).point(lambda v: 255 if v > 8 else 0).filter(ImageFilter.MaxFilter(13))
    m = Image.new("RGBA", (sw, sh), (0, 0, 0, 0))
    m.putalpha(a)
    r = OpenAI().images.edit(model=model, image=_png(guide.resize((sw, sh), Image.LANCZOS)), mask=_png(m), prompt=prompt, size=size, quality="high", n=1)
    out = Image.open(io.BytesIO(base64.b64decode(r.data[0].b64_json))).convert("RGB")
    u = r.usage.model_dump() if r.usage else {}
    det = u.get("input_tokens_details") or {}
    p = PRICES["openai"]
    cost = (det.get("text_tokens", 0) * p[0] + det.get("image_tokens", 0) * p[1] + u.get("output_tokens", 0) * p[2]) / 1e6
    return out, {"size": size, "usage": u}, cost


def _gemini(model, guide, prompt):
    from google import genai
    from google.genai import types
    w, h = guide.size
    ratio = min(GEMINI_RATIOS, key=lambda k: abs(GEMINI_RATIOS[k] - w / h))
    cfg = types.GenerateContentConfig(response_modalities=["IMAGE", "TEXT"], image_config=types.ImageConfig(aspect_ratio=ratio, image_size="2K"))
    r = genai.Client(api_key=setting("GEMINI_API_KEY")).models.generate_content(model=model, contents=[guide, prompt], config=cfg)
    out = next((Image.open(io.BytesIO(p.inline_data.data)).convert("RGB") for p in r.candidates[0].content.parts
                if getattr(p, "inline_data", None) and p.inline_data.data), None)
    if out is None:
        raise SystemExit("Gemini returned no image; try again or switch provider.")
    um = r.usage_metadata
    p = PRICES["gemini"]
    cost = ((um.prompt_token_count or 0) * p[0] + (um.candidates_token_count or 0) * p[2]) / 1e6
    return out, {"aspect_ratio": ratio, "usage": {"input_tokens": um.prompt_token_count, "output_tokens": um.candidates_token_count}}, cost


def repaint(run_dir: Path, prompt: str, provider: str | None = None) -> dict:
    provider, model = provider_and_model(provider)
    guide = Image.open(run_dir / "guide.png").convert("RGB")
    mask_alpha = Image.open(run_dir / "mask.png").getchannel("A")
    t0 = time.time()
    if provider == "openai":
        out, extra, cost = _openai(model, guide, mask_alpha, prompt)
    else:
        out, extra, cost = _gemini(model, guide, prompt)
    # Back to the page grid: scale to cover, centre crop, so the model's framing lines up with the guide.
    W, H = guide.size
    s = max(W / out.width, H / out.height)
    out = out.resize((round(out.width * s), round(out.height * s)), Image.LANCZOS)
    l, t = (out.width - W) // 2, (out.height - H) // 2
    out.crop((l, t, l + W, t + H)).save(run_dir / "repaint.png")
    meta = {"provider": provider, "model": model, "prompt": prompt, "cost_usd": round(cost, 4), "seconds": round(time.time() - t0, 1), **extra}
    (run_dir / "repaint.json").write_text(json.dumps(meta, indent=1, default=str))
    return meta
