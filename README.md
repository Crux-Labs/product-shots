# product-shots

Make product ads with AI **without letting AI touch your product.**

Blender places your real product, an image model paints the room around it, and the exact product pixels go back on top. Every image is checked: not one product pixel may change.

![Blender layout on the left, finished ad on the right](docs/img/demo_before_after.jpg)

*Left: the Blender layout. Right: the finished image. The tin and the box are the same pixels in both.*

## Why

There are two obvious ways to make a product ad with software, and each fails in its own way:

| | **Image model draws the whole ad** | **Blender renders the whole ad** |
|---|---|---|
| How | Give the model a product photo and a brief | Build the product and the scene in 3D |
| Great at | Real-looking rooms, light, mood, people | Exact product: right label, size and angle |
| Breaks on | **The product.** It redraws it: garbled logos, outdated logos, invented products, wrong sizes | **Everything else.** Rooms, props and hands look CG, and every scene is built by hand |

**product-shots splits the job.** Each tool does only the part it's good at:

| Step | Who does it | Why |
|---|---|---|
| Product, camera, framing, product light | Blender | It can't get the product wrong: it only uses your photos |
| Room, surface, background, mood | Image model | It makes believable photos |
| Final product pixels | Copied from Blender | So the model's version of your product is thrown away |

We call this **layout first**: the layout comes from Blender, the image model fills in around it.

## How it works

```
 your product photos ─► 3D model of your product (textures are your photos' pixels)
                                   │
 your brief ─► ad.json ─► 1. Blender layout ──► guide.png ─► 3. image model repaints the room ─┐
                                   ├──────────► layer.png  (product + its shadow) ─────────────┼─► 4. put product back ─► 5. verify ─► final.png
                                   └──────────► 2. mask.png (product outline: "do not change")─┘
```

1. **Blender layout.** Your product model, the camera, framing and product lighting, set up to sell the product. The room in this render is only a rough guide. Blender writes three images: the whole scene, the product with the shadows it casts, and a product mask.
2. **Mask.** The product outline, grown by about 6 px, is marked "do not change".
3. **Image model repaint.** One edit call re-shoots everything outside the mask as a real photo: wood grain, tiles, window light, shallow focus, calm space for a headline. The prompt says to keep the camera, horizon and every object's size and position, and to add no product, logo or text. About 30-40 s and $0.05-0.12 per image.
4. **Exact product put back.** The Blender product and its shadow go back on top. The blend happens in linear light, so shadows keep their real darkness.
5. **Verify.** The saved image is read back and every product pixel is compared with the Blender render. One changed pixel fails the run.

Details: [docs/how-it-works.md](docs/how-it-works.md).

## What we learned

We tested this against the two obvious approaches, and against the reverse order, on live ads from real brands, judged blind. Full write-up: [docs/results.md](docs/results.md).

- **Image model alone:** the most photographic results, and the riskiest. On lesser-known products it drew a misspelt brand logo, an outdated logo on a product that doesn't exist, and a memory card at twice its real size. On a world-famous product with a clean reference (a Coca-Cola can) it copies the label very well. You never know which you'll get, so every image needs a person to check the product.
- **Blender alone:** the product is always right, and simple graphic scenes work. Rooms, props and hands look like a render, and building each scene is slow.
- **Plate first** (the model paints an empty room, then Blender lights the product to match it): came last. Lighting the product from the room dulled brand colours, and the room's scale shrank the products.
- **Layout first** (this repo): won the blind test on ads from three brands whose 3D models came from clean product photos. The product is guaranteed, and the room looks real. It lost the Coca-Cola benchmark below, a world-famous product the image model draws well, where our studio-lit can looked pasted into location scenes.
- **Its weak spots:** the 3D model is the ceiling (a cut-off logo, a label that only covers the front, or light baked into the photo all show up, exactly), the image model sometimes redraws the product slightly bigger behind ours (a faint "ghost" edge), and products keep their Blender light, so a hard-sun room can look mismatched.

### Coca-Cola benchmark

<!-- BENCH:START -->
100 generated briefs for the classic Coca-Cola can, three arms, judged blind by Gemini 3.1 Pro:

| | Image model draws the ad | Blender only | Layout first |
|---|---|---|---|
| Ranked first | **98 %** | 0 % | 2 % |
| Would ship | **78 %** | 0 % | 0 % |
| Product score (1-10) | **6.7** | 3.9 | 4.2 |
| Realism (1-10) | **7.0** | 3.4 | 4.8 |
| Product pixels exact | not checked | yes | **100 / 100** |
| Cost per image | $0.08 | $0 | $0.09 |

**The image model won this one.** We ran it twice. The first can model was cut from one hand-held ad photo, with a cut-off logo and the photo's light baked in. Rebuilding it from a full vector label with a printed-metal finish more than halved layout first's bad product scores (82% → 35%), but it didn't change the result. What's left is light and styling. Our can keeps its studio light and stays dry. The image model lights the can with the scene and adds condensation, on a product it has seen countless times. Full write-up, both runs and what would close the gap: [results/coca-cola/report.md](results/coca-cola/report.md).
<!-- BENCH:END -->

## Quickstart

You need [Claude Code](https://claude.com/claude-code), Python 3.10+, and an OpenAI or Gemini API key, on macOS (Apple silicon) or Linux. Blender is downloaded into the folder for you if it's missing. On Windows, use WSL or install Blender yourself.

```bash
git clone https://github.com/Crux-Labs/product-shots
```

```bash
cd product-shots && claude
```

The first time, Claude Code asks whether you trust this folder. Say yes: that turns on the repo's pre-approved commands, so you aren't asked to approve every step. Then type:

| Command | What happens |
|---|---|
| `/setup` | Installs everything, asks you to paste one API key into `.env`, and makes a demo ad so you see it work (about 3 minutes, about $0.09). |
| `/new-product` | You put 2-5 photos of your product in a folder. Claude builds the 3D model from them and shows it next to your photos to check. |
| `/make-ad` | Describe the ad in plain words. You get the finished image, the steps, and what it cost. |

## What works today

- **Products:** boxes, cartons, tins, cans, jars, bottles, cards and other simple shapes with printed labels. Templates: `box` and `cylinder` (with a profile for bottles, jars and cans). See [docs/templates.md](docs/templates.md).
- **Not yet:** pouches, tubes, odd shapes (each needs a template), products held in hands, and text overlay without the optional Playwright install.

## Without Claude Code

Everything Claude does goes through the `shots` command:

```bash
./scripts/setup.sh
```

```bash
.venv/bin/shots ad examples/demo-tin/ads/counter/ad.json
```

`shots --help` lists every command, including `shots bench` for running the three-way benchmark on your own product. File formats: [docs/files.md](docs/files.md).

## License

GPL-3.0. The scripts in `shots/bpy/` run inside Blender and use its Python API, which is GPL.
