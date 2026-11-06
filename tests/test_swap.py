import numpy as np

from shots import swap


def test_corners_are_ordered_by_where_they_sit_in_the_image():
    mixed = [[800, 228], [546, 244], [508, 793], [779, 809]]  # a model's labels for a back face, left and right swapped
    assert swap.upright(mixed) == [[546, 244], [800, 228], [779, 809], [508, 793]]


def test_pose_recovers_a_known_card_and_focal_length():
    spec = {"template": "slab", "dimensions_mm": {"width": 85.6, "height": 51.9, "depth": 0.76}}
    a, b = np.radians(-20), np.radians(25)
    tilt = np.array([[1, 0, 0], [0, np.cos(a), -np.sin(a)], [0, np.sin(a), np.cos(a)]])
    yaw = np.array([[np.cos(b), -np.sin(b), 0], [np.sin(b), np.cos(b), 0], [0, 0, 1]])
    R = tilt @ np.array([[1, 0, 0], [0, 0, -1], [0, 1, 0]]) @ yaw
    t, f, size = np.array([30, 40, 500.0]), 1500.0, (1080, 1350)
    K = np.array([[f, 0, size[0] / 2], [0, f, size[1] / 2], [0, 0, 1]])
    centre, (u, v), fw, fh = swap.face_rect(spec, "front")
    img = [(K @ (R @ p + t))[:2] / (K @ (R @ p + t))[2] for p in (centre + s * fw / 2 * u + r * fh / 2 * v for s, r in ((-1, 1), (1, 1), (1, -1), (-1, -1)))]
    plane = np.array([[-fw / 2, fh / 2], [fw / 2, fh / 2], [fw / 2, -fh / 2], [-fw / 2, -fh / 2]])
    assert abs(swap.focal_from(swap.homography(plane, np.array(img)), size) - f) < 1
    T = swap.pose(img, spec, "front", f, size)
    assert np.allclose(T[:3, :3], R, atol=1e-6) and np.allclose(T[:3, 3], t, atol=1e-3)


def test_rebuild_covers_the_model_product_and_its_reflection_but_never_ours():
    mask = np.zeros((200, 200), np.uint8)
    mask[60:120, 80:120] = 255
    region = swap.rebuild_region([{"box": [70, 50, 130, 130]}], mask)
    assert not region[mask == 255].any()
    assert region[55, 75] and region[150, 100], "the model's outline and the reflection below it"
    assert not region[10, 10] and not region[190, 100]


def test_key_light_follows_the_camera():
    spec = {"template": "slab", "dimensions_mm": {"width": 72, "height": 145.9, "depth": 8.2}}
    behind = np.eye(4)
    behind[:3, :3] = np.array([[-1, 0, 0], [0, 0, -1], [0, -1, 0]])  # camera sees the back: product front points away
    behind[:3, 3] = [0, 50, 500]
    out = swap.render_spec([{}], [behind], 1500, (1080, 1080), {"name": "p"})
    assert abs(abs(out["light"]["key_azimuth_deg"] + 55) - 180) < 1, "a back view is lit from the camera's side"
