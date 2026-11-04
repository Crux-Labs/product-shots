"""A tiny real render of the demo scene. Skipped when Blender isn't installed."""
import json

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
