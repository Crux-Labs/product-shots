"""Resolves an ad or product spec and runs shots/bpy/build.py in a headless Blender."""
import json
import os
import subprocess
from pathlib import Path

from .config import find_blender, find_product

BUILD = Path(__file__).resolve().parent / "bpy" / "build.py"


def load_product(name_or_path: str, relative_to: Path | None = None) -> dict:
    folder = find_product(name_or_path, relative_to)
    spec = json.loads((folder / "product.json").read_text())
    spec.setdefault("name", folder.name)
    spec["dir"] = str(folder)
    return spec


def resolve_ad(ad_path: Path) -> dict:
    ad = json.loads(ad_path.read_text())
    items = []
    for item in ad["products"]:
        items.append({**item, "product": load_product(item["product"], ad_path.parent)})
    return {**ad, "mode": "layout", "products": items}


def run(spec: dict, out_dir: Path, log_name: str) -> dict:
    blender = find_blender()
    if not blender:
        raise SystemExit("Blender not found. Run /setup, or set BLENDER_PATH in .env.")
    out_dir.mkdir(parents=True, exist_ok=True)
    spec_path = out_dir / f"{log_name}_spec.json"
    spec_path.write_text(json.dumps(spec, indent=1))
    cmd = [str(blender), "-b", "--factory-startup", "--python-exit-code", "1", "-P", str(BUILD), "--", str(spec_path), str(out_dir)]
    log = out_dir / f"{log_name}.log"
    for _ in range(3):
        with open(log, "w") as f:
            done = subprocess.run(cmd, stdout=f, stderr=subprocess.STDOUT, env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
        # Blender on Apple GPUs sometimes aborts while compiling Metal kernels (SIGABRT, "NSURL ... nil string"); a rerun works.
        if done.returncode != -6:
            break
    if done.returncode:
        tail = "\n".join(log.read_text().splitlines()[-25:])
        raise SystemExit(f"Blender failed (exit {done.returncode}); last lines of {log}:\n{tail}")
    marker = "SHOTS_LAYOUT " if spec.get("mode", "layout") == "layout" else "SHOTS_VIEWS "
    line = next((l for l in log.read_text().splitlines() if l.startswith(marker)), None)
    return json.loads(line[len(marker):]) if line else {}


def layout(ad_path: Path, out_dir: Path) -> dict:
    return run(resolve_ad(ad_path), out_dir, "layout")


def views(product: str, out_dir: Path) -> dict:
    return run({"mode": "views", "products": [{"product": load_product(product)}]}, out_dir, "views")
