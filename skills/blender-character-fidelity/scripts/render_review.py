#!/usr/bin/env python3
"""Capture a saved Blender REVIEW scene. Run through Blender --python-exit-code 2."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from validate_character import FULL, THREE_QUARTER, digest, local_path, read_json, require, validate


def socket_value(value):
    """Serialize common lighting socket values without unstable object reprs."""
    if value is None or type(value) in (bool, int, float, str):
        return value
    if hasattr(value, "name"):
        return {"name": value.name}
    try:
        return [socket_value(item) for item in value]
    except TypeError:
        return {"unsupported_type": type(value).__name__}


def node_tree_snapshot(tree, ancestors=()):
    """Bind common world/light node settings, not every custom shader state."""
    if tree is None:
        return None
    if id(tree) in ancestors:
        return {"recursive_group": tree.name}
    nodes = []
    for node in sorted(tree.nodes, key=lambda n: n.name):
        row = {"name": node.name, "type": node.bl_idname, "mute": node.mute}
        for direction in ("inputs", "outputs"):
            row[direction] = [
                {"index": index, "identifier": socket.identifier,
                 "default": socket_value(socket.default_value)}
                for index, socket in enumerate(getattr(node, direction))
                if hasattr(socket, "default_value")
            ]
        for key in ("operation", "blend_type", "projection", "interpolation", "extension",
                    "space", "vector_type", "distribution"):
            if hasattr(node, key):
                row[key] = socket_value(getattr(node, key))
        image = getattr(node, "image", None)
        if image is not None:
            packed = image.packed_file
            row["image"] = {"name": image.name, "source": image.source,
                            "colorspace": image.colorspace_settings.name,
                            "packed_sha256": hashlib.sha256(bytes(packed.data)).hexdigest() if packed else None}
        ramp = getattr(node, "color_ramp", None)
        if ramp is not None:
            row["color_ramp"] = {
                "color_mode": ramp.color_mode, "interpolation": ramp.interpolation,
                "hue_interpolation": ramp.hue_interpolation,
                "elements": [{"position": e.position, "color": list(e.color)} for e in ramp.elements],
            }
        group = getattr(node, "node_tree", None)
        if group is not None:
            row["group"] = node_tree_snapshot(group, (*ancestors, id(tree)))
        nodes.append(row)
    links = sorted(
        [{"from_node": link.from_node.name, "from_socket": link.from_socket.identifier,
          "to_node": link.to_node.name, "to_socket": link.to_socket.identifier}
         for link in tree.links],
        key=lambda link: tuple(link[key] for key in ("from_node", "from_socket", "to_node", "to_socket")),
    )
    return {"nodes": nodes, "links": links}


def lighting_snapshot(scene):
    world = scene.world
    result = {
        "world": ({"name": world.name, "color": list(world.color), "use_nodes": world.use_nodes,
                   "node_tree": node_tree_snapshot(world.node_tree) if world.use_nodes else None}
                  if world else None),
        "lights": [],
    }
    for obj in sorted(scene.objects, key=lambda o: o.name):
        if obj.type != "LIGHT":
            continue
        data = obj.data
        row = {"name": obj.name, "type": data.type, "energy": data.energy,
               "color": list(data.color), "matrix_world": [list(r) for r in obj.matrix_world],
               "hide_render": obj.hide_render}
        for key in ("use_nodes", "shape", "size", "size_y", "angle", "spot_size", "spot_blend",
                    "shadow_soft_size", "spread", "normalize", "use_shadow", "use_custom_distance",
                    "cutoff_distance", "diffuse_factor", "specular_factor", "volume_factor"):
            if hasattr(data, key):
                row[key] = socket_value(getattr(data, key))
        row["node_tree"] = node_tree_snapshot(data.node_tree) if getattr(data, "use_nodes", False) else None
        result["lights"].append(row)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec", required=True, type=Path)
    parser.add_argument("--out", required=True, help="New directory relative to spec")
    parser.add_argument("--iteration", required=True, type=int)
    parser.add_argument("--stage", choices=("blockout", "identity", "camera", "lookdev", "final"), default="final")
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:])
    try:
        import bpy
    except ImportError as exc:
        raise RuntimeError("Run capture with Blender --background saved.blend --python-exit-code 2 --python this-script -- ...") from exc
    from bpy_extras.object_utils import world_to_camera_view
    from mathutils import Vector
    spec_path = args.spec.resolve()
    root = spec_path.parent
    spec = validate(read_json(spec_path), root, ready=True)
    spec_hash = digest(spec_path)
    cfg = spec["review"]
    require(1 <= args.iteration <= spec["quality"]["max_iterations"], "Iteration outside budget")
    require(bpy.app.version >= (4, 2, 0), "Blender 4.2+ required; verify local version")
    require(bpy.data.filepath and not bpy.data.is_dirty, "Open a saved, unchanged blend before rendering")
    blend = Path(bpy.data.filepath).resolve()
    require(blend.is_relative_to(root), "Blend must be inside the character project")
    blend_hash = digest(blend)
    require(not bpy.data.libraries and not bpy.data.movieclips and not bpy.data.cache_files
            and not bpy.data.volumes, "Pack/convert external or unsupported dependencies first")
    for image in bpy.data.images:
        if image.source in {"FILE", "SEQUENCE", "MOVIE", "TILED"}:
            require(image.source == "FILE" and bool(image.packed_file), f"Pack/convert image: {image.name}")
    require(cfg["scene"] in bpy.data.scenes, "Missing REVIEW scene")
    scene = bpy.data.scenes[cfg["scene"]]
    bpy.context.window.scene = scene
    require(len(scene.view_layers) == 1, "MVP review scene must contain one view layer")
    layer = scene.view_layers[0]
    collection = bpy.data.collections.get(cfg["collection"])
    require(collection is not None, "Missing CHARACTER collection")
    scene.frame_set(cfg["frame"])
    members = set(collection.all_objects)
    meshes = [o for o in members if o.type == "MESH" and not o.hide_render and o.name in scene.objects]
    require(meshes, "No character mesh to render")
    render_types = {"MESH", "CURVE", "SURFACE", "META", "FONT", "VOLUME", "CURVES", "POINTCLOUD"}
    for obj in scene.objects:
        if obj.type in render_types and not obj.hide_render:
            require(obj in members and obj.type == "MESH", f"Non-character/non-mesh render object: {obj.name}")
        require(not obj.particle_systems, f"Convert particles before review: {obj.name}")
        require(not any(m.type in {"FLUID", "CLOTH", "SOFT_BODY", "MESH_SEQUENCE_CACHE"} for m in obj.modifiers),
                f"Freeze unsupported simulation/cache: {obj.name}")
    cameras = {}
    directions = {"front": (0, -1, 0), "side": (1, 0, 0), "back": (0, 1, 0),
                  "front_three_quarter": (1, -1, 0), "back_three_quarter": (1, 1, 0)}
    for view in cfg["views"]:
        cam = scene.objects.get(view["camera"])
        require(cam is not None and cam.type == "CAMERA", f"Missing camera: {view['id']}")
        require(cam.data.type == view["projection"], f"Projection mismatch: {view['id']}")
        require(not cam.constraints and not cam.animation_data and not cam.data.animation_data,
                "Bake camera constraints/animation to fixed review transforms")
        if view["id"] in directions:
            forward = cam.matrix_world.to_quaternion() @ Vector((0, 0, -1))
            up = cam.matrix_world.to_quaternion() @ Vector((0, 1, 0))
            require(forward.dot(-Vector(directions[view["id"]]).normalized()) > .999
                    and up.dot(Vector((0, 0, 1))) > .999, f"Canonical camera direction/roll: {view['id']}")
        cam.data.dof.use_dof = False
        cameras[view["id"]] = cam
    canonical = [cameras[v] for v in FULL | THREE_QUARTER if v in cameras]
    require(max(c.data.ortho_scale for c in canonical) - min(c.data.ortho_scale for c in canonical) < 1e-5,
            "Canonical full-body cameras must share ortho scale")
    require(max(c.matrix_world.translation.z for c in canonical) - min(c.matrix_world.translation.z for c in canonical) < 1e-5,
            "Canonical cameras must share height")
    for name in cfg["landmarks"].values():
        require(name in scene.objects, f"Missing attached landmark: {name}")
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = cfg["samples"]
    scene.cycles.seed = cfg["seed"]
    scene.cycles.use_animated_seed = False
    scene.cycles.use_denoising = False
    scene.cycles.use_adaptive_sampling = False
    scene.render.resolution_x, scene.render.resolution_y = cfg["resolution"]
    scene.render.resolution_percentage = 100
    scene.render.pixel_aspect_x = scene.render.pixel_aspect_y = 1
    scene.render.use_border = False
    scene.render.use_compositing = False
    scene.render.use_sequencer = False
    scene.render.use_motion_blur = False
    scene.render.film_transparent = True
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.image_settings.color_depth = "8"
    scene.view_settings.view_transform = cfg["view_transform"]
    scene.view_settings.look = "None"
    scene.view_settings.exposure = 0
    scene.view_settings.gamma = 1
    layer.material_override = None
    layer.update()
    depsgraph = bpy.context.evaluated_depsgraph_get()
    vertices, triangle_count = [], 0
    for obj in meshes:
        evaluated = obj.evaluated_get(depsgraph)
        mesh = evaluated.to_mesh()
        try:
            mesh.calc_loop_triangles()
            triangle_count += len(mesh.loop_triangles)
            vertices.extend(evaluated.matrix_world @ v.co for v in mesh.vertices)
        finally:
            evaluated.to_mesh_clear()
    require(vertices and triangle_count > 0, "Empty evaluated character geometry")
    clay = bpy.data.materials.new("__FIDELITY_CLAY__")
    clay.use_nodes = True
    bsdf = next((node for node in clay.node_tree.nodes if node.type == "BSDF_PRINCIPLED"), None)
    require(bsdf is not None, "Missing Principled BSDF in review clay material")
    bsdf.inputs["Base Color"].default_value = (.5, .5, .5, 1)
    bsdf.inputs["Roughness"].default_value = .8
    out = local_path(root, args.out)
    require(not out.exists(), "Review directory exists; use a new iteration directory")
    out.mkdir(parents=True)
    manifest = {"schema_version": 1, "character_id": spec["character_id"], "spec_sha256": spec_hash,
                "blend": {"path": blend.relative_to(root).as_posix(), "sha256": blend_hash},
                "iteration": args.iteration, "stage": args.stage, "blender_version": bpy.app.version_string,
                "created_utc": datetime.now(timezone.utc).isoformat(), "settings": cfg,
                "render": {"engine": "CYCLES", "device": "CPU", "exposure": 0, "gamma": 1, "look": "None",
                           "dof": False, "denoising": False, "motion_blur": False},
                "lighting": lighting_snapshot(scene),
                "geometry": {"mesh_count": len(meshes), "triangles": triangle_count}, "views": {}}
    for view in cfg["views"]:
        camera = cameras[view["id"]]
        scene.camera = camera
        layer.update()
        if view["role"] == "full":
            projected = [world_to_camera_view(scene, camera, v) for v in vertices]
            require(all(0 <= p.x <= 1 and 0 <= p.y <= 1 and camera.data.clip_start < p.z < camera.data.clip_end
                        for p in projected), f"Clipped full-body view: {view['id']}")
        points = {}
        for key, name in cfg["landmarks"].items():
            pos = scene.objects[name].evaluated_get(depsgraph).matrix_world.translation
            p = world_to_camera_view(scene, camera, pos)
            points[key] = [p.x, 1 - p.y, p.z]
        data = camera.data
        row = {"camera": {"name": camera.name, "projection": data.type,
                          "matrix_world": [list(r) for r in camera.matrix_world], "lens_mm": data.lens,
                          "sensor_width": data.sensor_width, "sensor_height": data.sensor_height,
                          "sensor_fit": data.sensor_fit, "shift": [data.shift_x, data.shift_y],
                          "ortho_scale": data.ortho_scale, "clip": [data.clip_start, data.clip_end]},
               "landmarks": points, "images": {}}
        for mode in ("clay", "material"):
            layer.material_override = clay if mode == "clay" else None
            target = out / f"{view['id']}-{mode}.png"
            scene.render.filepath = str(target)
            bpy.ops.render.render(write_still=True)
            require(target.is_file() and target.stat().st_size > 100, "Missing/empty rendered PNG")
            check = bpy.data.images.load(str(target), check_existing=False)
            try:
                require(max(check.pixels[3::4], default=0) > .5, f"Blank character alpha: {view['id']}/{mode}")
            finally:
                bpy.data.images.remove(check)
            row["images"][mode] = {"path": target.relative_to(root).as_posix(), "sha256": digest(target)}
        manifest["views"][view["id"]] = row
    require(digest(blend) == blend_hash and digest(spec_path) == spec_hash, "Inputs changed during capture")
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(f"Captured {len(cameras)} views; no likeness claim. Manifest: {out / 'manifest.json'}")


if __name__ == "__main__":
    main()
