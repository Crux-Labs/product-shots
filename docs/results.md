# Why layout first

We remade 12 live ads from three consumer brands (supplements, storage, confectionery) and scored them blind with five model judges: realism, two product-fidelity checks, art direction, and performance. Each judge also said whether they'd run the ad as-is ("ship vote").

Four approaches, judged side by side on the 7 ads without hands:

| Approach | How | Ads won | Ship votes (of 35) | Mean score |
|---|---|---|---|---|
| **Layout first** (this repo) | Blender product, camera and light; image model repaints the room; exact product put back | **3 (43%)** | **18** | **6.41** |
| Image model draws the ad | Model draws the whole ad from a packshot, or pastes a cut-out on an AI background | 1.5 (21%) | 13 | 5.31 |
| Blender only | Everything rendered in 3D, no AI | 1.5 (21%) | 10 | 5.63 |
| Plate first | Model paints an empty room, Blender lights the product to match it | 1 (14%) | 3 | 5.20 |

What each one got wrong:
- **Model draws the product:** in 4 of 12 ads the model drew the product itself, and 3 of those had a garbled logo, an outdated logo or the product at twice its real size.
- **Cut-out pasted on AI background:** labels exact, but wrong perspective, no contact shadow, studio light in a lifestyle scene.
- **Blender only:** product right, room and props look CG.
- **Plate first:** brand colours went dull under the room's light, and products came out small.

Limits: model judges, not people or live ad spend; one round, 7-12 ads. Products held in hands were tested separately and are not solved: two of three hand ads got ship votes with a variant of this pipeline, the third none.

## Coca-Cola benchmark (100 briefs)

A larger, single-product run went the other way: the image model drawing the whole ad was ranked first on 98% of 99 briefs, layout first on 2%. Layout first kept every product pixel exact, but those pixels came from a 3D model built from one hand-held ad photo: a cut-off logo, a label covering 130° of the can, and the photo's light baked in. A famous product is also the image model's best case. Details: [results/coca-cola/report.md](../results/coca-cola/report.md).
