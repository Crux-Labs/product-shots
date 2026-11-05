"""Draws the made-up benchmark products once with the image model: front and back photos, or flat print artwork.

    python examples/draw_products.py OUT_DIR [job ...]

Each image then is the product, the way a brand's own photos or print files are. Ads never ask an image model to draw it again.
"""
import base64, io, json, sys, time
from pathlib import Path
from openai import OpenAI
from PIL import Image

OUT = Path(sys.argv[1]); OUT.mkdir(parents=True, exist_ok=True)
MODEL = "gpt-image-2.5-sunburst"
COMMON = ("Product design reference image. Perfectly straight-on orthographic view, exactly perpendicular to the camera, "
          "no perspective, not tilted or rotated, centred, on a pure white #FFFFFF background with no shadow, soft even studio "
          "lighting with no glare or reflections. Photorealistic, razor sharp, every small detail and letter crisp and legible.")
FLAT = ("Flat print-ready packaging artwork, perfectly flat and straight-on like a printer's proof, filling the whole image edge to edge "
        "with no background, no border, no mockup, no perspective, no shadows or lighting. Crisp vector-sharp graphics, every small "
        "letter crisp and legible.")
JOBS = {
 "phone_back": ("1152x2048", None,
   "The back of a fictional smartphone called the Orra One, filling 90% of the image height. Its back is frosted matte glass "
   "in a deep sage green, with rounded corners and a thin satin aluminium frame in the same green just visible around the edge. "
   "Top-left corner: a rounded-square camera island in slightly darker sage green holding three large black camera lenses with fine "
   "concentric metal rings in a triangle, a small round LED flash and a tiny microphone hole; tiny white text '50MP  f/1.8' printed "
   "on the island. Centre of the back: the lowercase wordmark 'orra' in a clean geometric sans-serif, glossy tone-on-tone. "
   "Near the bottom, centred, two lines of small light grey text: 'Designed by Orra in Lisbon' and 'Model OR-1  ·  256 GB'."),
 "phone_front": ("1152x2048", "phone_back",
   "The front of the same Orra One smartphone shown in the image (same size, same rounded corners, same sage green frame), filling 90% "
   "of the image height. Black glass front with very thin even black bezels and a small round punch-hole camera centred near the top. "
   "The screen is on, showing a lock screen: a soft abstract wallpaper of flowing sage green and peach waves; near the top the date "
   "'Tuesday 5 November' in small white text and below it a large thin white clock '9:41'; a status bar with signal, wifi and battery "
   "icons; a round flashlight button at bottom left and a round camera button at bottom right; a thin white home bar at the bottom."),
 "card_front": ("2048x1312", None,
   "The front of a fictional premium credit card from Kestrel Bank, card shape 85.6 x 54 mm with small rounded corners, filling 90% of "
   "the image width. Deep navy matte card with a very subtle fine diagonal line texture. Top left: a minimal geometric kestrel bird "
   "logo in brushed gold next to the wordmark 'KESTREL' in spaced gold capitals. Left, middle: a gold EMV chip with detailed contact "
   "pads, and a contactless wave symbol to its right. Across the lower middle in silver: the number '8812 4471 0093 5526' (sixteen digits, the last one a 6), below it "
   "the small label 'VALID THRU' and '08/29', and the cardholder name 'JORDAN ELLIS'. Top right: 'Reserve' in small gold italic. "
   "Bottom right: a made-up payment network mark: a small gold four-pointed star inside a thin gold rounded square outline, with the word 'NOVA' in silver capitals beside it."),
 "card_back": ("2048x1312", "card_front",
   "The back of the same Kestrel Bank credit card shown in the image (same navy colour, same size and rounded corners), filling 90% of "
   "the image width. A black magnetic stripe across the full width near the top. Below it a white signature strip with a faint "
   "diagonal pattern and the digits '417' in a small white box at its right end. A small silver holographic kestrel bird sticker at "
   "the right. Small white text at the bottom left in three lines: 'This card is issued by Kestrel Bank plc and remains its property.', "
   "'If found, please return to Kestrel Bank, PO Box 1200, Leeds LS1 4AB.' and 'Customer service +44 20 7946 0123  ·  kestrel.example'. "
   "The small gold 'KESTREL' wordmark at the top right above the stripe."),
 "serum_front": ("768x2048", None, "FLAT:"
   "The front panel of a tall skincare carton for a fictional brand, Lumea. Soft warm ivory background with a large pale apricot "
   "circle rising behind the text. Near the top the wordmark 'LUMEA' in elegant thin spaced serif capitals in deep terracotta. Below "
   "it, centred: 'Vitamin C' in large terracotta serif, 'Brightening Serum' in smaller dark grey sans-serif, then a thin terracotta "
   "line, then '15% Vitamin C + Ferulic Acid' in small grey text. Near the bottom: three tiny line icons (a leaf, a drop, a sun) with "
   "the words 'Vegan  ·  Fragrance free  ·  Daily' under them, and at the very bottom '30 ml  e  1.0 fl oz'."),
 "serum_side": ("768x2048", "serum_front", "FLAT:"
   "The side panel of the same Lumea carton shown in the image, same ivory background and terracotta colours. The word 'LUMEA' "
   "running vertically up the panel in large thin spaced serif capitals, and at the bottom, horizontal, small grey text in three "
   "lines: 'Dermatologist tested', 'Made in France', 'lumea.example'."),
 "serum_back": ("768x2048", "serum_front", "FLAT:"
   "The back panel of the same Lumea carton shown in the image, same ivory background and terracotta colours. At the top the small "
   "wordmark 'LUMEA'. Then a heading 'How to use' in terracotta with two lines of small grey text: 'Apply 3-4 drops to clean skin "
   "every morning.' and 'Follow with moisturiser and SPF.' Then a heading 'Ingredients' with a paragraph of tiny grey text: 'Aqua, "
   "Ascorbic Acid, Propanediol, Glycerin, Ferulic Acid, Tocopherol, Sodium Hyaluronate, Panthenol, Citric Acid, Xanthan Gum.' Near "
   "the bottom a black EAN barcode with the digits '5 012345 678900' under it, a small recycling symbol, and 'Lumea Ltd, 12 Rue "
   "Fictive, 75003 Paris'."),
 "coffee_label": ("2048x848", None, "FLAT:"
   "The full wrap-around label of a fictional coffee tin, Harbor & Pine, laid flat. Deep navy background. In the centre third: a "
   "cream circular emblem with a small lighthouse and two pine trees drawn in navy line art, the brand 'HARBOR & PINE' in cream "
   "slab-serif capitals under it, 'Coffee Roasters' in small copper script, then 'MORNING TIDE' in large cream capitals and "
   "'Medium roast  ·  Whole bean' in small copper text, and 'NET WT 12 OZ (340 g)' at the bottom. The left third: tasting notes in "
   "cream, a heading 'Tasting notes' and the lines 'Milk chocolate', 'Toasted hazelnut', 'Orange zest'. The right third: 'Roasted in "
   "Portland, Maine', 'Single origin  ·  Colombia Huila', 'Roast date ____' in small cream text, and a small cream barcode. Thin copper "
   "pinstripes run along the top and bottom edges."),
 "coffee_lid": ("1024x1024", "coffee_label", "FLAT:"
   "The round lid of the same Harbor & Pine coffee tin shown in the image, seen from straight above, a perfect circle filling the "
   "image edge to edge with pure white outside the circle. Brushed copper metal lid with the cream lighthouse-and-pines emblem in the "
   "centre and 'HARBOR & PINE' around the rim in navy capitals."),
}
client = OpenAI()
for name in (sys.argv[2:] or JOBS):
    size, ref, prompt = JOBS[name]
    t0 = time.time()
    full = f"{prompt[5:]} {FLAT}" if prompt.startswith("FLAT:") else f"{prompt} {COMMON}"
    if ref:
        b = io.BytesIO(); Image.open(OUT / f"{ref}.png").save(b, "PNG"); b.seek(0); b.name = "ref.png"
        r = client.images.edit(model=MODEL, image=b, prompt=full, size=size, quality="high", n=1)
    else:
        r = client.images.generate(model=MODEL, prompt=full, size=size, quality="high", n=1)
    Image.open(io.BytesIO(base64.b64decode(r.data[0].b64_json))).save(OUT / f"{name}.png")
    u = r.usage.model_dump() if r.usage else {}
    print(json.dumps({"name": name, "seconds": round(time.time() - t0), "out_tokens": u.get("output_tokens")}), flush=True)
