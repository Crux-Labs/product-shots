import json
import shutil

from shots import bench
from shots.config import ROOT


def test_briefs_are_valid_and_repeatable(tmp_path):
    product = tmp_path / "demo-tin"
    shutil.copytree(ROOT / "examples/demo-tin", product, ignore=shutil.ignore_patterns("out", "check", "bench"))
    out = bench.make_briefs(str(product), 6)
    briefs = sorted(out.iterdir())
    assert len(briefs) == 6
    first = (briefs[0] / "ad.json").read_text()
    ad = json.loads(first)
    assert ad["page"] in [list(v) for v in bench.FORMATS.values()]
    assert 1 <= len(ad["products"]) <= 3
    brief = json.loads((briefs[0] / "brief.json").read_text())
    assert "reference image" in brief["full_model_prompt"] and brief["text"]
    bench.make_briefs(str(product), 6)
    assert (briefs[0] / "ad.json").read_text() == first, "same seed, same briefs"
