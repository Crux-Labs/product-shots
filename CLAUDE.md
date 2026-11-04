# layoutfirst

This repo makes product ads where Blender renders the product and an image model repaints only the surroundings. Users run it through three skills: `/setup`, `/new-product`, `/make-ad`. Most users are not developers: explain each step in plain words, show images as soon as they exist, and fix problems yourself instead of pasting stack traces.

## Rules

- **Never let an image model draw the product.** No prompt, tool or workaround may generate or edit product pixels: no "make the label clearer", no upscaling or retouching the product, no generating a packshot. Product pixels come only from the user's photos, through the 3D model. If an ad can't be made this way, say so.
- **`lf verify` must pass** before you call an ad finished. If it fails, the image is not deliverable; find out why, don't hide it.
- **Never read or print `.env`.** It holds the user's API key. `lf doctor` reports whether a key is present without showing it. The user pastes the key into `.env` themselves.
- **Work through the `lf` command** (`.venv/bin/lf`). Don't reimplement its steps in ad-hoc scripts. If `lf` lacks something, add it to `lf/` with a test.
- **Ask before downloading Blender** (about 300 MB) and before any paid call beyond the one the user asked for. Report the cost of every ad (`cost_usd` in the output).

## Where things go

- `products/<name>/`: the user's products, git-ignored. `product.json`, `kit/` (their photos and the textures cut from them), `check/` (check sheets), `ads/<slug>/ad.json` with results in `ads/<slug>/out/`.
- `examples/`: made-up demo products. Don't put real brands here.
- `lf/`: the Python package. `lf/bpy/` runs inside Blender; everything else runs in `.venv`.
- File formats are in `docs/files.md`; templates in `docs/templates.md`.

## Commands

```
.venv/bin/lf doctor
.venv/bin/lf product-check <product>
.venv/bin/lf ad <ad.json> [--provider openai|gemini] [--skip-layout]
.venv/bin/lf layout|repaint|composite|verify <ad.json>
.venv/bin/lf texture rectify|unwrap <photo> ...
.venv/bin/python -m pytest -q
```
