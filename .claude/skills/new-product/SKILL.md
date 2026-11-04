---
name: new-product
description: Builds a 3D model of the user's physical product from their photos, textured with the photos' own pixels, and checks it side by side with the photos. Use when the user says /new-product, wants to add a product, or their product needs fixing ("the cap is too short", "label is upside down").
---

# New product

Goal: `products/<name>/product.json` plus textures cut from the user's photos, and a check sheet the user agrees looks like their product.

The label, logo and text on the model must be **pixels from the user's photos**, only cropped, straightened or unwrapped. Never draw, generate or "clean up" a label with an image model or by painting. If a side has no photo, use the product's plain body colour there.

## 1. Collect

Ask for:
- a short name (lowercase, dashes: `oat-milk-carton`)
- what it is in a few words, which becomes `display_name` (for example "white Oatly oat milk carton"); the image model reads this
- real size in millimetres (from the pack, or a ruler; ask, don't guess)
- photos: front straight on, plus side and top if they have them. Plain background, even light, the product filling most of the frame. Phone photos are fine.

Create `products/<name>/kit/` and ask them to put the photos there (or copy files they point you to). Look at every photo.

## 2. Pick a template

Read `docs/templates.md`. Today:
- `box`: cartons, boxes, cards, flat devices
- `cylinder`: tins, cans, jars, bottles (with `profile_mm` for shoulders and necks)

If the product fits neither, say so, and offer the closest template or adding a new one (`docs/templates.md` explains how).

## 3. Cut textures from the photos

Work in `products/<name>/kit/`, keep the original photos, and write textures beside them (`front.png`, `side.png`, ...).

- **Box faces:** find each face's four corners in the photo (open the image and measure; zoom on corners). Then:
  `.venv/bin/lf texture rectify kit/front_photo.jpg --corners x1,y1,x2,y2,x3,y3,x4,y4 --size WxH --out kit/front.png`
  Corners go top-left, top-right, bottom-right, bottom-left. Pick W:H in the face's real proportions (a 70 x 120 mm face is 700x1200).
- **Round labels:** find the body's left, top, right and bottom edges in a straight-on front photo, then:
  `.venv/bin/lf texture unwrap kit/front_photo.jpg --box l,t,r,b --wrap 150 --out kit/side.png`
  and set `"wrap_deg": 150` in `product.json`. Leave `wrap_deg` at 360 only for a texture that really covers the full circumference.
- **Tops and lids:** rectify a top photo to a square; for round lids, crop to the circle.

Open each texture and check it's upright, not mirrored, and cropped to the face.

## 4. Write product.json

Follow `docs/files.md`. Example:

```json
{
  "name": "oat-milk-carton",
  "display_name": "white oat milk carton",
  "template": "box",
  "dimensions_mm": {"width": 75, "depth": 75, "height": 200},
  "faces": {"front": "kit/front.png", "right": "kit/right.png"},
  "body_color": [244, 244, 240],
  "finish": "paper"
}
```

`body_color` is the plain colour of untextured areas (sample it from a photo). `finish` is `matte`, `paper`, `glossy`, `metal` or `plastic`.

## 5. Check

Run `.venv/bin/lf product-check <name>` (about 30-60 s) and show the user `products/<name>/check/sheet.jpg`: the model from front, three-quarter and top, above their photos. Compare it yourself first: proportions, label position, orientation, colour. Fix what you see, then ask the user whether it looks like their product. Repeat until they're happy.

Common fixes: wrong proportions means wrong `dimensions_mm`; label upside down or mirrored means re-cut the texture with the corners in the right order; label off-centre on a round product means the `--box` edges were off; too shiny or flat means change `finish`.

## 6. Next

Tell them they can now run `/make-ad` with this product.
