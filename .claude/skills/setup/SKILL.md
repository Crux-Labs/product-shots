---
name: setup
description: First-time setup for layoutfirst. Installs the Python environment, finds or installs Blender, gets the user's image-model API key into .env, and makes a demo ad to prove everything works. Use when the user says /setup, "set me up", "install", or when `lf doctor` reports something missing.
---

# Setup

Goal: in a few minutes the user sees a finished demo ad made on their machine. Talk in plain words; they may not be a developer. Say what each step is for before running it.

## 1. Python environment

Run `./scripts/setup.sh`. It creates `.venv`, installs the package, draws the demo product art, creates `.env` from `.env.example` if missing, and ends with a `lf doctor` JSON report.

If it fails on Python, tell the user which version was found and how to get 3.10+ (on a Mac: `brew install python`).

## 2. Blender

Read `blender` in the doctor report.
- `ok: true`: say which Blender was found and move on.
- Missing or older than 4.2: explain that Blender renders the product, and that you can download a portable copy into this folder (about 300 MB, nothing installed system-wide). **Ask before downloading.** On yes, run `./scripts/get_blender.sh`, then `.venv/bin/lf doctor` again.
- On Windows, or if the download fails, point them to blender.org and ask for the install path, then they add `BLENDER_PATH=...` to `.env`.

## 3. API key

If `keys` shows no key: explain that one image-model call repaints the room around the product, and that they need an OpenAI key (platform.openai.com/api-keys) or a Gemini key (aistudio.google.com/apikey). Each ad costs about $0.05-0.15.

Ask them to open `.env` in this folder, paste the key after `OPENAI_API_KEY=` (or `GEMINI_API_KEY=`), save, and tell you when done. **Do not read, print or edit `.env` yourself** and don't ask them to paste the key into the chat; if they paste it anyway, tell them to put it in `.env` and suggest rotating it later. Then re-run `.venv/bin/lf doctor` and confirm the key is found (it only reports true/false).

## 4. Demo ad

Tell the user this makes one real ad of two made-up products (about 2-3 minutes, about $0.09), then run:

```
.venv/bin/lf ad examples/demo-tin/ads/counter/ad.json
```

When it finishes, show `examples/demo-tin/ads/counter/out/guide.png` (the Blender layout) and `out/final.png` (the result) and explain the difference in one or two sentences: the room was repainted, the products are the exact Blender pixels (`product_pixels_from_model: 0`). Report the cost and time from the output.

## 5. Next

Tell them the next step is `/new-product`: they put 2-5 photos of their own product (front, side, top) in a folder and you build the 3D model.

## If something breaks

- `Blender failed`: read the log path in the error, explain the cause in one line, fix it if you can (wrong path, too-old version).
- Key errors (401, quota): the key is wrong or has no credit; say so plainly.
- Run `.venv/bin/python -m pytest -q` to check the install when unsure.
