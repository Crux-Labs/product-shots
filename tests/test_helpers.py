import numpy as np
from PIL import Image

from shots import prompt, textures
from shots.repaint import openai_size


def test_prompt_grammar_for_one_and_many():
    one = prompt.build("a marble counter.", ["red tin"])
    assert "The red tin in the masked area is the real product: keep it exactly where it is" in one
    many = prompt.build("a marble counter", ["red tin", "green box"])
    assert "The green box and red tin in the masked area are the real products: keep them exactly where they are" in many
    assert "a marble counter." in many


def test_openai_size_keeps_aspect_and_multiple_of_16():
    w, h = map(int, openai_size(1080, 1350).split("x"))
    assert max(w, h) <= 2048 and w % 16 == 0 and h % 16 == 0
    assert abs(w / h - 0.8) < 0.01


def test_rectify_straightens_a_skewed_face(tmp_path):
    img = Image.new("RGB", (200, 200), "white")
    img.paste((255, 0, 0), (50, 50, 150, 150))
    img.save(tmp_path / "photo.png")
    out = textures.rectify(tmp_path / "photo.png", [(50, 50), (150, 50), (150, 150), (50, 150)], tmp_path / "face.png", (100, 100))
    face = np.asarray(Image.open(out).convert("RGB"))
    assert face.shape == (100, 100, 3) and (face[10:90, 10:90] == (255, 0, 0)).all()


def test_unwrap_width_follows_wrap_angle(tmp_path):
    Image.new("RGB", (300, 120), "blue").save(tmp_path / "front.png")
    out = textures.unwrap(tmp_path / "front.png", (50, 10, 250, 110), tmp_path / "side.png", wrap_deg=120)
    w, h = Image.open(out).size
    assert h == 100 and abs(w - round(100 * np.radians(120))) <= 1
