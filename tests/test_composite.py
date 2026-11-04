import numpy as np
import pytest
from PIL import Image

from shots.composite import ProductPixelsChanged, composite, composite_arrays, verify


def scene(h=64, w=80):
    """A red square product with a soft shadow to its right, over a grey room the model 'painted' blue."""
    layer = np.zeros((h, w, 4))
    mask = np.zeros((h, w))
    layer[20:40, 20:40] = (0.8, 0.1, 0.1, 1.0)
    mask[20:40, 20:40] = 1.0
    layer[22:42, 40:50, 3] = 0.5  # shadow: alpha only, black
    env = np.zeros((h, w, 3))
    env[...] = (0.2, 0.3, 0.9)
    env[20:40, 20:40] = (0.0, 1.0, 0.0)  # the model's own (wrong) product, which must not survive
    return env, layer, mask


def test_product_is_copied_byte_for_byte():
    env, layer, mask = scene()
    out, check = composite_arrays(env, layer, mask)
    assert (out[20:40, 20:40] == np.round(layer[20:40, 20:40, :3] * 255)).all()
    assert check["product_px"] == 400


def test_shadow_darkens_room_and_far_room_is_untouched():
    env, layer, mask = scene()
    out, _ = composite_arrays(env, layer, mask, shadow_reach_px=20)
    room = np.round(env[0, 0] * 255)
    assert (out[30, 45] < room).all()
    assert (out[2, 2] == room).all()


def save(run, env, layer, mask):
    Image.fromarray(np.round(layer * 255).astype(np.uint8), "RGBA").save(run / "layer.png")
    m = np.zeros(layer.shape, dtype=np.uint8)
    m[..., 3] = np.round(mask * 255)
    Image.fromarray(m, "RGBA").save(run / "mask.png")
    Image.fromarray(np.round(env * 255).astype(np.uint8)).save(run / "repaint.png")


def test_composite_writes_plate_and_verify_passes(tmp_path):
    save(tmp_path, *scene())
    check = composite(tmp_path)
    assert check["verify"]["pass"] and check["verify"]["changed_px"] == 0


def test_verify_catches_a_changed_product_pixel(tmp_path):
    save(tmp_path, *scene())
    composite(tmp_path)
    img = np.asarray(Image.open(tmp_path / "plate.png")).copy()
    img[30, 30] = (0, 255, 0)
    Image.fromarray(img).save(tmp_path / "tampered.png")
    with pytest.raises(ProductPixelsChanged):
        verify(tmp_path / "tampered.png", tmp_path)
