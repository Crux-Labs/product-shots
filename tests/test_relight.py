import numpy as np
from PIL import Image

from shots import relight

EST = {"key_azimuth_deg": -150, "key_elevation_deg": 95, "key_color": [255, 180, 120], "key_hardness": 1.0,
       "key_strength": 3.0, "ambient_color": [200, 210, 230], "ambient_strength": 0.0, "exposure": 0.0}


def test_back_light_comes_round_to_the_front_and_shadows_stay_open():
    light = relight.light_spec(EST, {"ambient": 0.25})
    assert light["key_azimuth_deg"] == -75, "a back light keeps its side but never falls behind the product"
    assert light["key_elevation_deg"] == 85 and light["key_power"] == 1.6
    assert light["fill"] >= 0.22, "the label must still read in a dark room"
    assert light["key_size_m"] < 0.3 and light["ambient"] == 0.25


def test_panorama_puts_the_photo_in_front_and_its_mirror_behind(tmp_path):
    photo = np.zeros((100, 200, 3), np.uint8)
    photo[:, :100] = (255, 0, 0)  # left half red, right half blue
    photo[:, 100:] = (0, 0, 255)
    Image.fromarray(photo).save(tmp_path / "room.png")
    pano = np.asarray(Image.open(relight.panorama(tmp_path / "room.png", tmp_path / "pano.png", width=400, blur=0)))
    assert pano.shape == (200, 400, 3)
    mid = pano[100]
    # u = 0.75 looks where the camera looks: the photo runs left (red) to right (blue) around it; behind the camera it is mirrored.
    assert mid[220][0] > 200 and mid[380][2] > 200
    assert mid[20][2] > 200 and mid[180][0] > 200
