# Files

## Product: `products/<name>/product.json`

| Field | Templates | Meaning |
|---|---|---|
| `name` | all | Folder name, lowercase with dashes. |
| `display_name` | all | How the image model hears about the product, e.g. "red peppermint tin". |
| `template` | all | `box`, `cylinder` or `slab`. See [templates.md](templates.md). |
| `dimensions_mm` | all | Real size. box: `width`, `depth`, `height`. cylinder: `diameter`, `height`. slab: `width`, `height`, `depth` (thickness). |
| `body_color` | all | sRGB `[r, g, b]` for any area without a texture. |
| `finish` | all | `matte`, `paper`, `glossy`, `metal`, `plastic`, `aluminium` (bare can metal), `printed_metal` (ink on metal under varnish, as on drinks cans: coloured ink lets the metal shine through, white and black ink don't), `glass` (a phone screen) or `frosted_glass` (a matte glass back). |
| `faces` | box, slab | box: `front`, `back`, `left`, `right`, `top`, `bottom`; slab: `front`, `back`. Texture paths relative to the product folder. Missing faces use `body_color`. |
| `bevel_mm` | box, slab | Edge rounding, default 0.8 (box) or 0.5 (slab). |
| `corner_radius_mm` | slab | Rounding of the outline's corners, as seen from the front. Make it a touch larger than the photo's so no background shows at the corners. |
| `face_finish` | slab | Finish per face, e.g. `{"front": "glass", "back": "frosted_glass"}`; the edge uses `finish`. |
| `emit` | slab | `{"front": 1.0}` makes that face glow with its own image, for a screen that is on. |
| `raised` | slab | Blocks standing proud of a face, such as a camera island: `face`, `box` as `[left, top, right, bottom]` fractions of that face's image, `radius_mm`, `depth_mm`, optional `bevel_mm`. The block's top shows the face pixels it covers. |
| `side` | cylinder | `texture`, `wrap_deg` (how much of the circumference the texture covers, centred on the front; default 360), optional `z_from_mm` / `z_to_mm` for a label band, optional `turn_deg` to choose which part of a full label faces the camera (negative brings the label's left side round to the front). |
| `top` | cylinder | `texture` for a printed lid (front of the product at the bottom of the image), or just `color` and `finish` for a bare lid such as a can end. `from_mm` gives everything above that height (a can's neck and rim) the lid's material; with both `texture` and `color`, the image goes on the lid and the colour on the neck and rim. `tab: true` adds a drinks-can pull tab and rivet. |
| `bottom` | cylinder | `color`, `finish` and `to_mm`: everything below that height (a can's unprinted base) takes this material. |
| `profile_mm` | cylinder | Optional `[[radius, z], ...]` from the base up, for bottles and jars. Replaces `dimensions_mm`. |

| `reference_photo` | all | Optional. The photo the benchmark's image-model arm and judges get as "the product". |
| `bench` | all | Optional benchmark settings: `noun` ("phone"), `scenes` (`drinks`, `tech`, `wallet`, `beauty`, `home`), `stance` ("standing upright, leaning slightly back"), `lean_deg`, `counts` (e.g. `[1, 2]`), `sides` (`{"front": "its screen", "back": "its back"}` for a two-sided product: a pair shows both sides), `reference_note`, and `check`: the list of printed details the accuracy check looks for, each prefixed with the side it is on. |

Orientation: the model's base sits on the floor, its front faces the camera at `rotation_deg` `[0, 0, 0]`.

## Ad: `products/<name>/ads/<slug>/ad.json`

```json
{
  "page": [1080, 1350],
  "products": [{"product": "demo-tin", "position_mm": [0, 0, 0], "rotation_deg": [0, 0, 0]}],
  "camera": {"lens_mm": 60, "distance_mm": 520, "height_mm": 230, "azimuth_deg": 0, "target_mm": [0, 0, 45]},
  "set": {"floor_color": [176, 128, 86], "wall": true, "wall_color": [214, 216, 212], "wall_distance_mm": 260},
  "light": {"key_azimuth_deg": -60, "key_elevation_deg": 35, "key_power": 1.0, "fill": 0.35, "ambient": 0.25},
  "render": {"samples": 128, "exposure": 0.0, "denoise": true},
  "scene_prompt": "a warm oak kitchen counter, pale grey tiles behind, soft morning window light from the left",
  "overlay": "overlay.html"
}
```

- `products[].product`: a product name (looked up in `products/` then `examples/`) or a path.
- `camera`: `distance_mm` is horizontal distance from `target_mm`, `height_mm` is above the floor, `azimuth_deg` turns the camera round the target (0 = in front, positive = to the right). Optional `roll_deg`.
- `light`: `key_azimuth_deg` negative puts the key light on the left. `key_power`, `fill` and `ambient` scale the key, fill and sky.
- `overlay` (optional): an HTML file, the same size as `page`, transparent background, for headline and copy.

## Results: `ads/<slug>/out/`

| File | What |
|---|---|
| `guide.png` | Blender layout of the whole scene, sent to the image model. |
| `layer.png` | Products plus the shadows they cast, transparent elsewhere. |
| `mask.png` | Product alpha. |
| `repaint.png` + `repaint.json` | The image model's output, with model, prompt, cost. |
| `plate.png` + `composite.json` | Exact products over the repainted room, with the pixel check. |
| `final.png` | The deliverable (plate plus overlay text, if any). |
| `run.json` | Summary of the run. |
