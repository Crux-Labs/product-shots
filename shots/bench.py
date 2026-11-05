"""Benchmark: the same briefs made three ways, judged blind.

    full_model   the image model draws the whole ad, product included, from a reference photo (what this project avoids)
    blender      Blender alone: the layout render, product on a plain set
    layout_first Blender product + image-model room + exact product put back (this project)

    shots bench briefs <product> --n 100     write <product>/bench/briefs/NNN/{ad.json, brief.json}
    shots bench run <product>                make all three arms for every brief (resumable)
    shots bench judge <product>              blind-judge each brief's three images with Gemini (resumable)
    shots bench report <product> --out DIR   summary.json, report.md and example sheets
"""
import json
import random
import shutil
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from PIL import Image, ImageDraw

from . import blender, composite, prompt, repaint
from .config import find_product, setting

ARMS = ["full_model", "blender", "layout_first"]
ARM_NAMES = {"full_model": "Image model draws the ad", "blender": "Blender only", "layout_first": "Layout first"}
FORMATS = {"1:1": (1080, 1080), "4:5": (1080, 1350), "9:16": (1080, 1920)}
# (scene prompt, floor colour, wall colour or None, light side)
SCENES = [
    ("a sunlit stadium pitch with real green grass, a blurred stadium crowd and floodlights behind, golden evening sky", (70, 120, 50), (150, 160, 170), "right"),
    ("a wooden picnic table in a sunny park, blurred green trees behind, dappled summer light", (150, 110, 70), (120, 150, 100), "left"),
    ("a retro American diner counter with red vinyl stools and chrome trim blurred behind, warm interior light", (200, 200, 205), (190, 60, 60), "left"),
    ("a beach towel on golden sand, turquoise sea and bright sky behind, strong midday sun", (220, 200, 150), (140, 190, 220), "right"),
    ("a backyard barbecue table, grill smoke and string lights blurred behind, warm late-afternoon light", (130, 95, 65), (90, 80, 70), "left"),
    ("a warm oak kitchen counter, pale grey tiles behind, soft morning window light", (176, 128, 86), (214, 216, 212), "left"),
    ("a dark bar counter with blurred neon signs and bottles behind, moody night light", (60, 45, 40), (40, 40, 60), "right"),
    ("trampled grass at a summer music festival, blurred crowd and stage lights behind, hazy sunset", (90, 110, 60), (200, 150, 110), "right"),
    ("a stone ledge on a busy city street, blurred red double-decker buses and shopfronts behind, overcast daylight", (150, 150, 150), (170, 160, 150), "left"),
    ("a snowy wooden windowsill with frost on the glass and a blurred winter village behind, soft cool daylight", (230, 230, 235), (200, 210, 225), "left"),
    ("a tidy office desk next to a laptop and notebook, bright modern office blurred behind", (200, 190, 175), (225, 225, 225), "left"),
    ("the edge of a sunny swimming pool, blue water and palm shadows, bright summer light", (220, 215, 205), (100, 170, 210), "right"),
    ("a rooftop table at sunset, city skyline blurred behind, warm golden light", (120, 110, 105), (220, 150, 110), "right"),
    ("a coffee table in a living room on movie night, a bowl of popcorn and blurred TV glow behind, cosy warm lamp light", (110, 80, 60), (70, 70, 90), "left"),
    ("a white marble kitchen island, bright minimal kitchen behind, soft daylight", (235, 235, 235), (240, 240, 238), "left"),
    ("a gaming desk with RGB lights and a blurred monitor behind, dark room with colourful glow", (40, 40, 45), (40, 30, 70), "right"),
    ("the wooden floor of an indoor basketball court, blurred hoop and bleachers behind, arena light", (190, 140, 90), (110, 110, 120), "right"),
    ("a park bench in autumn, orange leaves on the ground and trees blurred behind, soft afternoon light", (150, 110, 70), (180, 120, 60), "left"),
    ("a camping table by a campfire at dusk, tent and pine trees blurred behind, warm firelight", (100, 80, 60), (50, 60, 70), "left"),
    ("a food-truck serving counter, colourful menu boards blurred behind, bright street light", (180, 180, 180), (220, 180, 70), "right"),
    ("a plain saturated red studio backdrop with a soft floor shadow, clean commercial studio light", (200, 20, 30), (200, 20, 30), "left"),
    ("a garden table with potted herbs and a sunny garden blurred behind, bright morning light", (170, 150, 120), (130, 170, 110), "right"),
    ("a beach bar counter made of bamboo, ocean and palm trees blurred behind, tropical sunset", (170, 130, 80), (230, 160, 100), "right"),
    ("a restaurant table next to a pepperoni pizza on a white plate, warm pizzeria blurred behind", (150, 100, 70), (120, 70, 50), "left"),
    ("a car's centre console cup area seen from the passenger seat, road trip landscape blurred through the windshield", (60, 60, 65), (180, 200, 220), "right"),
]
CAMERAS = {
    "eye level": {"height": 1.0, "dist": 1.0, "lens": 60},
    "low hero angle": {"height": 0.35, "dist": 0.9, "lens": 45},
    "high three-quarter view": {"height": 2.6, "dist": 1.0, "lens": 60},
}
CAMERA_PHRASES = {"eye level": "at eye level", "low hero angle": "from a low hero angle", "high three-quarter view": "from a high three-quarter view"}
ARRANGEMENTS = {"single": 1, "pair": 2, "trio": 3}


def _arrangement(n: int, rng: random.Random) -> list[dict]:
    spots = {1: [(0, 0)], 2: [(-40, 10), (40, -10)], 3: [(-70, 20), (0, -15), (70, 20)]}[n]
    return [{"position_mm": [x, y, 0], "rotation_deg": [0, 0, rng.uniform(-25, 25)]} for x, y in spots]


def make_briefs(product: str, n: int, seed: int = 7) -> Path:
    folder = find_product(product)
    spec = json.loads((folder / "product.json").read_text())
    height = max(z for _, z in spec["profile_mm"]) if "profile_mm" in spec else spec["dimensions_mm"]["height"]
    name = spec.get("display_name", spec["name"])
    rng = random.Random(seed)
    out = folder / "bench" / "briefs"
    out.mkdir(parents=True, exist_ok=True)
    for i in range(n):
        scene, floor, wall, side = SCENES[i % len(SCENES)]
        fmt = rng.choice(list(FORMATS))
        cam_name = rng.choice(list(CAMERAS))
        arr = rng.choice(list(ARRANGEMENTS))
        count = ARRANGEMENTS[arr]
        cam = CAMERAS[cam_name]
        spread = {1: 1.0, 2: 1.35, 3: 1.8}[count] * {"1:1": 1.1, "4:5": 0.95, "9:16": 0.8}[fmt]
        dist = height * 3.1 * spread * cam["dist"]
        items = [{"product": str(folder), **p} for p in _arrangement(count, rng)]
        ad = {
            "page": list(FORMATS[fmt]),
            "products": items,
            "camera": {"lens_mm": cam["lens"], "distance_mm": round(dist), "height_mm": round(height * 0.55 * cam["height"] + 20),
                       "azimuth_deg": rng.uniform(-12, 12), "target_mm": [0, 0, round(height * 0.5)]},
            "set": {"floor_color": list(floor), "wall": wall is not None, "wall_color": list(wall or (200, 200, 200)), "wall_distance_mm": 400},
            "light": {"key_azimuth_deg": -60 if side == "left" else 60, "key_elevation_deg": 35, "key_power": 1.0, "fill": 0.35, "ambient": 0.25},
            "render": {"samples": 64, "exposure": 0.0, "denoise": True},
            "scene_prompt": f"{scene}, calm uncluttered space at the top of the frame for a headline",
        }
        what = {1: f"One {name} standing upright", 2: f"Two {name}s standing upright side by side", 3: f"Three {name}s standing upright in a row"}[count]
        brief = {
            "id": f"{i:03d}", "scene": scene, "format": fmt, "camera": cam_name, "arrangement": arr,
            "text": f"{what}, seen {CAMERA_PHRASES[cam_name]}, on {scene}. Format {fmt}. Leave calm space at the top for a headline.",
            "full_model_prompt": (f"A photorealistic advertising photograph, {fmt} format. {what}, exactly the can shown in the reference image, "
                                  f"seen {CAMERA_PHRASES[cam_name]}, on {scene}. Keep the can's label, logo, lettering, colours and proportions exactly "
                                  f"as in the reference, at its real size. Calm space at the top of the frame for a headline. No added text, captions or watermark."),
        }
        d = out / brief["id"]
        d.mkdir(exist_ok=True)
        (d / "ad.json").write_text(json.dumps(ad, indent=1))
        (d / "brief.json").write_text(json.dumps(brief, indent=1))
    return out


def _briefs(product: str) -> list[Path]:
    return sorted(p for p in (find_product(product) / "bench" / "briefs").iterdir() if (p / "ad.json").exists())


def _record(d: Path, arm: str, data: dict, lock: threading.Lock):
    with lock:
        path = d / "arms.json"
        rec = json.loads(path.read_text()) if path.exists() else {}
        rec[arm] = data
        path.write_text(json.dumps(rec, indent=1, default=str))


def _done(d: Path, arm: str) -> bool:
    path = d / "arms.json"
    return path.exists() and json.loads(path.read_text()).get(arm, {}).get("ok", False)


def run(product: str, workers: int = 4, limit: int | None = None) -> dict:
    folder = find_product(product)
    spec = json.loads((folder / "product.json").read_text())
    refs = [folder / spec["reference_photo"]] if spec.get("reference_photo") else sorted((folder / "kit").glob("*.png"))[:1]
    briefs = _briefs(product)[:limit]
    lock = threading.Lock()
    pool = ThreadPoolExecutor(workers)

    def full_model(d):
        b = json.loads((d / "brief.json").read_text())
        size = tuple(json.loads((d / "ad.json").read_text())["page"])
        try:
            meta = repaint.generate_full(b["full_model_prompt"], refs, size, d / "full_model.png")
            _record(d, "full_model", {"ok": True, **meta}, lock)
        except Exception as e:  # one failed call shouldn't stop the batch
            _record(d, "full_model", {"ok": False, "error": repr(e)[:500]}, lock)

    def layout_first(d):
        ad = d / "ad.json"
        out = d / "out"
        try:
            ad_spec = json.loads(ad.read_text())
            names = [spec.get("display_name", spec["name"])] * len(ad_spec["products"])
            meta = repaint.repaint(out, prompt.build(ad_spec["scene_prompt"], names), "openai")
            check = composite.composite(out)
            shutil.copy(out / "plate.png", d / "layout_first.png")
            _record(d, "layout_first", {"ok": True, "cost_usd": meta["cost_usd"], "seconds": meta["seconds"], "verify": check["verify"]}, lock)
        except Exception as e:
            _record(d, "layout_first", {"ok": False, "error": repr(e)[:500]}, lock)

    futures = [pool.submit(full_model, d) for d in briefs if not _done(d, "full_model")]
    for d in briefs:  # Blender runs one job at a time on the GPU; image calls overlap with it
        if not _done(d, "blender"):
            t0 = time.time()
            try:
                info = blender.layout(d / "ad.json", d / "out")
                shutil.copy(d / "out" / "guide.png", d / "blender.png")
                _record(d, "blender", {"ok": True, "cost_usd": 0.0, "seconds": round(time.time() - t0, 1), "device": info.get("device")}, lock)
            except BaseException as e:
                _record(d, "blender", {"ok": False, "error": repr(e)[:500]}, lock)
                continue
        if not _done(d, "layout_first"):
            futures.append(pool.submit(layout_first, d))
    for f in futures:
        f.result()
    pool.shutdown()
    return {arm: sum(_done(d, arm) for d in briefs) for arm in ARMS} | {"briefs": len(briefs)}


JUDGE_PROMPT = """You are judging product advertising images for a brand, blind. The first image is a REAL photo of the product: the exact can the brand sells. Then come three candidate ads, labelled A, B and C, all made from the same brief:

BRIEF: {brief}

Score each candidate from 0 to 10 on:
- product_fidelity: is it exactly the product in the reference? Logo shape and spelling, every line of label text and marks, colours, proportions, and a believable real-world size in the scene. Any garbled, misspelt, missing or invented lettering or logo, or the wrong product, scores 3 or less.
- realism: does it look like a real photograph? Light, shadows, contact with the surface, perspective and depth all consistent; CG or pasted-in looks score low.
- brief_match: does it show what the brief asks (scene, number of cans, camera angle, space for a headline)?
- ad_appeal: would a brand's art director be pleased with it as a social ad?
Also give ship (true if you would run it for the brand as it is) and worst_issue (one short sentence, the most serious problem).
Finally rank the three from best to worst.

Look closely at the product lettering at full resolution before scoring product_fidelity. Judge only what you see."""

JUDGE_SCHEMA = {
    "type": "object",
    "properties": {
        "candidates": {"type": "object", "properties": {k: {"type": "object", "properties": {
            "product_fidelity": {"type": "number"}, "realism": {"type": "number"}, "brief_match": {"type": "number"},
            "ad_appeal": {"type": "number"}, "ship": {"type": "boolean"}, "worst_issue": {"type": "string"}},
            "required": ["product_fidelity", "realism", "brief_match", "ad_appeal", "ship", "worst_issue"]} for k in "ABC"},
            "required": list("ABC")},
        "ranking": {"type": "array", "items": {"type": "string", "enum": list("ABC")}},
    },
    "required": ["candidates", "ranking"],
}


def judge(product: str, workers: int = 4, model: str | None = None) -> dict:
    from google import genai
    from google.genai import types
    model = model or setting("SHOTS_JUDGE_MODEL") or "gemini-3.1-pro-preview"
    folder = find_product(product)
    spec = json.loads((folder / "product.json").read_text())
    ref = Image.open(folder / spec["reference_photo"]).convert("RGB")
    client = genai.Client(api_key=setting("GEMINI_API_KEY"))

    def one(d: Path):
        if (d / "judge.json").exists():
            return
        if not all((d / f"{a}.png").exists() for a in ARMS):
            return
        order = ARMS[:]
        random.Random(int(d.name)).shuffle(order)  # fixed per brief, different across briefs
        key = dict(zip("ABC", order))
        brief = json.loads((d / "brief.json").read_text())
        contents = [ref] + [x for label, arm in key.items() for x in (f"Candidate {label}:", Image.open(d / f"{arm}.png").convert("RGB"))]
        contents.append(JUDGE_PROMPT.format(brief=brief["text"]))
        for attempt in range(3):
            try:
                r = client.models.generate_content(model=model, contents=contents, config=types.GenerateContentConfig(
                    response_mime_type="application/json", response_schema=JUDGE_SCHEMA, temperature=0.2))
                data = json.loads(r.text)
                result = {"model": model, "key": key, "raw": data,
                          "arms": {arm: {**data["candidates"][label], "rank": data["ranking"].index(label) + 1} for label, arm in key.items()}}
                (d / "judge.json").write_text(json.dumps(result, indent=1))
                return
            except Exception as e:
                err = repr(e)[:300]
                time.sleep(5 * (attempt + 1))
        (d / "judge_error.txt").write_text(err)

    with ThreadPoolExecutor(workers) as pool:
        list(pool.map(one, _briefs(product)))
    return {"judged": sum((d / "judge.json").exists() for d in _briefs(product))}


def _sheet(d: Path, judged: dict, out: Path, h: int = 520):
    tiles = []
    for arm in ARMS:
        im = Image.open(d / f"{arm}.png").convert("RGB")
        im = im.resize((round(im.width * h / im.height), h), Image.LANCZOS)
        j = judged["arms"][arm]
        tile = Image.new("RGB", (im.width, h + 64), "white")
        tile.paste(im, (0, 64))
        draw = ImageDraw.Draw(tile)
        draw.text((6, 6), f"{ARM_NAMES[arm]}  ·  rank {j['rank']}  ·  {'ship' if j['ship'] else 'no ship'}", fill=(0, 0, 0))
        draw.text((6, 26), f"product {j['product_fidelity']:g} · real {j['realism']:g} · brief {j['brief_match']:g} · appeal {j['ad_appeal']:g}", fill=(60, 60, 60))
        tiles.append(tile)
    sheet = Image.new("RGB", (sum(t.width for t in tiles) + 20 * (len(tiles) - 1), h + 64), "white")
    x = 0
    for t in tiles:
        sheet.paste(t, (x, 0))
        x += t.width + 20
    out.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out, quality=82)


def report(product: str, out_dir: Path, examples: int = 6) -> dict:
    rows = []
    for d in _briefs(product):
        if (d / "judge.json").exists():
            rows.append((d, json.loads((d / "judge.json").read_text()), json.loads((d / "arms.json").read_text())))
    n = len(rows)
    dims = ["product_fidelity", "realism", "brief_match", "ad_appeal"]
    summary = {"briefs_judged": n, "arms": {}}
    for arm in ARMS:
        js = [j["arms"][arm] for _, j, _ in rows]
        costs = [a[arm].get("cost_usd", 0) for _, _, a in rows]
        secs = [a[arm].get("seconds", 0) for _, _, a in rows]
        summary["arms"][arm] = {
            **{k: round(sum(x[k] for x in js) / n, 2) for k in dims},
            "overall": round(sum(sum(x[k] for k in dims) / 4 for x in js) / n, 2),
            "ship_rate": round(sum(x["ship"] for x in js) / n, 3),
            "win_rate": round(sum(x["rank"] == 1 for x in js) / n, 3),
            "low_product_fidelity_rate": round(sum(x["product_fidelity"] <= 3 for x in js) / n, 3),
            "mean_cost_usd": round(sum(costs) / n, 4), "mean_seconds": round(sum(secs) / n, 1),
        }
    lf = [a["layout_first"]["verify"] for _, _, a in rows]
    summary["layout_first_pixel_check"] = {"passed": sum(v["pass"] for v in lf), "of": len(lf)}
    out_dir.mkdir(parents=True, exist_ok=True)
    img_dir = out_dir / "examples"
    picks = []
    by_win = {arm: [r for r in rows if r[1]["arms"][arm]["rank"] == 1] for arm in ARMS}
    for arm in ARMS:
        picks += by_win[arm][: max(1, examples // 3)]
    fails = sorted(rows, key=lambda r: r[1]["arms"]["full_model"]["product_fidelity"])[:2]
    picks += [r for r in fails if r not in picks]
    for d, j, _ in picks:
        _sheet(d, j, img_dir / f"brief_{d.name}.jpg")
    summary["examples"] = [{"brief": d.name, "text": json.loads((d / "brief.json").read_text())["text"], "file": f"examples/brief_{d.name}.jpg",
                            "issues": {arm: j["arms"][arm]["worst_issue"] for arm in ARMS}} for d, j, _ in picks]
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=1))
    return summary
