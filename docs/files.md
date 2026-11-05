# Files

## Product: `products/<name>/product.json`

| Field | Templates | Meaning |
|---|---|---|
| `name` | all | Folder name, lowercase with dashes. |
| `display_name` | all | How the image model hears about the product, e.g. "red peppermint tin". |
| `template` | all | `box` or `cylinder`. See [templates.md](templates.md). |
| `dimensions_mm` | all | Real size. box: `width`, `depth`, `height`. cylinder: `diameter`, `height`. |
| `body_color` | all | sRGB `[r, g, b]` for any area without a texture. |
| `finish` | all | `matte`, `paper`, `glossy`, `metal` or `plastic`. |
| `faces` | box | `front`, `back`, `left`, `right`, `top`, `bottom`: texture paths relative to the product folder. Missing faces use `body_color`. |
| `bevel_mm` | box | Edge rounding, default 0.8. |
| `side` | cylinder | `texture`, `wrap_deg` (how much of the circumference the texture covers, centred on the front; default 360), optional `z_from_mm` / `z_to_mm` for a label band. |
| `top` | cylinder | `texture` for a printed lid (front of the product at the bottom of the image), or just `color` and `finish` for a bare lid such as a can end. `from_mm` gives everything above that height (a can's neck and rim) the lid's material. |
| `profile_mm` | cylinder | Optional `[[radius, z], ...]` from the base up, for bottles and jars. Replaces `dimensions_mm`. |

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
