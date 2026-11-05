# Coca-Cola benchmark: 100 briefs, three methods

**Short version:** the image model drawing the whole ad won 97 of 99 briefs. Layout first kept every product pixel exact (99 of 99 passed `shots verify`) and beat Blender alone 97 times out of 99. But the product it kept exact came from a weak 3D model, and the judge marked it down for that. **The method held. The kit was the ceiling.**

## What we ran

- **Product:** the classic red Coca-Cola can. The 3D model was built from a single competitor-library ad (US, "Around the World"), where a hand holds the can.
- **Briefs:** 100 generated briefs. They mix 25 scenes (stadium, picnic, diner, beach, office, campfire and more), 3 camera angles, 1-3 cans and 3 formats (1:1, 4:5, 9:16). Every arm got the same brief.
- **Arms:**
  - **Image model draws the ad:** gpt-image-2.5 with a photo of the can as reference. Nothing stops it redrawing the product.
  - **Blender only:** the Blender layout render on its plain set.
  - **Layout first:** this repo. Blender layout, image model repaints outside the product, exact product put back, pixel check.
- **Judge:** Gemini 3.1 Pro, blind. The three images were shuffled for each brief. It scored each image 1-10 on product, realism, brief match and appeal, said whether it would ship, and ranked the three.
- **Kept:** 99 briefs. One layout-first image failed to generate, so that brief was dropped for every arm.

## Results

| | Image model draws the ad | Blender only | Layout first |
|---|---|---|---|
| Ranked first | **98 %** | 0 % | 2 % |
| Would ship | **66 %** | 0 % | 0 % |
| Product score (1-10) | **5.9** | 3.1 | 3.2 |
| Realism | **7.0** | 3.1 | 4.5 |
| Brief match | **6.8** | 3.4 | 6.6 |
| Appeal | **6.4** | 3.0 | 3.8 |
| Product scored 3 or less | 27 % | 85 % | 82 % |
| Product pixels exact | not checked | yes | **99 / 99** |
| Cost per image | $0.08 | $0 | $0.09 |
| Time per image | 35 s | 92 s | 55 s |

The whole run cost about $16 in image calls, plus the judge calls, which weren't logged. It took about 2 h 45 min on one Mac.

## Why layout first lost here

The judge's "worst issue" notes tell the story. For layout first, 49 of 99 notes mention label mapping, a seam or an edge, and 47 mention a cut-off or garbled logo.

1. **The source photo shows only part of the logo.** The hand-held can in the ad reads "ca-Col": the script logo is wider than the side facing the camera. The texture copies that faithfully, so every can we render reads "ca-Co". The image model, given the same photo, sometimes fills in the full "Coca-Cola" from memory. That is why its product score is higher, even though 23 of its notes also flag a cut-off logo.
2. **The label covers only 130° of the can.** The rest of the can is plain red. Turn the can slightly, as the high and low camera angles do, and a hard edge shows where the photo ends.
3. **The photo's light is baked in.** Water drops, highlights and the ad's colour grade are part of the texture. Blender then lights them again, so the cans look washed-out and pinkish, and don't sit in the repainted room's light.

None of this is a pixel-check failure. The guarantee worked: the product is exactly what the 3D model rendered. The 3D model was simply not good enough to sell.

## What this means

- **Layout first is only as good as the product model.** On our earlier tests the kits came from clean, flat-on product photos, and layout first won. One hand-held ad photo of a round can isn't enough.
- **The image model does well on famous products.** Coca-Cola is probably the most-drawn can in its training data. On lesser-known products, earlier tests showed it inventing logos and changing sizes. This benchmark doesn't test that case.
- **Blender alone never shipped.** Layout first beat it on 97 of 99 briefs, mostly on brief match (6.6 vs 3.4) and realism.

## What would make this a fair rerun

- **A real label:** the flat 360° label artwork, or 3-4 photos of the can turned by about 90° each, stitched together. Either gives the full logo and no seam.
- **Light-neutral texture:** photos without water drops or strong highlights, so Blender's light is the only light.
- **Match light to the room:** relight the product layer to the repainted room before compositing. This is the open weak spot from the earlier tests.

## Update: the can model is rebuilt

After this run, the can was rebuilt the way the list above describes:
- **Label:** a full 360° flat label drawn from the official Coca-Cola wordmark (vector), sized and placed by fitting it to the ad photo. The text was measured from the same photo. The back panel is approximated.
- **Material:** printed metal. Red ink lets the aluminium shine through, white ink doesn't, and a clear varnish sits on top.
- **Shape:** a bare aluminium lid with a pull tab and rivet, and a bare base.
- **Light:** a brighter-overhead environment, so the metal has something to reflect.
- **Angle:** the can is turned 25° so "Coca-Co" faces the camera.

The benchmark above still shows the old model. A rerun with the new one hasn't been done yet.

## Reproduce

```bash
.venv/bin/shots bench briefs coca-cola --n 100
.venv/bin/shots bench run coca-cola --workers 4
.venv/bin/shots bench judge coca-cola --workers 4
.venv/bin/shots bench report coca-cola --out results/coca-cola
```

Brand images aren't in the repo. To rerun, build `products/coca-cola/` from your own photos with `/new-product`.
