# How it works

```
product photos ──► 3D model (textures = photo pixels)
                         │
ad.json ──► Blender ──► guide.png ──► image model edit ──► repaint.png ─┐
                    ├─► layer.png (product + its shadow) ───────────────┼─► composite ──► verify ──► final.png
                    └─► mask.png (product alpha) ───────────────────────┘
```

**1. Blender layout** (`shots layout`, `shots/bpy/build.py`). Builds the products from their templates, a floor and wall in roughly the scene's colours, a camera and lights, and renders three passes in one go:
- `guide.png`, the whole scene.
- `layer.png`, with every non-product object turned into a shadow catcher, so only the products and the shadows they cast remain.
- `mask.png`, with every non-product object as a holdout, so only product alpha remains.

**2. Repaint** (`shots repaint`, `shots/repaint.py`). One image-edit call. For OpenAI, the edit mask keeps the product (grown by about 6 px) fixed. Gemini has no mask input, so it gets the guide and the rules in the prompt; its product pixels are discarded anyway. The prompt (`shots/prompt.py`) asks for a real photograph of the described scene, keeping camera, horizon, framing and every object's size and position, and adding no product, logo or text.

**3. Composite** (`shots composite`, `shots/composite.py`). The product layer goes over the repainted room in linear light, which is how a shadow catcher's alpha is meant to be read; in sRGB the shadows come out far too dark. Shadow alpha is kept only near the product, so shadows from the rough CG set don't land on the new room. Where the mask is full, product pixels are copied byte for byte.

**4. Verify** (`shots verify`). Reads the saved image back from disk and compares every full-mask pixel with `layer.png`. Any difference fails the run. The 1-2 px anti-aliased edge blends, as any cut-out does.

## Why the product keeps its Blender light

The product is lit in Blender and never relit to match the repainted room. We tried the opposite order (model paints an empty room, Blender lights the product from it) and it scored worst in a blind test: matching the room's light dulled brand colours and the room's scale shrank products. See [results.md](results.md). The trade-off: if the model invents a strong light (hard sun) the product, lit softly, can look slightly off. Set `light.key_azimuth_deg` to where the window will be.
