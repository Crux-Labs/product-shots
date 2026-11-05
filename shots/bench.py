"""Benchmark: the same briefs made three ways, judged blind.

    full_model   the image model draws the whole ad, product included, from a reference photo (what this project avoids)
    blender      Blender alone: the layout render, product on a plain set
    layout_first Blender product + image-model room + exact product put back (this project)

    shots bench briefs <product> --n 100     write <product>/bench/briefs/NNN/{ad.json, brief.json}
    shots bench run <product>                make all three arms for every brief (resumable)
    shots bench relight <product>            a fourth arm, relit: layout first with the product re-lit from its repaint
    shots bench judge <product> --arms full_model,layout_first,relit --tag relit    judge any three arms, kept apart by tag
    shots bench judge <product>              blind-judge each brief's three images with Gemini (resumable)
    shots bench accuracy <product>           check each ad's product item by item against the reference (resumable)
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
ARM_NAMES = {"full_model": "Image model draws the ad", "blender": "Blender only", "layout_first": "Layout first", "relit": "Layout first, relit",
             "relit_neutral": "Layout first, relit in white light"}
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
# Scene sets for other kinds of product, picked by product.json bench.scenes.
TECH_SCENES = [
    ("a light oak desk beside a laptop, a ceramic coffee cup and a notebook, bright Scandinavian home office blurred behind, soft window light", (196, 160, 118), (230, 228, 222), "left"),
    ("a white marble kitchen counter, bright minimal kitchen blurred behind, soft morning daylight", (235, 235, 235), (240, 240, 238), "left"),
    ("a café table by a big window, a flat white in a cup and a croissant, blurred street outside, warm morning light", (150, 110, 80), (200, 190, 170), "right"),
    ("a bedside table next to a small lamp and a book, cosy bedroom blurred behind, warm evening lamp light", (120, 85, 60), (90, 80, 75), "left"),
    ("a seamless pastel peach studio backdrop with a soft floor shadow, clean commercial studio light", (240, 200, 180), (240, 200, 180), "left"),
    ("a seamless deep green studio backdrop with a soft floor shadow, dramatic side light", (40, 70, 55), (40, 70, 55), "right"),
    ("a concrete ledge on a city rooftop at sunset, skyline blurred behind, warm golden light", (150, 145, 140), (220, 150, 110), "right"),
    ("a beach towel on golden sand next to sunglasses, turquoise sea blurred behind, bright midday sun", (220, 200, 150), (140, 190, 220), "right"),
    ("a co-working space table with a keyboard and plants blurred behind, bright modern daylight", (200, 190, 175), (225, 225, 225), "left"),
    ("a train window table, countryside blurred through the window, soft travel daylight", (90, 90, 95), (170, 190, 160), "left"),
    ("a gym bench next to a water bottle and a towel, gym blurred behind, crisp cool light", (60, 60, 65), (120, 120, 130), "right"),
    ("a stone table in a sunny Mediterranean courtyard with lemon trees blurred behind, bright summer light", (210, 195, 170), (230, 220, 190), "left"),
    ("a dark walnut desk with a mechanical keyboard and a monitor glowing blurred behind, moody evening light", (70, 50, 40), (40, 40, 60), "right"),
    ("a park bench in autumn, orange leaves on the ground and trees blurred behind, soft afternoon light", (150, 110, 70), (180, 120, 60), "left"),
    ("a living-room coffee table on a sofa evening, blurred TV glow and a blanket behind, cosy warm lamp light", (110, 80, 60), (70, 70, 90), "left"),
    ("a white seamless studio sweep with a soft reflection on a glossy floor, bright high-key light", (245, 245, 245), (245, 245, 245), "left"),
    ("a mossy rock by a forest stream, ferns blurred behind, soft dappled light", (90, 100, 70), (60, 90, 60), "right"),
    ("a car's centre console seen from the passenger seat, road trip landscape blurred through the windshield", (60, 60, 65), (180, 200, 220), "right"),
    ("a sunlit windowsill with a potted plant, city blurred outside, bright morning light", (230, 225, 215), (200, 210, 225), "left"),
    ("an airport lounge table, departure boards and big windows blurred behind, bright daylight", (180, 175, 170), (200, 210, 220), "right"),
]
WALLET_SCENES = [
    ("a café counter next to a card payment terminal and a takeaway coffee, barista area blurred behind, warm morning light", (150, 110, 80), (190, 170, 150), "left"),
    ("a restaurant table with a folded bill, wine glasses and candles blurred behind, warm evening light", (110, 70, 50), (80, 50, 40), "right"),
    ("a brown leather wallet open on a walnut desk, soft study light", (90, 60, 40), (120, 100, 80), "left"),
    ("a boutique shop counter with shopping bags and a clothes rail blurred behind, bright retail light", (235, 230, 225), (220, 210, 200), "right"),
    ("an airport lounge side table next to a passport and a boarding pass, runway blurred through big windows, daylight", (180, 175, 170), (200, 210, 220), "left"),
    ("a hotel reception desk in marble, elegant lobby blurred behind, warm luxurious light", (225, 220, 210), (170, 140, 100), "right"),
    ("a seamless navy studio backdrop with a soft floor shadow, premium studio light", (25, 35, 60), (25, 35, 60), "left"),
    ("a seamless warm beige studio backdrop with a soft floor shadow, clean commercial light", (225, 205, 180), (225, 205, 180), "right"),
    ("a light oak desk beside a laptop showing an online checkout, home office blurred behind, soft window light", (196, 160, 118), (230, 228, 222), "left"),
    ("a white marble surface with gold jewellery and a watch nearby, luxurious soft light", (235, 235, 235), (240, 238, 235), "left"),
    ("a bar counter with a cocktail, bottles and neon blurred behind, moody night light", (60, 45, 40), (40, 40, 60), "right"),
    ("a farmers' market stall counter with fruit crates blurred behind, bright morning sun", (160, 120, 80), (200, 180, 120), "right"),
    ("a petrol station counter, forecourt blurred through the window, cool daylight", (180, 180, 185), (170, 180, 190), "left"),
    ("a co-working space table next to a phone and earbuds, bright modern office blurred behind", (200, 190, 175), (225, 225, 225), "left"),
    ("a beach-club table next to sunglasses and a fresh juice, sea blurred behind, bright summer light", (220, 200, 160), (140, 190, 220), "right"),
    ("a black slate surface with soft reflections, dark luxury studio light with a rim light", (35, 35, 38), (25, 25, 30), "right"),
    ("a bookshop counter with stacked books blurred behind, warm cosy light", (130, 95, 65), (110, 80, 60), "left"),
    ("a taxi back seat, city lights blurred through the window, evening light", (50, 50, 55), (90, 80, 100), "right"),
    ("a cinema snack counter with popcorn blurred behind, warm colourful light", (120, 40, 40), (90, 30, 40), "left"),
    ("a minimalist concrete shelf with a small plant, soft overcast daylight", (170, 168, 165), (190, 188, 185), "left"),
]
BEAUTY_SCENES = [
    ("a white marble bathroom shelf with a folded towel and a eucalyptus sprig, soft morning window light", (235, 235, 232), (225, 222, 215), "left"),
    ("a vanity table with a round mirror and a ceramic dish of rings blurred behind, warm soft light", (230, 215, 200), (215, 200, 190), "right"),
    ("a travertine block on a seamless sand-coloured backdrop, hard sunlight with palm-leaf shadows", (215, 195, 165), (225, 205, 175), "left"),
    ("the edge of a bathtub with bubbles and candles blurred behind, warm spa light", (240, 238, 232), (200, 190, 180), "right"),
    ("a seamless pastel peach studio backdrop with a soft floor shadow, clean commercial studio light", (240, 200, 180), (240, 200, 180), "left"),
    ("a seamless sage green studio backdrop with water ripples reflected on the floor, fresh bright light", (170, 190, 165), (170, 190, 165), "right"),
    ("a wet pebble beside a still pool of water, soft green foliage blurred behind, dewy morning light", (120, 125, 120), (100, 130, 100), "left"),
    ("a linen-covered bedside table with a glass of water and a book, bedroom blurred behind, golden hour light", (225, 215, 200), (200, 185, 165), "right"),
    ("a pharmacy shelf with neat rows of skincare blurred behind, clean bright retail light", (240, 240, 240), (220, 225, 230), "left"),
    ("a beach towel on warm sand with sunglasses, sea blurred behind, bright summer sun", (220, 200, 150), (140, 190, 220), "right"),
    ("a pink terrazzo countertop, sunny bathroom blurred behind, bright soft light", (235, 205, 200), (240, 225, 220), "left"),
    ("a stack of clean white towels in a hotel bathroom, warm luxurious light", (245, 243, 238), (190, 175, 160), "right"),
    ("a glossy black acrylic surface with soft reflections, dark studio with a warm rim light", (30, 30, 32), (25, 25, 28), "left"),
    ("halved oranges and fresh leaves on a cream surface, bright fresh daylight", (240, 230, 210), (245, 238, 225), "right"),
    ("a wooden tray on a made bed with white sheets, soft morning light", (180, 140, 100), (235, 232, 228), "left"),
]
HOME_SCENES = [
    ("a warm oak kitchen counter next to a pour-over coffee maker and a mug, pale tiles behind, soft morning window light", (176, 128, 86), (214, 216, 212), "left"),
    ("a café counter with an espresso machine and cups blurred behind, warm morning light", (150, 110, 80), (120, 90, 70), "right"),
    ("a breakfast table with a plate of croissants and a jug of milk, sunny dining room blurred behind", (190, 160, 125), (230, 220, 200), "left"),
    ("a wooden picnic table at a lakeside campsite, tent and pine trees blurred behind, early morning mist", (130, 100, 70), (120, 140, 130), "right"),
    ("a cabin windowsill with snowy pines blurred outside, soft cool daylight", (150, 120, 90), (210, 220, 230), "left"),
    ("a white marble kitchen island, bright minimal kitchen behind, soft daylight", (235, 235, 235), (240, 240, 238), "left"),
    ("a rustic shelf in a pantry with jars blurred behind, warm cosy light", (140, 100, 70), (110, 90, 70), "right"),
    ("scattered roasted coffee beans on a dark slate surface, moody studio light with a warm rim light", (45, 40, 38), (30, 28, 26), "left"),
    ("a seamless navy studio backdrop with a soft floor shadow, premium studio light", (25, 35, 60), (25, 35, 60), "right"),
    ("a seamless warm beige studio backdrop with a soft floor shadow, clean commercial light", (225, 205, 180), (225, 205, 180), "left"),
    ("a harbour wall by the sea at sunrise, fishing boats blurred behind, golden light", (150, 145, 140), (220, 180, 140), "right"),
    ("a farmhouse dining table with a linen runner, garden blurred through the window, bright morning light", (170, 130, 95), (220, 225, 210), "left"),
    ("an office kitchenette counter with a kettle, bright modern office blurred behind", (200, 200, 200), (225, 225, 225), "right"),
    ("a coffee roastery counter with burlap sacks and a roaster blurred behind, warm industrial light", (120, 90, 65), (90, 75, 65), "left"),
    ("a boat deck table with a thermos, sea and coastline blurred behind, crisp morning light", (160, 130, 100), (150, 180, 200), "right"),
]
SCENE_SETS = {"drinks": SCENES, "tech": TECH_SCENES, "wallet": WALLET_SCENES, "beauty": BEAUTY_SCENES, "home": HOME_SCENES}
CAMERAS = {
    "eye level": {"height": 1.0, "dist": 1.0, "lens": 60},
    "low hero angle": {"height": 0.35, "dist": 0.9, "lens": 45},
    "high three-quarter view": {"height": 2.6, "dist": 1.0, "lens": 60},
}
CAMERA_PHRASES = {"eye level": "at eye level", "low hero angle": "from a low hero angle", "high three-quarter view": "from a high three-quarter view"}
ARRANGEMENTS = {"single": 1, "pair": 2, "trio": 3}


def _arrangement(n: int, rng: random.Random, scale: float = 1.0, lean: float = 0.0, sides: list[str] | None = None) -> list[dict]:
    """Where each product stands. A leaning product shows its front (leaning back) or its back (turned round, leaning away)."""
    spots = {1: [(0, 0)], 2: [(-40, 10), (40, -10)], 3: [(-70, 20), (0, -15), (70, 20)]}[n]
    out = []
    for k, (x, y) in enumerate(spots):
        turn = rng.uniform(-25, 25)
        back = bool(sides) and sides[k] == "back"
        out.append({"position_mm": [x * scale, y * scale, 0], "rotation_deg": [lean if back else -lean, 0, turn + (180 if back else 0)]})
    return out


def make_briefs(product: str, n: int, seed: int = 7) -> Path:
    folder = find_product(product)
    spec = json.loads((folder / "product.json").read_text())
    height = max(z for _, z in spec["profile_mm"]) if "profile_mm" in spec else spec["dimensions_mm"]["height"]
    width = 2 * max(r for r, _ in spec["profile_mm"]) if "profile_mm" in spec else spec["dimensions_mm"].get("width", spec["dimensions_mm"].get("diameter", 66))
    name = spec.get("display_name", spec["name"])
    # bench: what the product is called, its scene set, how it stands, and (for two-sided products) what each side shows.
    cfg = spec.get("bench", {})
    noun, stance, side_words = cfg.get("noun", "can"), cfg.get("stance", "standing upright"), cfg.get("sides")
    scenes = SCENE_SETS[cfg.get("scenes", "drinks")]
    arrangements = {k: v for k, v in ARRANGEMENTS.items() if v in cfg.get("counts", [1, 2, 3])}
    rng = random.Random(seed)
    out = folder / "bench" / "briefs"
    out.mkdir(parents=True, exist_ok=True)
    for i in range(n):
        scene, floor, wall, side = scenes[i % len(scenes)]
        fmt = rng.choice(list(FORMATS))
        cam_name = rng.choice(list(CAMERAS))
        arr = rng.choice(list(arrangements))
        count = arrangements[arr]
        # One product shows a random side; a pair shows both.
        sides = (["front", "back"] if count == 2 else [rng.choice(["front", "back"]) for _ in range(count)]) if side_words else None
        cam = CAMERAS[cam_name]
        spread = {1: 1.0, 2: 1.35, 3: 1.8}[count] * {"1:1": 1.1, "4:5": 0.95, "9:16": 0.8}[fmt]
        scale = max(1.0, width / 66)
        items = [{"product": str(folder), **p} for p in _arrangement(count, rng, scale, cfg.get("lean_deg", 0), sides)]
        # Far enough back for the product's height, and for the whole group's width to fill at most 80% of the frame (wide things like cards).
        page_w, page_h = FORMATS[fmt]
        group = max(p["position_mm"][0] for p in items) - min(p["position_mm"][0] for p in items) + width * 1.1
        dist = max(height * 3.1 * spread * cam["dist"], group / (0.8 * 36 * min(1, page_w / page_h) / cam["lens"]))
        ad = {
            "page": list(FORMATS[fmt]),
            "products": items,
            "camera": {"lens_mm": cam["lens"], "distance_mm": round(dist), "height_mm": round(height * 0.55 * cam["height"] + 20),
                       "azimuth_deg": rng.uniform(-12, 12), "target_mm": [0, 0, round(height * 0.5)]},
            "set": {"floor_color": list(floor), "wall": wall is not None, "wall_color": list(wall or (200, 200, 200)), "wall_distance_mm": 400},
            "light": {"key_azimuth_deg": -60 if side == "left" else 60, "key_elevation_deg": 35, "key_power": 1.0, "fill": 0.35, "ambient": 0.25},
            "render": {"samples": 64, "exposure": cfg.get("exposure", 0.0), "denoise": True},
            "scene_prompt": f"{scene}, calm uncluttered space at the top of the frame for a headline",
        }
        what = {1: f"One {name} {stance}", 2: f"Two {name}s side by side, {stance}", 3: f"Three {name}s in a row, {stance}"}[count]
        if side_words:
            what += f", showing {side_words[sides[0]]}" if count == 1 else f", the left one showing {side_words[sides[0]]} and the right one {side_words[sides[1]]}"
        keep = "label, logo, lettering, colours and proportions" if noun == "can" else "design, logo, every line of lettering, colours and proportions"
        brief = {
            "id": f"{i:03d}", "scene": scene, "format": fmt, "camera": cam_name, "arrangement": arr, "sides": sides,
            "text": f"{what}, seen {CAMERA_PHRASES[cam_name]}, on {scene}. Format {fmt}. Leave calm space at the top for a headline.",
            "full_model_prompt": (f"A photorealistic advertising photograph, {fmt} format. {what}, exactly the {noun} shown in the reference image, "
                                  f"seen {CAMERA_PHRASES[cam_name]}, on {scene}. {cfg.get('reference_note', '')} Keep the {noun}'s {keep} exactly "
                                  f"as in the reference, at its real size. Calm space at the top of the frame for a headline. No added text, captions or watermark.").replace(".  ", ". "),
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


def relight_all(product: str, workers: int = 4, limit: int | None = None, neutral: bool = False) -> dict:
    """Re-lights every finished layout-first ad. Light estimates run in parallel (once, shared by both variants), Blender one job
    at a time."""
    from . import relight
    arm = "relit_neutral" if neutral else "relit"
    todo = [d for d in _briefs(product)[:limit] if _done(d, "layout_first") and not _done(d, arm)]
    lock = threading.Lock()

    def estimate(d):
        path = d / "out" / "relit" / "light_estimate.json"
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            try:
                path.write_text(json.dumps(relight.estimate_light(d / "out" / "repaint.png"), indent=1))
            except Exception as e:
                _record(d, arm, {"ok": False, "error": repr(e)[:500]}, lock)

    with ThreadPoolExecutor(workers) as pool:
        list(pool.map(estimate, todo))
    for d in todo:
        path = d / "out" / "relit" / "light_estimate.json"
        if not path.exists():
            continue
        t0 = time.time()
        try:
            result = relight.relight(d / "ad.json", json.loads(path.read_text()), neutral)
            shutil.copy(d / "out" / arm / "plate.png", d / f"{arm}.png")
            base = json.loads((d / "arms.json").read_text())["layout_first"]
            # The repaint is reused, so the arm costs what layout first did plus one small vision call.
            _record(d, arm, {"ok": True, "cost_usd": round(base["cost_usd"] + relight.ESTIMATE_COST_USD, 4),
                                 "seconds": round(base["seconds"] + time.time() - t0, 1), "verify": result["verify"]}, lock)
        except BaseException as e:
            _record(d, arm, {"ok": False, "error": repr(e)[:500]}, lock)
    return {arm: sum(_done(d, arm) for d in _briefs(product)[:limit])}


JUDGE_PROMPT = """You are judging product advertising images for a brand, blind. The first image is a REAL photo of the product: the exact {noun} the brand sells.{reference_note} Then come three candidate ads, labelled A, B and C, all made from the same brief:

BRIEF: {brief}

Score each candidate from 0 to 10 on:
- product_fidelity: is it exactly the product in the reference? Logo shape and spelling, every line of label text and marks, colours, proportions, and a believable real-world size in the scene. Any garbled, misspelt, missing or invented lettering or logo, or the wrong product, scores 3 or less.
- realism: does it look like a real photograph? Light, shadows, contact with the surface, perspective and depth all consistent; CG or pasted-in looks score low.
- brief_match: does it show what the brief asks (scene, number of {noun}s{sides}, camera angle, space for a headline)?
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


def _judge_file(tag: str | None) -> str:
    return f"judge_{tag}.json" if tag else "judge.json"


def judge(product: str, workers: int = 4, model: str | None = None, arms: list[str] | None = None, tag: str | None = None) -> dict:
    arms = arms or ARMS
    if len(arms) != 3:
        raise KeyError("the judge compares exactly three arms")
    from google import genai
    from google.genai import types
    model = model or setting("SHOTS_JUDGE_MODEL") or "gemini-3.1-pro-preview"
    folder = find_product(product)
    spec = json.loads((folder / "product.json").read_text())
    ref = Image.open(folder / spec["reference_photo"]).convert("RGB")
    client = genai.Client(api_key=setting("GEMINI_API_KEY"))

    def one(d: Path):
        if (d / _judge_file(tag)).exists():
            return
        if not all((d / f"{a}.png").exists() for a in arms):
            return
        order = list(arms)
        random.Random(int(d.name)).shuffle(order)  # fixed per brief, different across briefs
        key = dict(zip("ABC", order))
        brief = json.loads((d / "brief.json").read_text())
        contents = [ref] + [x for label, arm in key.items() for x in (f"Candidate {label}:", Image.open(d / f"{arm}.png").convert("RGB"))]
        cfg = spec.get("bench", {})
        note = f" {cfg['reference_note']}" if cfg.get("reference_note") else ""
        contents.append(JUDGE_PROMPT.format(brief=brief["text"], noun=cfg.get("noun", "can"), reference_note=note,
                                            sides=" and which side each shows" if cfg.get("sides") else ""))
        for attempt in range(3):
            try:
                r = client.models.generate_content(model=model, contents=contents, config=types.GenerateContentConfig(
                    response_mime_type="application/json", response_schema=JUDGE_SCHEMA, temperature=0.2))
                data = json.loads(r.text)
                result = {"model": model, "key": key, "raw": data,
                          "arms": {arm: {**data["candidates"][label], "rank": data["ranking"].index(label) + 1} for label, arm in key.items()}}
                (d / _judge_file(tag)).write_text(json.dumps(result, indent=1))
                return
            except Exception as e:
                err = repr(e)[:300]
                time.sleep(5 * (attempt + 1))
        (d / "judge_error.txt").write_text(err)

    with ThreadPoolExecutor(workers) as pool:
        list(pool.map(one, _briefs(product)))
    return {"judged": sum((d / _judge_file(tag)).exists() for d in _briefs(product))}


ACCURACY_PROMPT = """The first image is the reference for a product: the exact {noun} the brand sells.{reference_note}
The second image is an advert that should show: {brief}

Check the product in the advert against the reference, item by item. If several products are shown, check them all; an item is wrong if it is wrong on any of them. Look at the product at full resolution before answering.

Items:
{items}

For each item give a status:
- correct: present and the same as the reference (spelling, shape, colour, layout)
- wrong: present but garbled, misspelt, altered, redrawn differently or misplaced
- missing: it should be visible on the side the advert shows, but it isn't there
- not_visible: on a side the advert doesn't show, hidden, or too small to read at this size
Then:
- shape_ok: the product's silhouette and proportions match the reference
- colour_ok: its colours match the reference
- invented: the product carries lettering, logos or marks the reference doesn't have (true/false), with what in invented_what
- exact: true only if no item is wrong or missing, shape_ok and colour_ok are true and nothing is invented
Judge only what you see."""

ACCURACY_SCHEMA = {
    "type": "object",
    "properties": {
        "items": {"type": "array", "items": {"type": "object", "properties": {
            "item": {"type": "string"}, "status": {"type": "string", "enum": ["correct", "wrong", "missing", "not_visible"]}, "note": {"type": "string"}},
            "required": ["item", "status"]}},
        "shape_ok": {"type": "boolean"}, "colour_ok": {"type": "boolean"}, "invented": {"type": "boolean"}, "invented_what": {"type": "string"},
        "exact": {"type": "boolean"},
    },
    "required": ["items", "shape_ok", "colour_ok", "invented", "exact"],
}
ACCURACY_ARMS = ["full_model", "layout_first"]


def accuracy(product: str, workers: int = 4, model: str | None = None) -> dict:
    """A strict product check of each ad on its own, item by item from product.json bench.check. Blender only is skipped: its
    product pixels are the ones layout first keeps."""
    from google import genai
    from google.genai import types
    model = model or setting("SHOTS_JUDGE_MODEL") or "gemini-3.1-pro-preview"
    folder = find_product(product)
    spec = json.loads((folder / "product.json").read_text())
    cfg = spec.get("bench", {})
    if not cfg.get("check"):
        raise KeyError("product.json has no bench.check list of items to check")
    ref = Image.open(folder / spec["reference_photo"]).convert("RGB")
    note = f" {cfg['reference_note']}" if cfg.get("reference_note") else ""
    items = "\n".join(f"- {c}" for c in cfg["check"])
    client = genai.Client(api_key=setting("GEMINI_API_KEY"))
    lock = threading.Lock()

    def one(d: Path, arm: str):
        path = d / "accuracy.json"
        if (d / f"{arm}.png").exists() is False or (path.exists() and arm in json.loads(path.read_text())):
            return
        brief = json.loads((d / "brief.json").read_text())
        text = ACCURACY_PROMPT.format(noun=cfg.get("noun", "can"), reference_note=note, brief=brief["text"], items=items)
        for attempt in range(3):
            try:
                r = client.models.generate_content(model=model, contents=[ref, Image.open(d / f"{arm}.png").convert("RGB"), text],
                                                   config=types.GenerateContentConfig(response_mime_type="application/json",
                                                                                      response_schema=ACCURACY_SCHEMA, temperature=0.2))
                data = json.loads(r.text)
                with lock:
                    rec = json.loads(path.read_text()) if path.exists() else {}
                    rec[arm] = {"model": model, **data}
                    path.write_text(json.dumps(rec, indent=1))
                return
            except Exception:
                time.sleep(5 * (attempt + 1))

    with ThreadPoolExecutor(workers) as pool:
        list(pool.map(lambda job: one(*job), [(d, arm) for d in _briefs(product) for arm in ACCURACY_ARMS]))
    return {"checked": sum((d / "accuracy.json").exists() for d in _briefs(product))}


def accuracy_summary(product: str) -> dict:
    out = {}
    recs = [json.loads((d / "accuracy.json").read_text()) for d in _briefs(product) if (d / "accuracy.json").exists()]
    for arm in ACCURACY_ARMS:
        rows = [r[arm] for r in recs if arm in r]
        if not rows:
            continue
        status = [i["status"] for r in rows for i in r["items"]]
        seen = sum(s != "not_visible" for s in status)
        out[arm] = {
            "ads": len(rows),
            "exact_rate": round(sum(r["exact"] for r in rows) / len(rows), 3),
            "item_accuracy": round(status.count("correct") / seen, 3) if seen else None,
            "items_wrong_rate": round(status.count("wrong") / seen, 3) if seen else None,
            "items_missing_rate": round(status.count("missing") / seen, 3) if seen else None,
            "items_not_visible_rate": round(status.count("not_visible") / len(status), 3),
            "invented_rate": round(sum(r["invented"] for r in rows) / len(rows), 3),
            "shape_ok_rate": round(sum(r["shape_ok"] for r in rows) / len(rows), 3),
            "colour_ok_rate": round(sum(r["colour_ok"] for r in rows) / len(rows), 3),
        }
    return out


def _sheet(d: Path, judged: dict, out: Path, h: int = 520):
    tiles = []
    for arm in judged["arms"]:
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


def report(product: str, out_dir: Path, examples: int = 6, arms: list[str] | None = None, tag: str | None = None) -> dict:
    ARMS = arms or globals()["ARMS"]
    rows = []
    for d in _briefs(product):
        if (d / _judge_file(tag)).exists():
            rows.append((d, json.loads((d / _judge_file(tag)).read_text()), json.loads((d / "arms.json").read_text())))
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
    for arm in ("layout_first", "relit", "relit_neutral"):
        if arm in ARMS:
            checks = [a[arm]["verify"] for _, _, a in rows]
            summary[f"{arm}_pixel_check"] = {"passed": sum(v["pass"] for v in checks), "of": len(checks)}
    out_dir.mkdir(parents=True, exist_ok=True)
    img_dir = out_dir / "examples"
    picks = []
    by_win = {arm: [r for r in rows if r[1]["arms"][arm]["rank"] == 1] for arm in ARMS}
    for arm in ARMS:
        picks += by_win[arm][: max(1, examples // 3)]
    fails = sorted(rows, key=lambda r: r[1]["arms"]["full_model"]["product_fidelity"])[:2] if "full_model" in ARMS else []
    picks += [r for r in fails if r not in picks]
    for d, j, _ in picks:
        _sheet(d, j, img_dir / f"brief_{d.name}.jpg")
    summary["examples"] = [{"brief": d.name, "text": json.loads((d / "brief.json").read_text())["text"], "file": f"examples/brief_{d.name}.jpg",
                            "issues": {arm: j["arms"][arm]["worst_issue"] for arm in ARMS}} for d, j, _ in picks]
    if not tag:
        summary["product_accuracy"] = accuracy_summary(product)
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=1))
    return summary
