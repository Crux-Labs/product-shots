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


def test_two_sided_product_briefs_show_front_and_back(tmp_path):
    product = tmp_path / "demo-phone"
    shutil.copytree(ROOT / "examples/demo-phone", product, ignore=shutil.ignore_patterns("out", "check", "bench"))
    out = bench.make_briefs(str(product), 12)
    for d in sorted(out.iterdir()):
        brief, ad = json.loads((d / "brief.json").read_text()), json.loads((d / "ad.json").read_text())
        assert len(brief["sides"]) == len(ad["products"]) <= 2
        assert brief["scene"] in [s[0] for s in bench.TECH_SCENES]
        for side, item in zip(brief["sides"], ad["products"]):
            # The back is turned round and leans away from the camera, the front leans back towards the wall.
            assert (item["rotation_deg"][2] > 90) == (side == "back")
            assert (item["rotation_deg"][0] > 0) == (side == "back")
        assert "the phone" in brief["full_model_prompt"] and "the can" not in brief["full_model_prompt"]


def test_accuracy_summary_ignores_items_not_in_view(tmp_path, monkeypatch):
    d = tmp_path / "000"
    d.mkdir()
    (d / "ad.json").write_text("{}")
    item = lambda s: {"item": "x", "status": s}
    rec = {"full_model": {"items": [item("correct"), item("wrong"), item("not_visible")], "shape_ok": True, "colour_ok": True, "invented": True, "exact": False},
           "layout_first": {"items": [item("correct"), item("correct"), item("not_visible")], "shape_ok": True, "colour_ok": True, "invented": False, "exact": True}}
    (d / "accuracy.json").write_text(json.dumps(rec))
    monkeypatch.setattr(bench, "_briefs", lambda product: [d])
    s = bench.accuracy_summary("x")
    assert s["full_model"]["item_accuracy"] == 0.5 and s["full_model"]["exact_rate"] == 0
    assert s["layout_first"]["item_accuracy"] == 1.0 and s["layout_first"]["invented_rate"] == 0
