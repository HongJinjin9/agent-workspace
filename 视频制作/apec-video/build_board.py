import bpy
import math
import os
import sys

OUT = "/app/vedio/apec-video/assets/blender"
FONT_CANDIDATES = [
    "/usr/share/fonts/opentype/noto/NotoSerifCJK-Regular.ttc",
    "/usr/share/fonts/opentype/noto/NotoSerifCJK-Bold.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/home/admin/.fonts/NotoSansCJKsc-Regular.otf",
]
FONT = next((f for f in FONT_CANDIDATES if os.path.exists(f)), FONT_CANDIDATES[-1])

GOLD = (1.0, 0.78, 0.32, 1)
TEAL = (0.31, 0.76, 0.97, 1)
RED = (0.92, 0.32, 0.30, 1)
PURPLE = (0.64, 0.52, 0.82, 1)
WHITE = (0.92, 0.96, 1.0, 1)
DIM = (0.28, 0.38, 0.48, 1)
BG = (0.008, 0.012, 0.022, 1)

# palace layout: (name, gan, star, gate, god, kong, highlight)
PALACES = [
    ("巽四宫", "己", "天柱", "伤门", "九地", False),
    ("离九宫", "癸", "天心", "杜门", "九天", False),
    ("坤二宫", "辛", "天蓬 符", "景门", "值符", True),
    ("震三宫", "庚", "天芮", "生门", "玄武", False),
    ("中五宫", "戊", "天禽寄坤", "", "", False),
    ("兑七宫", "丙", "天任", "死门", "螣蛇", True),
    ("艮八宫", "丁", "天英", "休门 使", "白虎", False),
    ("坎一宫", "壬", "天辅", "开门", "六合", False),
    ("乾六宫", "乙", "天冲", "惊门", "太阴", False),
]
ORDER = [4, 3, 2, 1, 0, 8, 7, 6, 5]  # 宫序 5→4→3→2→1→9→8→7→6 → indices

TILE = 0.34
GAP = 0.03
STEP = TILE + GAP
HALF = 3 * TILE / 2 + GAP  # board half width


def setup_scene(mode):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = 24 if mode == "ortho" else 24
    sc.cycles.use_denoising = True
    sc.render.film_transparent = mode == "ortho"
    sc.render.resolution_x = 1440 if mode == "ortho" else 1080
    sc.render.resolution_y = 2560 if mode == "ortho" else 1920
    sc.render.resolution_percentage = 100
    sc.view_settings.view_transform = "AgX"
    sc.view_settings.look = "AgX - Medium High Contrast"
    world = bpy.data.worlds.new("W")
    sc.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes["Background"]
    bg.inputs[0].default_value = BG
    bg.inputs[1].default_value = 1.0
    return sc


def load_font():
    try:
        return bpy.data.fonts.load(FONT)
    except Exception as e:
        print("font load failed", e)
        return None


def make_material(name, color, strength=2.2, metallic=0.0, rough=0.4):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    bsdf = nt.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = color
    bsdf.inputs["Metallic"].default_value = metallic
    bsdf.inputs["Roughness"].default_value = rough
    if "Emission Color" in bsdf.inputs:
        bsdf.inputs["Emission Color"].default_value = color
        bsdf.inputs["Emission Strength"].default_value = strength
    return m


def add_text(text, size, loc, color, font, strength=3.0, extrude=0.0008, align_y="CENTER"):
    curve = bpy.data.curves.new(type="FONT", name="txt")
    curve.body = text
    if font:
        curve.font = font
    curve.size = size
    curve.align_x = "CENTER"
    curve.align_y = align_y
    curve.extrude = extrude
    obj = bpy.data.objects.new("t_" + text[:8], curve)
    bpy.context.collection.objects.link(obj)
    obj.location = loc
    mat = make_material("m_" + text[:10], color, strength=strength, rough=0.35)
    obj.data.materials.append(mat)
    return obj


def rounded_tile(name, w, h, loc, mat, bevel=0.028):
    bpy.ops.mesh.primitive_cube_add(size=1, location=(loc[0], loc[1], loc[2]))
    obj = bpy.context.object
    obj.name = name
    obj.scale = (w, h, 0.024)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    mod = obj.modifiers.new("bevel", "BEVEL")
    mod.width = bevel
    mod.segments = 6
    mod.limit_method = "NONE"
    obj.data.materials.append(mat)
    return obj


def build_board(sc, mode, font, highlight=None, kong_pulse=None):
    dark = make_material("tile", (0.016, 0.028, 0.050, 1), strength=0.0, metallic=0.55, rough=0.30)
    nt = dark.node_tree
    bsdf = nt.nodes.get("Principled BSDF")
    tex = nt.nodes.new("ShaderNodeTexNoise")
    tex.inputs["Scale"].default_value = 180.0
    tex.inputs["Detail"].default_value = 4.0
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.08
    nt.links.new(tex.outputs["Fac"], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    edge = make_material("edge", (0.35, 0.62, 0.85, 1), strength=1.6, metallic=0.2, rough=0.3)
    edge_gold = make_material("edge_gold", GOLD, strength=2.2, metallic=0.6, rough=0.25)
    edge_red = make_material("edge_red", RED, strength=2.6, metallic=0.3, rough=0.3)

    for idx, (pname, gan, star, gate, god, kong) in enumerate(PALACES):
        col = idx % 3
        row = idx // 3
        x = (col - 1) * STEP
        y = (1 - row) * STEP
        hi = highlight is not None and PALACES[highlight][0] == pname
        # glow frame behind tile
        if kong:
            frame_mat = edge_red
        elif hi:
            frame_mat = edge_gold
        else:
            frame_mat = edge
        rounded_tile("frame_%d" % idx, TILE + 0.022, TILE + 0.022, (x, y, -0.004), frame_mat, bevel=0.03)
        rounded_tile("tile_%d" % idx, TILE, TILE, (x, y, 0.0), dark, bevel=0.026)
        # texts
        z = 0.016
        add_text(pname, 0.033, (x, y + 0.056, z), (0.55, 0.68, 0.80, 1) if not kong else RED, font, strength=2.2)
        add_text(gan, 0.150, (x, y + 0.012, z), GOLD, font, strength=3.0)
        add_text(star, 0.024, (x, y - 0.066, z), TEAL, font, strength=3.0)
        if gate:
            add_text(gate, 0.024, (x, y - 0.103, z), RED, font, strength=3.0)
        if god:
            add_text(god, 0.022, (x, y - 0.140, z), PURPLE, font, strength=2.6)
        if kong:
            add_text("空", 0.05, (x + TILE * 0.32, y + TILE * 0.32, z), RED, font, strength=3.2)

    # decorative outer ring (Luoshu-ish circle)
    bpy.ops.mesh.primitive_torus_add(
        major_radius=HALF + 0.10, minor_radius=0.0016,
        location=(0, 0, -0.02), major_segments=256, minor_segments=8,
    )
    ring = bpy.context.object
    ring.data.materials.append(make_material("ring", (0.25, 0.55, 0.8, 1), strength=1.2, rough=0.4))
    for r, s in ((HALF + 0.22, 0.9), (HALF + 0.34, 0.6)):
        bpy.ops.mesh.primitive_torus_add(
            major_radius=r, minor_radius=0.0010,
            location=(0, 0, -0.03), major_segments=256, minor_segments=6,
        )
        bpy.context.object.data.materials.append(make_material("ring2", (0.2, 0.4, 0.6, 1), strength=s, rough=0.4))


def setup_lights(sc, mode):
    bpy.ops.object.light_add(type="AREA", location=(-1.2, 1.4, 2.2))
    k = bpy.context.object
    k.data.energy = 260
    k.data.size = 2.2
    k.data.color = (1.0, 0.92, 0.8)
    k.rotation_euler = (math.radians(-35), math.radians(20), 0)
    bpy.ops.object.light_add(type="AREA", location=(1.6, -1.0, 1.6))
    f = bpy.context.object
    f.data.energy = 120
    f.data.size = 2.0
    f.data.color = (0.35, 0.65, 1.0)
    f.rotation_euler = (math.radians(30), math.radians(-25), 0)


def setup_camera(sc, mode):
    bpy.ops.object.camera_add()
    cam = bpy.context.object
    sc.camera = cam
    if mode == "ortho":
        cam.data.type = "ORTHO"
        cam.data.ortho_scale = 1.92
        cam.location = (0, 0, 8)
        cam.rotation_euler = (0, 0, 0)
    else:
        cam.data.lens = 45
        cam.location = (0.0, -1.95, 1.32)
        cam.rotation_euler = (math.radians(54), 0, 0)
        # floor
        bpy.ops.mesh.primitive_plane_add(size=8, location=(0, 0, -0.06))
        floor = bpy.context.object
        floor.data.materials.append(make_material("floor", (0.010, 0.014, 0.024, 1), strength=0.0, metallic=0.6, rough=0.25))
        # backdrop glow plane
        bpy.ops.mesh.primitive_plane_add(size=6, location=(0, 0.9, 0.6))
        back = bpy.context.object
        back.rotation_euler = (math.radians(70), 0, 0)
        back.data.materials.append(make_material("back", (0.02, 0.05, 0.10, 1), strength=1.2, rough=1.0))


def main():
    mode = "ortho"
    if "--" in sys.argv:
        args = sys.argv[sys.argv.index("--") + 1:]
        if args:
            mode = args[0]
    os.makedirs(OUT, exist_ok=True)
    sc = setup_scene(mode)
    font = load_font()
    setup_lights(sc, mode)
    build_board(sc, mode, font)
    setup_camera(sc, mode)
    sc.render.filepath = os.path.join(OUT, "board_" + mode + ".png")
    bpy.ops.render.render(write_still=True)
    print("RENDERED", sc.render.filepath)


main()
