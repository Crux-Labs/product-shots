# Templates

A template turns a `product.json` into a Blender object. It lives in `shots/bpy/templates.py` and gets the product spec with texture paths already made absolute.

## box

Six faces, each its own texture, with bevelled edges. Each face image is shown upright as seen from outside: front, back, left and right with the top of the image up; top with the front edge at the bottom of the image.

Good for cartons, boxes, cards, phones, flat devices.

## cylinder

A body of revolution. With `dimensions_mm` it's a straight cylinder; with `profile_mm` you describe the silhouette as `[radius, z]` points from the base up, which gives bottles, jars and tubs.

The side texture is wrapped round the body: `u = 0.5` is the front, `wrap_deg` sets how much of the circumference one image covers. A label cut from one front photo covers about 150°; the rest shows `body_color`.

Good for tins, cans, jars, bottles, tubs.

## Adding a template

1. Write a function `name(spec, obj_name)` in `shots/bpy/templates.py` that builds a mesh with UVs and returns the object, origin at the base centre, front facing -Y, metres. Use `material()` for textured and plain materials so finishes stay consistent.
2. Register it in `TEMPLATES`.
3. Make texture paths absolute in `build()` if it adds new texture fields.
4. Add a made-up example under `examples/` and a check sheet in your PR.

Wanted: pouch (stand-up bag), tube (squeeze tube with crimp), bottle with a separate cap object, blister card.
