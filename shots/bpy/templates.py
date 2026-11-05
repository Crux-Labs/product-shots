"""Product templates, built inside Blender from a product.json. Origin is the base centre on z = 0, front faces -Y, metres.

Every template textures the model with the product's own photos, so labels and logos are real pixels, never drawn.

    box       cartons, boxes, cards, flat devices: dimensions_mm {width, depth, height}, faces {front, back, left, right, top, bottom}
    cylinder  tins, cans, jars, bottles: dimensions_mm {diameter, height} or profile_mm [[radius, z], ...] from the base up,
              side {texture, wrap_deg, turn_deg, z_from_mm, z_to_mm}, top {texture and/or color, finish, from_mm, tab},
              bottom {color, finish, to_mm}
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
    # Bare can or tin metal, and ink printed on it under a clear varnish (drinks cans, printed tins).
    "aluminium": {"Roughness": 0.2, "Metallic": 1.0},
    "printed_metal": {"Roughness": 0.22, "Metallic": 1.0, "Coat Weight": 0.6, "Coat Roughness": 0.04},
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
        if finish == "printed_metal":
            # Coloured ink is thin, so the metal shines through it; white and black inks are opaque, so no metal there.
            hsv = nodes.new("ShaderNodeSeparateColor")
            hsv.mode = "HSV"
            links.new(tex.outputs["Color"], hsv.inputs["Color"])
            ramp = nodes.new("ShaderNodeMapRange")
            ramp.inputs["From Min"].default_value, ramp.inputs["From Max"].default_value = 0.2, 0.6
            links.new(hsv.outputs["Green"], ramp.inputs["Value"])
            links.new(ramp.outputs["Result"], bsdf.inputs["Metallic"])
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
    # turn_deg: which part of the label faces the camera at rotation 0; negative brings the label's left side round to the front.
    turn = side.get("turn_deg", 0)
    z_from = side.get("z_from_mm", profile[0][1] / MM) * MM
    z_to = side.get("z_to_mm", profile[-1][1] / MM) * MM
    color, finish = spec.get("body_color", [200, 200, 200]), spec.get("finish", "metal")
    mats = [material(f"{name}_body", color, finish)]
    side_i = 0
    if side.get("texture"):
        side_i = len(mats)
        mats.append(material(f"{name}_side", color, finish, side["texture"], clip=wrap < 360))
    top, bottom = spec.get("top", {}), spec.get("bottom", {})
    cap_i = band_i = bottom_i = 0
    if top.get("color"):
        # A bare lid (a can's aluminium end) is a plain material, not a label; it also covers the neck and rim (from_mm).
        band_i = cap_i = len(mats)
        mats.append(material(f"{name}_lid", top["color"], top.get("finish", finish)))
    if top.get("texture"):
        cap_i = len(mats)
        mats.append(material(f"{name}_top", top.get("color", color), top.get("finish", finish), top["texture"], clip=True))
    if bottom.get("color"):
        bottom_i = len(mats)
        mats.append(material(f"{name}_bottom", bottom["color"], bottom.get("finish", finish)))
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
        # top.from_mm: everything from that height up (a can's neck and rim) takes the lid's material; bottom.to_mm likewise below.
        lid_band = band_i and top.get("from_mm") is not None and z0 >= top["from_mm"] * MM - 1e-6
        base_band = bottom_i and bottom.get("to_mm") is not None and max(z0, z1) <= bottom["to_mm"] * MM + 1e-6
        for k in range(segments):
            faces.append((ring(i, k), ring(i, k + 1), ring(i + 1, k + 1), ring(i + 1, k)))
            u0, u1 = 0.5 + (phis[k] + turn) / wrap, 0.5 + (phis[k + 1] + turn) / wrap
            v0, v1 = ((z0 - z_from) / (z_to - z_from), (z1 - z_from) / (z_to - z_from)) if labelled else (0, 1)
            uvs.append([(u0, v0), (u1, v0), (u1, v1), (u0, v1)])
            mat_index.append(side_i if labelled else band_i if lid_band else bottom_i if base_band else 0)
    for cap, is_top in ((0, False), (len(profile) - 1, True)):
        r, z = profile[cap]
        if r <= 0:
            continue
        centre = len(verts)
        verts.append((0, 0, z))
        for k in range(segments):
            a, b = ring(cap, k), ring(cap, k + 1)
            faces.append((a, b, centre) if is_top else (b, a, centre))
            # Top image: front of the product at the bottom of the image.
            uv = lambda v: (0.5 + verts[v][0] / (2 * r), 0.5 + verts[v][1] / (2 * r))
            corners = (a, b, centre) if is_top else (b, a, centre)
            uvs.append([uv(v) for v in corners])
            mat_index.append(cap_i if is_top else bottom_i)
    obj = _mesh_object(name, verts, faces, uvs, mat_index, mats, smooth=True)
    # Sharp rims where the side meets a flat cap, smooth round the body.
    mod = obj.modifiers.new("rims", "EDGE_SPLIT")
    mod.split_angle = math.radians(40)
    if top.get("tab"):
        pull_tab(obj, profile[-1][1], mats[band_i or 0], f"{name}_tab")
    return obj


def _rounded_rect(cx, cy, w, h, r, steps=6):
    """Outline points of a rounded rectangle, anticlockwise, metres."""
    pts = []
    for qx, qy, a0 in ((1, 1, 0), (-1, 1, 90), (-1, -1, 180), (1, -1, 270)):
        ox, oy = cx + qx * (w / 2 - r), cy + qy * (h / 2 - r)
        pts += [(ox + r * math.cos(math.radians(a0 + 90 * k / steps)), oy + r * math.sin(math.radians(a0 + 90 * k / steps))) for k in range(steps + 1)]
    return pts


def pull_tab(can, lid_z, mat, name):
    """A drinks-can pull tab and rivet on the lid: nose over the opening at the front, finger ring at the back."""
    curve = bpy.data.curves.new(name, "CURVE")
    curve.dimensions, curve.fill_mode = "2D", "BOTH"
    curve.extrude, curve.bevel_depth, curve.bevel_resolution = 0.25 * MM, 0.15 * MM, 2
    for pts in (_rounded_rect(0, 3.5 * MM, 12.5 * MM, 21 * MM, 5 * MM), _rounded_rect(0, 8.0 * MM, 8.5 * MM, 7.5 * MM, 3.2 * MM)):
        spline = curve.splines.new("POLY")
        spline.points.add(len(pts) - 1)
        for p, (x, y) in zip(spline.points, pts):
            p.co = (x, y, 0, 1)
        spline.use_cyclic_u = True
    curve.materials.append(mat)
    tab = bpy.data.objects.new(name, curve)
    tab.location = (0, 0, lid_z + 0.6 * MM)
    bpy.context.collection.objects.link(tab)
    bpy.ops.mesh.primitive_cylinder_add(radius=1.6 * MM, depth=0.8 * MM, location=(0, 0, lid_z + 0.4 * MM))
    rivet = bpy.context.object
    rivet.name = f"{name}_rivet"
    rivet.data.materials.append(mat)
    for part in (tab, rivet):
        part.parent = can
        part["shots_product"] = True


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
    obj["shots_product"] = True
    return obj
