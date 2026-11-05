"""A tiny real render of the demo scene. Skipped when Blender isn't installed."""
import json
import shutil

import numpy as np
import pytest
from PIL import Image

from shots import blender
from shots.config import ROOT, find_blender

pytestmark = pytest.mark.skipif(find_blender() is None, reason="Blender not installed")


def test_layout_writes_three_passes(tmp_path):
    ad = json.loads((ROOT / "examples/demo-tin/ads/counter/ad.json").read_text())
    ad.update(page=[160, 200], render={"samples": 4, "denoise": False})
    for item in ad["products"]:
        item["product"] = str(ROOT / "examples" / item["product"])
    (tmp_path / "ad.json").write_text(json.dumps(ad))
    info = blender.layout(tmp_path / "ad.json", tmp_path / "out")
    assert len(info["products"]) == 2
    mask = np.asarray(Image.open(tmp_path / "out/mask.png").getchannel("A"))
    assert (mask == 255).sum() > 500, "both products should be in frame"
    assert Image.open(tmp_path / "out/guide.png").size == (160, 200)


def test_printed_can_with_tab_renders(tmp_path):
    """A drinks can: printed-metal label turned round, bare-metal lid with a pull tab, bare-metal base."""
    shutil.copytree(ROOT / "examples/demo-tin", tmp_path / "can", ignore=shutil.ignore_patterns("out", "check", "bench", "ads"))
    spec = json.loads((tmp_path / "can/product.json").read_text())
    spec.update(dimensions_mm=None, profile_mm=[[25, 0], [33, 9], [33, 108], [26.5, 121], [26.2, 122.6], [24.9, 119.6]],
                finish="printed_metal", bottom={"color": [196, 199, 204], "finish": "aluminium", "to_mm": 7})
    spec["side"].update(z_from_mm=9, z_to_mm=108, turn_deg=-25)
    spec["top"] = {"color": [196, 199, 204], "finish": "aluminium", "from_mm": 116, "texture": "kit/top.png", "tab": True}
    (tmp_path / "can/product.json").write_text(json.dumps(spec))
    ad = {"page": [120, 160], "products": [{"product": str(tmp_path / "can")}], "render": {"samples": 4, "denoise": False},
          "camera": {"lens_mm": 60, "distance_mm": 450, "height_mm": 200, "target_mm": [0, 0, 60]}}
    (tmp_path / "ad.json").write_text(json.dumps(ad))
    blender.layout(tmp_path / "ad.json", tmp_path / "out")
    mask = np.asarray(Image.open(tmp_path / "out/mask.png").getchannel("A"))
    assert (mask == 255).sum() > 500
