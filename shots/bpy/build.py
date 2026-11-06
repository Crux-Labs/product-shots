"""Runs inside Blender: builds a scene from a resolved spec and renders it.

    blender -b --factory-startup -P build.py -- <spec.json> <out_dir>

mode "layout" writes the three passes the pipeline needs:
    guide.png  the whole scene, sent to the image model as the layout
    layer.png  the products and the shadows they cast, everything else transparent (straight alpha)
    mask.png   alpha of the products alone
With "environment" (an equirectangular image) the world lights and reflects that image instead of the plain studio sky, and with
"layer_only" only layer.png is rendered: shots relight uses both to re-light the product to match the repainted room.
mode "views" renders each product alone on grey from front, three-quarter and top, for the check sheet.
"""
import json
import math
import sys
import time
from pathlib import Path

import bpy
from mathutils import Matrix, Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
import templates  # noqa: E402

MM = 0.001
argv = sys.argv[sys.argv.index("--") + 1:]
SPEC = json.loads(Path(argv[0]).read_text())
OUT = Path(argv[1])
OUT.mkdir(parents=True, exist_ok=True)


def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.view_settings.view_transform, sc.view_settings.look = "Standard", "None"
    use_gpu(sc)
    return sc


def use_gpu(sc):
    """First GPU backend that has a device, else CPU."""
    prefs = bpy.context.preferences.addons["cycles"].preferences
    for backend in ("OPTIX", "CUDA", "METAL", "HIP", "ONEAPI"):
        try:
            prefs.compute_device_type = backend
            prefs.get_devices()
        except TypeError:
            continue
        gpus = [d for d in prefs.devices if d.type != "CPU"]
        if gpus:
            for d in prefs.devices:
                d.use = True
            sc.cycles.device = "GPU"
            return backend
    sc.cycles.device = "CPU"
    return "CPU"


def _diffuse(name, color, roughness):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = templates.linear(color)
    bsdf.inputs["Roughness"].default_value = roughness
    return mat


def plane(name, size, location, rotation, mat):
    bpy.ops.mesh.primitive_plane_add(size=size, location=location, rotation=rotation)
    obj = bpy.context.object
    obj.name = name
    obj.data.materials.append(mat)
    return obj


def place_products(items):
    objs = []
    for n, item in enumerate(items):
        obj = templates.build(item["product"], f"{item['product']['name']}_{n}")
        if "matrix" in item:  # a full pose in metres, as shots swap measures it from an existing image
            obj.matrix_world = Matrix(item["matrix"])
        else:
            x, y, z = item.get("position_mm", [0, 0, 0])
            obj.location = (x * MM, y * MM, z * MM)
            obj.rotation_euler = [math.radians(a) for a in item.get("rotation_deg", [0, 0, 0])]
        objs.append(obj)
    return objs


def camera(cam_spec, page):
    sc = bpy.context.scene
    sc.render.resolution_x, sc.render.resolution_y = page
    sc.render.resolution_percentage = 100
    data = bpy.data.cameras.new("camera")
    data.lens, data.sensor_width = cam_spec.get("lens_mm", 70), 36
    data.sensor_fit = "AUTO"
    cam = bpy.data.objects.new("camera", data)
    sc.collection.objects.link(cam)
    if "matrix" in cam_spec:
        cam.matrix_world = Matrix(cam_spec["matrix"])
        sc.camera = cam
        return cam
    tx, ty, tz = [v * MM for v in cam_spec.get("target_mm", [0, 0, 20])]
    az = math.radians(cam_spec.get("azimuth_deg", 0))
    dist, height = cam_spec.get("distance_mm", 500) * MM, cam_spec.get("height_mm", 150) * MM
    cam.location = (tx + dist * math.sin(az), ty - dist * math.cos(az), height)
    direction = Vector((tx, ty, tz)) - cam.location
    cam.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
    cam.rotation_euler.rotate_axis("Z", math.radians(cam_spec.get("roll_deg", 0)))
    sc.camera = cam
    return cam


def area_light(name, target, azimuth, elevation, distance, size, power, color=(255, 255, 255)):
    data = bpy.data.lights.new(name, "AREA")
    data.size, data.energy = size, power
    data.color = templates.linear(color)[:3]
    light = bpy.data.objects.new(name, data)
    bpy.context.scene.collection.objects.link(light)
    az, el = math.radians(azimuth), math.radians(elevation)
    light.location = (target[0] + distance * math.cos(el) * math.sin(az), target[1] - distance * math.cos(el) * math.cos(az),
                      target[2] + distance * math.sin(el))
    light.rotation_euler = (Vector(target) - light.location).to_track_quat("-Z", "Y").to_euler()
    return light


def lights(spec, target):
    l = spec.get("light", {})
    area_light("key", target, l.get("key_azimuth_deg", -55), l.get("key_elevation_deg", 35), 1.2, l.get("key_size_m", 0.8),
               40 * l.get("key_power", 1.0), l.get("key_color", (255, 246, 232)))
    if fill := l.get("fill", 0.3):
        area_light("fill", target, l.get("key_azimuth_deg", -55) + 110, 20, 1.4, 1.2, 40 * fill, l.get("fill_color", (232, 240, 255)))
    world = bpy.data.worlds.new("world")
    world.use_nodes = True
    nodes, links = world.node_tree.nodes, world.node_tree.links
    bg = nodes["Background"]
    bg.inputs["Color"].default_value = templates.linear(l.get("ambient_color", (210, 215, 225)))
    # Brighter overhead than at the horizon, like a room or studio, so metal and gloss have something to reflect.
    coord, xyz, ramp = nodes.new("ShaderNodeTexCoord"), nodes.new("ShaderNodeSeparateXYZ"), nodes.new("ShaderNodeMapRange")
    ramp.inputs["From Min"].default_value, ramp.inputs["From Max"].default_value = -0.1, 0.9
    ambient = l.get("ambient", 0.25)
    ramp.inputs["To Min"].default_value, ramp.inputs["To Max"].default_value = ambient * 0.4, ambient * 1.8
    links.new(coord.outputs["Generated"], xyz.inputs["Vector"])
    links.new(xyz.outputs["Z"], ramp.inputs["Value"])
    links.new(ramp.outputs["Result"], bg.inputs["Strength"])
    bpy.context.scene.world = world


def environment(path, strength):
    """The world becomes the given panorama, so the product is lit by, and reflects, the room it will sit in."""
    world = bpy.context.scene.world
    nodes, links = world.node_tree.nodes, world.node_tree.links
    for n in [n for n in nodes if n.type not in ("BACKGROUND", "OUTPUT_WORLD")]:
        nodes.remove(n)
    bg = nodes["Background"]
    tex = nodes.new("ShaderNodeTexEnvironment")
    tex.image = bpy.data.images.load(str(path))
    links.new(tex.outputs["Color"], bg.inputs["Color"])
    bg.inputs["Strength"].default_value = strength


def set_pieces(spec):
    s = spec.get("set", {})
    if s.get("floor") is False:  # shots swap: the product goes into an existing photo, which already has its floor and shadows
        return []
    env = [plane("floor", 8, (0, 0, 0), (0, 0, 0), _diffuse("floor", s.get("floor_color", (180, 150, 120)), 0.6))]
    if s.get("wall", True):
        y = s.get("wall_distance_mm", 300) * MM
        env.append(plane("wall", 8, (0, y, 4), (math.radians(90), 0, 0), _diffuse("wall", s.get("wall_color", (225, 225, 220)), 0.9)))
    return env


def render(path, samples):
    sc = bpy.context.scene
    sc.cycles.samples = samples
    sc.render.filepath = str(path)
    t = time.time()
    bpy.ops.render.render(write_still=True)
    return round(time.time() - t, 1)


def layout():
    sc = reset()
    r = SPEC.get("render", {})
    products = place_products(SPEC["products"])
    env = set_pieces(SPEC)
    cam_spec = SPEC.get("camera", {})
    camera(cam_spec, SPEC["page"])
    lights(SPEC, [v * MM for v in cam_spec.get("target_mm", [0, 0, 20])])
    if SPEC.get("environment"):
        environment(SPEC["environment"], SPEC.get("environment_strength", 0.5))
    sc.view_settings.exposure = r.get("exposure", 0.0)
    cy = sc.cycles
    cy.use_denoising = r.get("denoise", True)
    if cy.use_denoising:
        cy.denoiser = "OPENIMAGEDENOISE"
        # Albedo and normal guides with the accurate prefilter keep printed detail; colour alone smears small text.
        cy.denoising_input_passes, cy.denoising_prefilter = "RGB_ALBEDO_NORMAL", "ACCURATE"
    # Pixel filter width: Cycles' default 1.5 px softens small print; about 1.0 keeps it crisp without stair-stepping.
    cy.filter_width = r.get("filter_width", 1.5)
    sc.render.image_settings.file_format, sc.render.image_settings.color_mode = "PNG", "RGBA"
    samples = r.get("samples", 128)
    info = {"blender": bpy.app.version_string, "device": cy.device, "samples": samples, "page": SPEC["page"], "products": [o.name for o in products]}
    if not SPEC.get("layer_only") and not SPEC.get("no_guide"):
        info["guide_s"] = render(OUT / "guide.png", samples)
    sc.render.film_transparent = True
    for o in env:
        o.is_shadow_catcher = True
    info["layer_s"] = render(OUT / "layer.png", samples)
    if SPEC.get("layer_only"):
        (OUT / "layout.json").write_text(json.dumps(info, indent=1))
        print("SHOTS_LAYOUT", json.dumps(info))
        return
    for o in env:
        o.is_shadow_catcher, o.is_holdout = False, True
    cy.use_denoising = False
    info["mask_s"] = render(OUT / "mask.png", 64)
    (OUT / "layout.json").write_text(json.dumps(info, indent=1))
    print("SHOTS_LAYOUT", json.dumps(info))


def views():
    """Each product alone, on a neutral grey sweep, from the three angles the check sheet shows."""
    info = {"views": []}
    for n, item in enumerate(SPEC["products"]):
        prod = item["product"]
        for view, az, dist_k, height_k in (("front", 0, 5.5, 0.35), ("three_quarter", 35, 5.0, 2.2), ("top", 0, 1.0, 5.5)):
            sc = reset()
            obj = place_products([{"product": prod}])[0]
            bpy.context.view_layer.update()
            corners = [obj.matrix_world @ Vector(c) for c in obj.bound_box]
            size = max((max(c[i] for c in corners) - min(c[i] for c in corners)) for i in range(3))
            centre_z = (max(c.z for c in corners) + min(c.z for c in corners)) / 2
            plane("floor", 8, (0, 0, 0), (0, 0, 0), _diffuse("floor", (128, 128, 128), 0.7))
            camera({"lens_mm": 85, "target_mm": [0, 0, centre_z / MM], "azimuth_deg": az, "distance_mm": size * dist_k / MM,
                    "height_mm": (centre_z + size * height_k) / MM}, (900, 900))
            lights({"light": {"key_azimuth_deg": -40, "key_elevation_deg": 45, "fill": 0.5, "ambient": 0.6}}, [0, 0, centre_z])
            sc.cycles.use_denoising = True
            path = OUT / f"view_{n}_{view}.png"
            render(path, 96)
            info["views"].append({"product": prod["name"], "view": view, "file": str(path)})
    (OUT / "views.json").write_text(json.dumps(info, indent=1))
    print("SHOTS_VIEWS", json.dumps(info))


{"layout": layout, "views": views}[SPEC.get("mode", "layout")]()
