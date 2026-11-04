---
name: make-ad
description: Makes a finished product image or ad from a plain-language description, with the user's 3D product placed in Blender and only the surroundings repainted by an image model. Use when the user says /make-ad, or asks for a product photo, ad, scene or variation for a product that has a product.json.
---

# Make an ad

Goal: `products/<product>/ads/<slug>/out/final.png`, with `shots verify` passing, shown to the user with its cost.

## 1. Understand the ask

Get, asking only for what's missing:
- which product(s): must exist under `products/` (or `examples/`); if not, offer `/new-product`
- the scene: surface, room, light, mood ("on a marble bathroom shelf, soft morning light")
- format: 1:1 (1080x1080), 4:5 (1080x1350), 9:16 (1080x1920), 16:9 (1920x1080)
- headline or text, if any (optional, see step 5)

## 2. Write ad.json

Create `products/<product>/ads/<slug>/ad.json` (format in `docs/files.md`; `examples/demo-tin/ads/counter/ad.json` is a working example). You decide:
- **Placement:** `position_mm` on the floor plane (origin is the frame centre, +Y away from camera); `rotation_deg` [x, y, z], where z turns the product; lying down is x = 90.
- **Camera:** `lens_mm` (50-85 for product shots), `distance_mm` and `height_mm` from the target, `target_mm` at the products' middle height. Lower camera = heroic; higher = flat-lay feel (a top-down flat lay is height much bigger than distance).
- **Set:** `floor_color` and `wall_color` close to the scene the user wants (warm brown for wood, white for marble). The model repaints them, but a close colour helps it. Set `"wall": false` for outdoor or top-down scenes.
- **Light:** `key_azimuth_deg` matches where the window or sun should be (negative = left). Product light is kept in the final image, so light the product the way the scene will be lit.
- **scene_prompt:** the room in plain photographic words: surface, background, light direction, depth of field, and where to leave calm space for text. Don't mention the product; `shots` adds the rules that protect it.

## 3. Check the layout first

Run `.venv/bin/shots layout <ad.json>` (about 1-2 min) and look at `out/guide.png`. Check framing, product size in frame, nothing cut off, room for text, lighting direction. Fix `ad.json` and re-run until it's right; this costs nothing. Show it to the user if the composition is a judgement call.

## 4. Repaint and finish

Run `.venv/bin/shots ad <ad.json> --skip-layout` (reuses the layout; about 30-60 s and $0.05-0.15). It repaints, puts the product back and verifies. Look at `out/final.png` before showing it:
- Does the room match the request? Is the light direction plausible against the product's shadow?
- **Ghosts:** a faint second edge or outline right next to the product means the model redrew it slightly bigger. Re-run `shots ad --skip-layout` once (a new repaint usually fixes it), or move the product a little.
- If the room is wrong, adjust `scene_prompt` and re-run with `--skip-layout`. Tell the user before spending on more than two re-runs.

Never fix a product problem by editing the final image or asking the image model about the product. Product problems are fixed in the model (`/new-product`) or the layout.

## 5. Text (optional)

If the user wants a headline: write `products/<product>/ads/<slug>/overlay.html`, a page the exact image size with a transparent background and the text placed in the calm area, and add `"overlay": "overlay.html"` to `ad.json`. It needs `.venv/bin/pip install -e '.[overlay]'` and `.venv/bin/playwright install chromium` once (ask first). Then `shots ad <ad.json> --skip-layout`.

## 6. Deliver

Show `out/final.png` (and `out/guide.png` if useful), and report from the output:
- cost (`cost_usd`) and time
- that the product pixels were verified unchanged (`product_pixels_from_model: 0`)
- anything you noticed but couldn't fix (a ghost, light mismatch)

Offer variations: another scene, another format, another angle (a new `ads/<slug>/`).
