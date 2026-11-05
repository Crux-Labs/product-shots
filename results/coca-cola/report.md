# Coca-Cola benchmark: 100 briefs, three methods

**Short version:** on the classic Coca-Cola can, the image model drawing the whole ad still wins. It was ranked first on 98 of 100 briefs.

We ran the benchmark twice. The second time, the 3D can was rebuilt to fix every product fault from the first run. That more than halved layout first's bad product scores (82% → 35%), and every product pixel stayed exact (100 of 100 passed `shots verify`). It still lost almost every brief. The gap left is no longer the label. It is light, styling and framing: our cans look studio-lit and clean, while the image model's look shot on location, with condensation and hero framing.

## What we ran

- **Product:** the classic red Coca-Cola can. The reference photo is a competitor-library ad (US, "Around the World") with a hand holding the can.
- **Briefs:** 100 generated briefs. They mix 25 scenes (stadium, picnic, diner, beach, office, campfire and more), 3 camera angles, 1-3 cans and 3 formats (1:1, 4:5, 9:16). Every arm got the same brief.
- **Arms:**
  - **Image model draws the ad:** gpt-image-2.5 with the reference photo. Nothing stops it redrawing the product.
  - **Blender only:** the Blender layout render on its plain set.
  - **Layout first:** this repo. Blender layout, image model repaints outside the product, exact product put back, pixel check.
- **Judge:** Gemini 3.1 Pro, blind. It saw the reference photo, then the three ads in a random order for each brief. It scored each ad 1-10 on product, realism, brief match and appeal, said whether it would ship, and ranked the three.

## Two runs

| Run | The 3D can |
|---|---|
| 1. Old can | The label was cut from the one ad photo: 130° of the can, logo cut off ("ca-Col"), the photo's water drops and highlights baked in, glossy plastic-like material, flat grey lid. |
| 2. New can | A full 360° label drawn from the official Coca-Cola wordmark (vector). It was sized and placed by fitting it to the ad photo, and the text was measured from the same photo; the back panel is approximated. Printed-metal finish: red ink shows the aluminium, white ink doesn't, with clear varnish on top. Aluminium lid with a pull tab, bare base, turned 25° so "Coca-Co" faces the camera. |

Run 2 reused run 1's image-model ads (same reference photo, same prompts) and remade only the Blender and layout-first ads. The judge scored all three again, so the image model's scores move a little too: the judge compares the three ads against each other.

## Results (run 2, new can)

| | Image model draws the ad | Blender only | Layout first |
|---|---|---|---|
| Ranked first | **98 %** | 0 % | 2 % |
| Would ship | **78 %** | 0 % | 0 % |
| Product score (1-10) | **6.7** | 3.9 | 4.2 |
| Realism | **7.0** | 3.4 | 4.8 |
| Brief match | **6.7** | 3.3 | 6.6 |
| Appeal | **6.8** | 3.1 | 4.5 |
| Product scored 3 or less | **6 %** | 43 % | 35 % |
| Product pixels exact | not checked | yes | **100 / 100** |
| Cost per image | $0.08 | $0 | $0.09 |
| Time per image | 35 s | 78 s | 40 s |

## What the new can changed (layout first)

| | Old can | New can |
|---|---|---|
| Product score | 3.2 | **4.2** |
| Product scored 3 or less | 82 % | **35 %** |
| Realism | 4.5 | **4.8** |
| Appeal | 3.8 | **4.5** |
| Overall (mean of four scores) | 4.5 | **5.0** |
| Ranked first | 2 % | 2 % |

The judge's notes on layout first changed too. Run 1 was about the label: 49 notes on mapping or seams, 47 on a cut-off logo. In run 2, 62 of 100 notes are about light, finish or looking artificial ("lacks the condensation seen in the reference", "incorrect metallic finish").

## Product accuracy check

A second pass checked each ad on its own against the reference photo, item by item (logo, "ORIGINAL TASTE", "12 FL OZ (355 mL)", lid and tab). The image model's script logo was wrong in 43 of 100 ads and "12 FL OZ" in 49; 11 ads carried text the can doesn't have (mostly "Delicious & Refreshing" moved to the front); 40% of its ads were right on every item. Layout first scored lower on this check (13%), but not because pixels changed: our can is a rebuild from the wordmark, not the real print file, so the checker counts our label's differences from the photo, and reads the logo bending round the can as "cut off". The four made-up products in [../report.md](../report.md) don't have that problem, because there the 3D model is built from the reference itself.

## Why layout first still loses here

1. **Studio light on a location photo.** The can keeps the light Blender gave it, and the image model only repaints around it. On a sunny picnic table or a stadium at sunset, the can is still lit like a studio packshot. The image model, drawing everything at once, lights the can with the scene.
2. **No styling.** The reference photo, like most Coke ads, has a cold can covered in condensation. Our can is clean and dry, and the judge marked that down against the reference.
3. **Reflections of the wrong room.** Metal reflects what's around it. Our can reflects the plain Blender set, which shows up as odd colours on the rim (green on the stadium grass).
4. **Smaller, less heroic framing.** The benchmark's layouts use one camera recipe per angle, so the cans often sit small in the frame. The image model fills the frame with the can.
5. **The famous-product effect.** Coca-Cola is probably the most-drawn can there is, so the image model draws it well. It still slipped: 10 of its 100 notes mention a garbled or cut-off logo, and 6% of its ads scored 3 or less on product. On less famous products, earlier tests showed much more of this. This benchmark doesn't measure that case.

## What would close the gap

- **Relight the product to the scene:** estimate the room's light from the repainted image and render the product again under it (an environment map from the repaint), or add a lighting-match step before compositing.
- **Use the repaint as the reflection source,** so metal and gloss reflect the room the can is in.
- **Styling layers in 3D:** condensation drops as a Blender material on the can, never painted by the image model.
- **Hero camera framing** in the layout step: fill the frame the way a product photographer would.

## Reproduce

```bash
.venv/bin/shots bench briefs coca-cola --n 100
.venv/bin/shots bench run coca-cola --workers 4
.venv/bin/shots bench judge coca-cola --workers 4
.venv/bin/shots bench report coca-cola --out results/coca-cola
```

Brand images aren't in the repo. To rerun, build `products/coca-cola/` with `/new-product`, ideally from the flat label artwork. The numbers for both runs are in `summary.json` (new can) and `summary_old_kit.json` (old can).
