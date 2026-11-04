"""Product templates, built inside Blender from a product.json. Origin is the base centre on z = 0, front faces -Y, metres.

Every template textures the model with the product's own photos, so labels and logos are real pixels, never drawn.

    box       cartons, boxes, cards, flat devices: dimensions_mm {width, depth, height}, faces {front, back, left, right, top, bottom}
    cylinder  tins, cans, jars, bottles: dimensions_mm {diameter, height} or profile_mm [[radius, z], ...] from the base up,
              side {texture, wrap_deg, z_from_mm, z_to_mm}, top {texture}
"""
import math
from pathlib import Path

import bpy

MM = 0.001
FINISHES = {
    "matte": {"Roughness": 0.6},
    "paper": {"Roughness": 0.75},
    "glossy": {"Roughness": 0.18, "Coat Weight": 0.35, "Coat Roughness": 0.08},
    "metal": {"Roughness": 0.3, "Metallic": 0.55},
    "plastic": {"Roughness": 0.35, "Coat Weight": 0.15},
}


def linear(rgb):
    """sRGB 0-255 to linear RGBA, for Principled base colours."""
    def ch(c):
        c = c / 255
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    return (*[ch(c) for c in rgb[:3]], 1.0)


def _socket(node, identifier):
    return next(s for s in list(node.inputs) + list(node.outputs) if s.identifier == identifier)


def material(name, color, finish, texture=None, clip=False):
    """Principled material in the product's finish. With a texture, the image is the colour; with clip, UVs outside 0-1 show color."""
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    bsdf = nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = linear(color)
    for key, value in FINISHES.get(finish, FINISHES["matte"]).items():
        if key in bsdf.inputs:
            bsdf.inputs[key].default_value = value
    if texture:
        tex = nodes.new("ShaderNodeTexImage")
        tex.image = bpy.data.images.load(str(texture), check_existing=True)
        tex.interpolation = "Cubic"
        tex.extension = "CLIP" if clip else "EXTEND"
        mix = nodes.new("ShaderNodeMix")
        mix.data_type = "RGBA"
        links.new(tex.outputs["Alpha"], _socket(mix, "Factor_Float"))
        _socket(mix, "A_Color").default_value = linear(color)
        links.new(tex.outputs["Color"], _socket(mix, "B_Color"))
        links.new(_socket(mix, "Result_Color"), bsdf.inputs["Base Color"])
    return mat


def _mesh_object(name, verts, faces, uvs, mat_index, materials, smooth=False):
    """uvs and mat_index are per face; uvs[f] lists one (u, v) per corner of faces[f]."""
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(verts, [], faces)
    layer = mesh.uv_layers.new(name="UVMap")
    for poly in mesh.polygons:
        poly.material_index = mat_index[poly.index]
        poly.use_smooth = smooth
        for corner, loop in enumerate(poly.loop_indices):
            layer.data[loop].uv = uvs[poly.index][corner]
    for m in materials:
        mesh.materials.append(m)
    mesh.validate()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    return obj


def box(spec, name):
    d = spec["dimensions_mm"]
    w, dp, h = d["width"] * MM / 2, d["depth"] * MM / 2, d["height"] * MM
    verts = [(-w, -dp, 0), (w, -dp, 0), (w, dp, 0), (-w, dp, 0), (-w, -dp, h), (w, -dp, h), (w, dp, h), (-w, dp, h)]
    # Corners in the order bottom-left, bottom-right, top-right, top-left as seen from outside, so every face image reads upright.
    faces = {"front": (0, 1, 5, 4), "back": (2, 3, 7, 6), "right": (1, 2, 6, 5), "left": (3, 0, 4, 7), "top": (4, 5, 6, 7), "bottom": (3, 2, 1, 0)}
    color, finish = spec.get("body_color", [200, 200, 200]), spec.get("finish", "paper")
    textures = spec.get("faces", {})
    mats, index = [material(f"{name}_body", color, finish)], {}
    for face in faces:
        if textures.get(face):
            index[face] = len(mats)
            mats.append(material(f"{name}_{face}", color, finish, textures[face]))
    corner_uv = [(0, 0), (1, 0), (1, 1), (0, 1)]
    obj = _mesh_object(name, verts, list(faces.values()), [corner_uv] * 6, [index.get(f, 0) for f in faces], mats)
    if bevel := spec.get("bevel_mm", 0.8):
        mod = obj.modifiers.new("bevel", "BEVEL")
        mod.width, mod.segments, mod.limit_method, mod.harden_normals = bevel * MM, 3, "ANGLE", True
        obj.data.shade_smooth()
    return obj


def cylinder(spec, name, segments=128):
    d = spec.get("dimensions_mm", {})
    profile = spec.get("profile_mm") or [[d["diameter"] / 2, 0], [d["diameter"] / 2, d["height"]]]
    profile = [(r * MM, z * MM) for r, z in profile]
    side = spec.get("side", {})
    wrap = side.get("wrap_deg", 360)
    z_from = side.get("z_from_mm", profile[0][1] / MM) * MM
    z_to = side.get("z_to_mm", profile[-1][1] / MM) * MM
    color, finish = spec.get("body_color", [200, 200, 200]), spec.get("finish", "metal")
    mats = [material(f"{name}_body", color, finish)]
    side_i = top_i = 0
    if side.get("texture"):
        side_i = len(mats)
        mats.append(material(f"{name}_side", color, finish, side["texture"], clip=wrap < 360))
    if spec.get("top", {}).get("texture"):
        top_i = len(mats)
        mats.append(material(f"{name}_top", color, finish, spec["top"]["texture"], clip=True))
    # phi is the angle from the front (-Y) towards +X, so u runs left to right as seen from the front and u = 0.5 is the front.
    phis = [-180 + 360 * k / segments for k in range(segments + 1)]
    verts, faces, uvs, mat_index = [], [], [], []
    for r, z in profile:
        for k in range(segments):
            p = math.radians(phis[k])
            verts.append((r * math.sin(p), -r * math.cos(p), z))
    ring = lambda i, k: i * segments + k % segments
    for i in range(len(profile) - 1):
        (_, z0), (_, z1) = profile[i], profile[i + 1]
        labelled = side_i and z0 >= z_from - 1e-6 and z1 <= z_to + 1e-6
        for k in range(segments):
            faces.append((ring(i, k), ring(i, k + 1), ring(i + 1, k + 1), ring(i + 1, k)))
            u0, u1 = 0.5 + phis[k] / wrap, 0.5 + phis[k + 1] / wrap
            v0, v1 = ((z0 - z_from) / (z_to - z_from), (z1 - z_from) / (z_to - z_from)) if labelled else (0, 1)
            uvs.append([(u0, v0), (u1, v0), (u1, v1), (u0, v1)])
            mat_index.append(side_i if labelled else 0)
    for cap, top in ((0, False), (len(profile) - 1, True)):
        r, z = profile[cap]
        if r <= 0:
            continue
        centre = len(verts)
        verts.append((0, 0, z))
        for k in range(segments):
            a, b = ring(cap, k), ring(cap, k + 1)
            faces.append((a, b, centre) if top else (b, a, centre))
            # Top image: front of the product at the bottom of the image.
            uv = lambda v: (0.5 + verts[v][0] / (2 * r), 0.5 + verts[v][1] / (2 * r))
            corners = (a, b, centre) if top else (b, a, centre)
            uvs.append([uv(v) for v in corners])
            mat_index.append(top_i if top else 0)
    obj = _mesh_object(name, verts, faces, uvs, mat_index, mats, smooth=True)
    # Sharp rims where the side meets a flat cap, smooth round the body.
    mod = obj.modifiers.new("rims", "EDGE_SPLIT")
    mod.split_angle = math.radians(40)
    return obj


TEMPLATES = {"box": box, "cylinder": cylinder}


def build(spec, name):
    if spec["template"] not in TEMPLATES:
        raise ValueError(f"unknown template {spec['template']!r}; have {sorted(TEMPLATES)}")
    resolved = dict(spec)
    base = Path(spec["dir"])
    for key in ("faces",):
        if key in resolved:
            resolved[key] = {f: str(base / p) for f, p in resolved[key].items() if p}
    for key in ("side", "top"):
        if resolved.get(key, {}).get("texture"):
            resolved[key] = {**resolved[key], "texture": str(base / resolved[key]["texture"])}
    obj = TEMPLATES[spec["template"]](resolved, name)
    obj["lf_product"] = True
    return obj
