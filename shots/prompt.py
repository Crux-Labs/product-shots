"""The repaint prompt: the scene the user asked for, wrapped in the rules that keep layout and product intact."""

TEMPLATE = """The first image is a rough 3D layout render. Re-shoot it as a real photograph: {scene}
Keep the camera angle, perspective, horizon line, framing, and the position and size of every object exactly as in the layout.
{products} in the masked area {verb} the real {noun}: keep {pronoun} exactly where {pronoun2} {verb} and the same size; do not redraw, restyle, move or duplicate {pronoun}, and do not add any other product, packaging, logo or text anywhere. No text, no watermark."""


def build(scene: str, product_names: list[str]) -> str:
    names = sorted(set(product_names))
    many = len(product_names) > 1
    listed = names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]
    return TEMPLATE.format(scene=scene.strip().rstrip(".") + ".", products=f"The {listed}", verb="are" if many else "is",
                           noun="products" if many else "product", pronoun="them" if many else "it", pronoun2="they" if many else "it")
