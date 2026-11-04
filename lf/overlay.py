"""Optional ad copy: an HTML file the size of the image, with a transparent background, set by a real browser over the plate.

Needs the overlay extra: pip install -e '.[overlay]' && playwright install chromium
"""
from pathlib import Path

from PIL import Image


def apply(plate: Path, html: Path, out: Path) -> Path:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as e:
        raise SystemExit("Text overlay needs Playwright: pip install -e '.[overlay]' && playwright install chromium") from e
    base = Image.open(plate).convert("RGBA")
    layer_path = out.with_name(out.stem + "_text.png")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--allow-file-access-from-files"])
        page = browser.new_page(viewport={"width": base.width, "height": base.height})
        page.goto(html.resolve().as_uri())
        page.evaluate("document.fonts.ready")
        page.wait_for_timeout(300)
        page.screenshot(path=str(layer_path), omit_background=True)
        browser.close()
    Image.alpha_composite(base, Image.open(layer_path).convert("RGBA")).convert("RGB").save(out)
    return out
