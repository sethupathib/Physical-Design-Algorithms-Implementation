#!/usr/bin/env python3
"""Generate continuous-build-up ROUTING teaching GIF (1280x720).

Starts from CTS-done die and accumulates:
  global route → track assignment → detail route → DRC fix → timing opt
"""

from __future__ import annotations

import os
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUT_DIR = Path(__file__).resolve().parent
FRAMES = OUT_DIR / "route_frames"
GIF = OUT_DIR / "route_flow.gif"
ARTIFACT = Path("/opt/cursor/artifacts/route_flow.gif")

W, H = 1280, 720
LEFT_W = 360

BG = (236, 238, 242)
HEADER = (18, 42, 74)
PANEL = (248, 249, 252)
INK = (28, 34, 48)
MUTED = (120, 128, 140)
DONE = (34, 140, 78)
ACTIVE = (28, 96, 196)
DIE_EDGE = (20, 24, 32)
CORE = (230, 120, 40)
UTIL = (210, 228, 240)
PIN_TB = (40, 70, 140)
PIN_LR = (210, 120, 50)
PWR_H = (200, 55, 55)
PWR_V = (55, 95, 190)
MACRO_FILL = (190, 210, 160)
MACRO_FILL_ALT = (225, 205, 150)
MACRO_EDGE = (70, 95, 55)
LEGAL = (50, 130, 90)
CLK = (20, 140, 150)
CLK_ROUTE = (15, 110, 120)
BUF = (180, 90, 40)
BUF_EDGE = (120, 50, 20)
# Signal metals
M1 = (50, 100, 190)
M2 = (190, 90, 50)
M3 = (40, 150, 90)
GCell = (100, 120, 160)
TRACK = (160, 170, 185)
DRC = (210, 40, 40)
OK = (40, 140, 70)
CRIT = (200, 40, 50)
WHITE = (255, 255, 255)
COND = (100, 70, 160)

STEPS = [
    "Global routing",
    "Track assignment",
    "Detail routing",
    "DRC fix",
    "Timing optimization",
]


def font(size: int, bold: bool = False):
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    ]
    for p in candidates:
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


F_TITLE = font(22, True)
F_H1 = font(18, True)
F_BODY = font(14)
F_SMALL = font(12)
F_TINY = font(11)
F_MACRO = font(11, True)
F_LABEL = font(12, True)


def die_box():
    return LEFT_W + 70, 90, LEFT_W + 70 + 520, 90 + 520


def core_box(die):
    x0, y0, x1, y1 = die
    m = 36
    return x0 + m, y0 + m, x1 - m, y1 - m


CLEAN_MACROS = [
    ("SRAM0", 0.04, 0.05, 0.26, 0.28, MACRO_FILL),
    ("SRAM1", 0.38, 0.05, 0.60, 0.26, MACRO_FILL),
    ("DDR PHY", 0.78, 0.10, 0.95, 0.68, MACRO_FILL),
    ("PLL/ANA", 0.04, 0.40, 0.24, 0.60, MACRO_FILL_ALT),
    ("MACRO", 0.34, 0.56, 0.60, 0.82, MACRO_FILL_ALT),
]


def abs_macros(core, macros):
    cx0, cy0, cx1, cy1 = core
    cw, ch = cx1 - cx0, cy1 - cy0
    return [
        (n, int(cx0 + a * cw), int(cy0 + b * ch), int(cx0 + c * cw), int(cy0 + d * ch), f)
        for n, a, b, c, d, f in macros
    ]


def macro_rects(macros):
    return [(m[1], m[2], m[3], m[4]) for m in macros]


def in_macro(x, y, rects, pad=2):
    for x0, y0, x1, y1 in rects:
        if x0 - pad <= x <= x1 + pad and y0 - pad <= y <= y1 + pad:
            return True
    return False


def make_cells(core, macros, n=140, seed=11):
    rng = random.Random(seed)
    cx0, cy0, cx1, cy1 = core
    cw, ch = cx1 - cx0, cy1 - cy0
    rects = macro_rects(macros)
    centers = [(0.32, 0.36), (0.52, 0.40), (0.48, 0.72), (0.68, 0.80), (0.30, 0.80)]
    cells = []
    attempts = 0
    while len(cells) < n and attempts < n * 50:
        attempts += 1
        cxn, cyn = rng.choice(centers)
        nx = min(0.96, max(0.04, cxn + rng.gauss(0, 0.04)))
        ny = min(0.96, max(0.04, cyn + rng.gauss(0, 0.035)))
        x = cx0 + 4 + int(((cx0 + nx * cw) - cx0 - 4) // 3) * 3
        y0 = cy0 + 4
        y = int(y0 + max(0, (int(cy0 + ny * ch) - y0) // 10) * 10)
        w, h = rng.choice([5, 6, 7]), 8
        if in_macro(x, y, rects, 4) or in_macro(x + w, y + h, rects, 4):
            continue
        if x < cx0 + 3 or y < cy0 + 3 or x + w > cx1 - 3 or y + h > cy1 - 3:
            continue
        cells.append((x, y, w, h))
    return cells


def clock_skeleton(core):
    """Light CTS remnant: root + a few trunk segs (kept under signal routes)."""
    cx0, cy0, cx1, cy1 = core
    cw, ch = cx1 - cx0, cy1 - cy0

    def pt(nx, ny):
        return int(cx0 + nx * cw), int(cy0 + ny * ch)

    root = pt(0.30, 0.34)
    hubs = [pt(0.42, 0.38), pt(0.52, 0.44), pt(0.30, 0.72), pt(0.68, 0.80)]
    segs = []
    for h in hubs:
        mid = (h[0], root[1])
        segs.append((root, mid))
        segs.append((mid, h))
    return root, hubs, segs


def gcell_grid(core, nx=8, ny=8):
    cx0, cy0, cx1, cy1 = core
    xs = [int(cx0 + i * (cx1 - cx0) / nx) for i in range(nx + 1)]
    ys = [int(cy0 + i * (cy1 - cy0) / ny) for i in range(ny + 1)]
    return xs, ys


def global_nets(core, macros, seed=5):
    """Coarse G-cell paths (list of waypoints) for a handful of nets."""
    rng = random.Random(seed)
    cx0, cy0, cx1, cy1 = core
    cw, ch = cx1 - cx0, cy1 - cy0
    rects = macro_rects(macros)

    def snap(nx, ny):
        # snap to gcell centers (8x8)
        gx = int(nx * 8) + 0.5
        gy = int(ny * 8) + 0.5
        return int(cx0 + (gx / 8) * cw), int(cy0 + (gy / 8) * ch)

    # endpoints in free regions
    pairs = [
        ((0.30, 0.36), (0.55, 0.42)),
        ((0.48, 0.34), (0.68, 0.78)),
        ((0.32, 0.78), (0.55, 0.40)),
        ((0.50, 0.48), (0.70, 0.82)),
        ((0.28, 0.50), (0.48, 0.74)),
        ((0.60, 0.36), (0.66, 0.50)),
        ((0.34, 0.84), (0.70, 0.86)),
        ((0.44, 0.40), (0.30, 0.70)),
    ]
    nets = []
    for (a, b) in pairs:
        ax, ay = snap(*a)
        bx, by = snap(*b)
        # L then maybe jog to avoid macro center
        mid1 = (bx, ay)
        mid2 = (bx, by)
        path = [ (ax, ay), mid1, mid2 ]
        # if mid in macro, jog
        fixed = [path[0]]
        for p in path[1:]:
            if in_macro(p[0], p[1], rects, 8):
                # push left into channel
                p = (int(cx0 + 0.48 * cw), p[1])
            fixed.append(p)
        # thicken to gcell corridor (store as polyline)
        nets.append(fixed)
    return nets


def tracks_in_region(core, pitch=10):
    """Horizontal + vertical preferred tracks inside core."""
    cx0, cy0, cx1, cy1 = core
    h_tracks = list(range(cy0 + 8, cy1 - 4, pitch))
    v_tracks = list(range(cx0 + 8, cx1 - 4, pitch))
    return h_tracks, v_tracks


def detail_routes(core, macros, seed=13):
    """On-track Manhattan signal routes with vias (layer changes)."""
    rng = random.Random(seed)
    cx0, cy0, cx1, cy1 = core
    cw, ch = cx1 - cx0, cy1 - cy0
    rects = macro_rects(macros)
    h_tracks, v_tracks = tracks_in_region(core, pitch=10)

    def near_track(val, tracks):
        return min(tracks, key=lambda t: abs(t - val))

    routes = []  # list of dicts: segs [(a,b,layer)], vias [(x,y)]
    terminals = [
        ((0.30, 0.36), (0.54, 0.42), M1, M2),
        ((0.48, 0.34), (0.66, 0.78), M2, M3),
        ((0.32, 0.78), (0.52, 0.40), M1, M2),
        ((0.50, 0.48), (0.70, 0.82), M2, M1),
        ((0.28, 0.52), (0.46, 0.74), M3, M2),
        ((0.58, 0.36), (0.66, 0.50), M1, M2),
        ((0.34, 0.84), (0.68, 0.86), M2, M3),
        ((0.44, 0.40), (0.30, 0.70), M1, M3),
        ((0.62, 0.44), (0.48, 0.70), M2, M1),
        ((0.36, 0.38), (0.68, 0.84), M3, M2),
    ]
    for (a, b, la, lb) in terminals:
        ax = near_track(int(cx0 + a[0] * cw), v_tracks)
        ay = near_track(int(cy0 + a[1] * ch), h_tracks)
        bx = near_track(int(cx0 + b[0] * cw), v_tracks)
        by = near_track(int(cy0 + b[1] * ch), h_tracks)
        # prefer: H on M1/M3, V on M2 style
        mid = (bx, ay)
        if in_macro(mid[0], mid[1], rects, 6):
            mid = (near_track(int(cx0 + 0.48 * cw), v_tracks), ay)
            path = [(ax, ay), (mid[0], ay), (mid[0], by), (bx, by)]
        else:
            path = [(ax, ay), mid, (bx, by)]
        segs = []
        vias = []
        for u, v in zip(path, path[1:]):
            layer = la if u[1] == v[1] else lb  # H vs V
            segs.append((u, v, layer))
        # vias at bends
        for p in path[1:-1]:
            vias.append(p)
        routes.append({"segs": segs, "vias": vias})
    return routes


def drc_violations(routes):
    """Pick two intentional shorts/spacing issues for the DRC frame."""
    bend = routes[2]["vias"][0] if routes[2]["vias"] else routes[2]["segs"][0][0]
    v1 = {
        "kind": "spacing",
        "box": (bend[0] - 10, bend[1] - 10, bend[0] + 10, bend[1] + 10),
        "label": "spacing!",
    }
    bend2 = routes[1]["vias"][0] if routes[1]["vias"] else routes[1]["segs"][-1][1]
    v2 = {
        "kind": "short",
        "box": (bend2[0] - 12, bend2[1] - 12, bend2[0] + 12, bend2[1] + 12),
        "label": "short!",
    }
    return [v1, v2]


def critical_net_path(routes):
    """Use one detailed route as timing-critical net."""
    r = routes[1]
    pts = [r["segs"][0][0]]
    for _, b, _ in r["segs"]:
        pts.append(b)
    return pts


def draw_header(draw):
    draw.rectangle([0, 0, W, 48], fill=HEADER)
    draw.text((22, 12), "Physical Design · ROUTING · continuous build-up", fill=WHITE, font=F_TITLE)


def draw_footer(draw):
    draw.rectangle([0, H - 36, W, H], fill=(220, 223, 230))
    draw.text(
        (22, H - 26),
        "Same die accumulates features → final route_opt shows clean DRC + timed nets",
        fill=INK,
        font=F_SMALL,
    )


def wrap_text(draw, text, font_obj, max_w):
    words = text.split()
    lines, line = [], ""
    for w in words:
        trial = (line + " " + w).strip()
        if draw.textlength(trial, font=font_obj) > max_w:
            if line:
                lines.append(line)
            line = w
        else:
            line = trial
    if line:
        lines.append(line)
    return lines


def draw_sidebar(draw, step_idx: int, title: str, blurb: str):
    draw.rounded_rectangle([16, 64, LEFT_W - 16, H - 52], radius=10, fill=PANEL, outline=(210, 214, 222), width=1)
    draw.text((32, 80), title, fill=INK, font=F_H1)
    y = 112
    for line in wrap_text(draw, blurb, F_BODY, LEFT_W - 64):
        draw.text((32, y), line, fill=MUTED, font=F_BODY)
        y += 20
    y += 10
    draw.text((32, y), "BUILD-UP (nothing resets)", fill=INK, font=F_SMALL)
    y += 28
    for i, name in enumerate(STEPS):
        if step_idx < 0:
            mark, color = "○", MUTED
        elif i < step_idx:
            mark, color = "✓", DONE
        elif i == step_idx:
            mark, color = "●", ACTIVE
        else:
            mark, color = "○", MUTED
        draw.text((36, y), f"{mark}  {i+1}. {name}", fill=color, font=F_BODY)
        y += 32


def draw_die(draw, die):
    x0, y0, x1, y1 = die
    draw.rectangle([x0, y0, x1, y1], outline=DIE_EDGE, width=3, fill=WHITE)
    draw.rectangle(core_box(die), outline=CORE, width=2)
    mx = (x0 + x1) // 2
    draw.line([x0, y1 + 18, x1, y1 + 18], fill=INK, width=1)
    draw.line([x0, y1 + 12, x0, y1 + 24], fill=INK, width=1)
    draw.line([x1, y1 + 12, x1, y1 + 24], fill=INK, width=1)
    tw = draw.textlength("WIDTH × HEIGHT", font=F_SMALL)
    draw.text((mx - tw / 2, y1 + 24), "WIDTH × HEIGHT", fill=INK, font=F_SMALL)


def draw_util(draw, core):
    cx0, cy0, cx1, cy1 = core
    draw.rectangle([cx0 + 2, cy0 + 2, cx1 - 2, cy1 - 2], fill=UTIL)


def draw_pins(draw, die):
    x0, y0, x1, y1 = die
    s, gap = 14, 28
    x = x0 + 40
    while x + s < x1 - 30:
        draw.rectangle([x, y0 + 8, x + s, y0 + 8 + s], fill=PIN_TB, outline=DIE_EDGE)
        draw.rectangle([x, y1 - 8 - s, x + s, y1 - 8], fill=PIN_TB, outline=DIE_EDGE)
        x += gap
    y = y0 + 40
    while y + s < y1 - 30:
        draw.rectangle([x0 + 8, y, x0 + 8 + s, y + s], fill=PIN_LR, outline=DIE_EDGE)
        draw.rectangle([x1 - 8 - s, y, x1 - 8, y + s], fill=PIN_LR, outline=DIE_EDGE)
        y += gap


def draw_power(draw, core):
    cx0, cy0, cx1, cy1 = core
    draw.rectangle([cx0, cy0, cx1, cy1], outline=CORE, width=3)
    for i in range(1, 6):
        y = cy0 + i * (cy1 - cy0) // 6
        draw.line([cx0 + 4, y, cx1 - 4, y], fill=PWR_H, width=1)
    for i in range(1, 6):
        x = cx0 + i * (cx1 - cx0) // 6
        draw.line([x, cy0 + 4, x, cy1 - 4], fill=PWR_V, width=1)


def draw_macros(draw, macros):
    for name, x0, y0, x1, y1, fill in macros:
        draw.rectangle([x0 - 1, y0 - 1, x1 + 1, y1 + 1], fill=WHITE)
        draw.rectangle([x0, y0, x1, y1], fill=fill, outline=MACRO_EDGE, width=2)
        tw = draw.textlength(name, font=F_MACRO)
        draw.text((x0 + (x1 - x0 - tw) / 2, y0 + (y1 - y0 - 12) / 2), name, fill=MACRO_EDGE, font=F_MACRO)


def draw_cells(draw, cells):
    for x, y, w, h in cells:
        draw.rectangle([x, y, x + w, y + h], fill=LEGAL)


def draw_cts_light(draw, root, hubs, segs):
    for a, b in segs:
        draw.line([a, b], fill=(120, 180, 185), width=1)
    draw.rectangle([root[0] - 4, root[1] - 3, root[0] + 4, root[1] + 3], fill=CLK, outline=CLK_ROUTE)
    for h in hubs:
        draw.rectangle([h[0] - 3, h[1] - 2, h[0] + 3, h[1] + 2], fill=BUF, outline=BUF_EDGE)


def draw_gcells(draw, xs, ys):
    for x in xs:
        draw.line([x, ys[0], x, ys[-1]], fill=(180, 190, 205), width=1)
    for y in ys:
        draw.line([xs[0], y, xs[-1], y], fill=(180, 190, 205), width=1)


def draw_global_routes(draw, nets):
    colors = [M1, M2, M3, (120, 80, 160), (40, 130, 160)]
    for i, path in enumerate(nets):
        col = colors[i % len(colors)]
        # fat corridor (guide path)
        for a, b in zip(path, path[1:]):
            draw.line([a, b], fill=col, width=6)
        draw.ellipse([path[0][0] - 3, path[0][1] - 3, path[0][0] + 3, path[0][1] + 3], fill=col)
        draw.ellipse([path[-1][0] - 3, path[-1][1] - 3, path[-1][0] + 3, path[-1][1] + 3], fill=col)


def draw_tracks(draw, core, h_tracks, v_tracks, highlight_used=None):
    cx0, cy0, cx1, cy1 = core
    for y in h_tracks:
        draw.line([cx0 + 2, y, cx1 - 2, y], fill=TRACK, width=1)
    for x in v_tracks:
        draw.line([x, cy0 + 2, x, cy1 - 2], fill=(175, 185, 200), width=1)
    if highlight_used:
        for y in highlight_used.get("h", []):
            draw.line([cx0 + 2, y, cx1 - 2, y], fill=M1, width=2)
        for x in highlight_used.get("v", []):
            draw.line([x, cy0 + 2, x, cy1 - 2], fill=M2, width=2)


def used_tracks_from_routes(routes):
    h, v = set(), set()
    for r in routes:
        for a, b, layer in r["segs"]:
            if a[1] == b[1]:
                h.add(a[1])
            if a[0] == b[0]:
                v.add(a[0])
    return {"h": sorted(h)[:12], "v": sorted(v)[:12]}


def draw_detail_routes(draw, routes, skip_idx=None):
    for i, r in enumerate(routes):
        if skip_idx is not None and i in skip_idx:
            continue
        for a, b, layer in r["segs"]:
            draw.line([a, b], fill=layer, width=2)
        for x, y in r["vias"]:
            draw.rectangle([x - 2, y - 2, x + 2, y + 2], fill=WHITE, outline=(40, 40, 40))


def draw_drc(draw, viols):
    for v in viols:
        x0, y0, x1, y1 = v["box"]
        draw.ellipse([x0, y0, x1, y1], outline=DRC, width=3)
        draw.text((x1 + 4, (y0 + y1) // 2 - 6), v["label"], fill=DRC, font=F_LABEL)


def draw_timing(draw, path, improved=False):
    col = OK if improved else CRIT
    for a, b in zip(path, path[1:]):
        draw.line([a, b], fill=col, width=3)
    for p in path:
        draw.ellipse([p[0] - 4, p[1] - 4, p[0] + 4, p[1] + 4], fill=col, outline=WHITE)
    mid = path[len(path) // 2]
    if improved:
        draw.text((mid[0] + 8, mid[1] - 16), "buffer/layer↑  WNS≥0", fill=OK, font=F_LABEL)
    else:
        draw.text((mid[0] + 8, mid[1] - 16), "long net  WNS<0", fill=CRIT, font=F_LABEL)


def status_box(draw, die, text, color=INK, border=None):
    x0, y0, x1, y1 = die
    bx0, by0, bx1, by1 = x0 + 10, y1 - 52, x1 - 10, y1 - 14
    draw.rounded_rectangle([bx0, by0, bx1, by1], radius=6, fill=WHITE, outline=border or (180, 185, 195), width=2)
    tw = draw.textlength(text, font=F_TINY)
    draw.text(((bx0 + bx1 - tw) / 2, by0 + 10), text, fill=color, font=F_TINY)


def legend(draw, die, items):
    x = die[0] + 8
    y = die[1] - 28
    for label, col in items:
        draw.rectangle([x, y, x + 12, y + 12], fill=col, outline=DIE_EDGE)
        draw.text((x + 16, y - 1), label, fill=MUTED, font=F_TINY)
        x += 16 + int(draw.textlength(label, font=F_TINY)) + 12


def make_base():
    im = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(im)
    draw_header(draw)
    draw_footer(draw)
    return im, draw


def paint_base(draw, die, core, macros, cells, root, hubs, csegs, light_cts=True):
    draw_die(draw, die)
    draw_util(draw, core)
    draw_pins(draw, die)
    draw_power(draw, core)
    draw_macros(draw, macros)
    draw_cells(draw, cells)
    if light_cts:
        draw_cts_light(draw, root, hubs, csegs)


def render_frames():
    FRAMES.mkdir(parents=True, exist_ok=True)
    die = die_box()
    core = core_box(die)
    macros = abs_macros(core, CLEAN_MACROS)
    cells = make_cells(core, macros)
    root, hubs, csegs = clock_skeleton(core)
    xs, ys = gcell_grid(core)
    nets = global_nets(core, macros)
    h_tracks, v_tracks = tracks_in_region(core, pitch=10)
    routes = detail_routes(core, macros)
    used = used_tracks_from_routes(routes)
    viols = drc_violations(routes)
    crit = critical_net_path(routes)

    frames = []

    # f00 start
    im, draw = make_base()
    draw_sidebar(draw, -1, "Start — CTS ready", "Routing begins on cts_done. Clock kept light; signals next.")
    paint_base(draw, die, core, macros, cells, root, hubs, csegs)
    status_box(draw, die, "Input: cts_done.enc — signal nets not routed yet")
    p = FRAMES / "f00.png"
    im.save(p)
    frames.append(p)

    # f01 global
    im, draw = make_base()
    draw_sidebar(
        draw,
        0,
        "1 / 5 Global routing",
        "Assign G-cell corridors. Guide paths only — not on tracks yet.",
    )
    paint_base(draw, die, core, macros, cells, root, hubs, csegs)
    draw_gcells(draw, xs, ys)
    draw_global_routes(draw, nets)
    # redraw macros/cells on top so corridors go “under” macros visually where needed
    draw_macros(draw, macros)
    legend(draw, die, [("G-cell", (180, 190, 205)), ("global net", M1), ("clock", CLK)])
    status_box(draw, die, "Layer: GLOBAL route (coarse corridors)", color=M1, border=M1)
    p = FRAMES / "f01.png"
    im.save(p)
    frames.append(p)

    # f02 track assignment
    im, draw = make_base()
    draw_sidebar(
        draw,
        1,
        "2 / 5 Track assignment",
        "Map corridors onto metal tracks (H/V preferred directions).",
    )
    paint_base(draw, die, core, macros, cells, root, hubs, csegs)
    draw_gcells(draw, xs, ys)
    draw_tracks(draw, core, h_tracks, v_tracks, highlight_used=used)
    draw_global_routes(draw, nets)
    draw_macros(draw, macros)
    legend(draw, die, [("tracks", TRACK), ("used H", M1), ("used V", M2)])
    status_box(draw, die, "Layers: global + TRACK ASSIGNMENT", color=M2, border=M2)
    p = FRAMES / "f02.png"
    im.save(p)
    frames.append(p)

    # f03 detail
    im, draw = make_base()
    draw_sidebar(
        draw,
        2,
        "3 / 5 Detail routing",
        "Pin-to-pin wires on tracks + vias. Global guides remain as context.",
    )
    paint_base(draw, die, core, macros, cells, root, hubs, csegs)
    # faint global
    for path in nets:
        for a, b in zip(path, path[1:]):
            draw.line([a, b], fill=(200, 210, 220), width=3)
    draw_tracks(draw, core, h_tracks[::2], v_tracks[::2])  # lighter track density
    draw_detail_routes(draw, routes)
    draw_macros(draw, macros)
    legend(draw, die, [("M1", M1), ("M2", M2), ("M3", M3), ("via", (40, 40, 40))])
    status_box(draw, die, "Layers: tracks + DETAIL route (wires + vias)", color=M3, border=M3)
    p = FRAMES / "f03.png"
    im.save(p)
    frames.append(p)

    # f04 DRC violations
    im, draw = make_base()
    draw_sidebar(
        draw,
        3,
        "4 / 5 DRC fix",
        "Catch shorts/spacing/via issues on the full routed picture.",
    )
    paint_base(draw, die, core, macros, cells, root, hubs, csegs)
    draw_detail_routes(draw, routes)
    draw_macros(draw, macros)
    draw_drc(draw, viols)
    status_box(draw, die, "Same full route — DRC violations highlighted", color=DRC, border=DRC)
    p = FRAMES / "f04.png"
    im.save(p)
    frames.append(p)

    # f04b DRC fixed (jog/open space)
    im, draw = make_base()
    draw_sidebar(
        draw,
        3,
        "4 / 5 DRC fix",
        "Jog / rip-up & reroute. Clean DRC, topology mostly kept.",
    )
    paint_base(draw, die, core, macros, cells, root, hubs, csegs)
    # slightly nudged routes = "fixed"
    fixed_routes = []
    for i, r in enumerate(routes):
        if i in (1, 2):
            segs = []
            for a, b, layer in r["segs"]:
                # nudge verticals a track pitch
                if a[0] == b[0]:
                    a = (a[0] + 10, a[1])
                    b = (b[0] + 10, b[1])
                segs.append((a, b, layer))
            vias = [(x + 10, y) for x, y in r["vias"]]
            fixed_routes.append({"segs": segs, "vias": vias})
        else:
            fixed_routes.append(r)
    draw_detail_routes(draw, fixed_routes)
    draw_macros(draw, macros)
    status_box(draw, die, "Clean ✓ — shorts/spacing cleared", color=OK, border=OK)
    p = FRAMES / "f04b.png"
    im.save(p)
    frames.append(p)

    # f05 timing opt bad
    im, draw = make_base()
    draw_sidebar(
        draw,
        4,
        "5 / 5 Timing optimization",
        "Post-route WNS: layer promote, buffer, or re-route critical net.",
    )
    paint_base(draw, die, core, macros, cells, root, hubs, csegs)
    draw_detail_routes(draw, fixed_routes)
    draw_macros(draw, macros)
    draw_timing(draw, crit, improved=False)
    status_box(draw, die, "Critical net highlighted — optimize in place", color=CRIT, border=CRIT)
    p = FRAMES / "f05.png"
    im.save(p)
    frames.append(p)

    # f05b timing fixed
    im, draw = make_base()
    draw_sidebar(
        draw,
        4,
        "5 / 5 Timing optimization",
        "Layer bump + buffer. DRC still clean. Ready for signoff.",
    )
    paint_base(draw, die, core, macros, cells, root, hubs, csegs)
    draw_detail_routes(draw, fixed_routes)
    draw_macros(draw, macros)
    # show improved path (same geometry, green) + a buffer
    draw_timing(draw, crit, improved=True)
    mid = crit[len(crit) // 2]
    draw.rectangle([mid[0] - 6, mid[1] - 5, mid[0] + 6, mid[1] + 5], fill=BUF, outline=BUF_EDGE)
    status_box(draw, die, "route_opt done — DRC clean + WNS≥0 → signoff", color=OK, border=OK)
    p = FRAMES / "f05b.png"
    im.save(p)
    frames.append(p)

    # f06 handoff
    im, draw = make_base()
    draw.rounded_rectangle([16, 64, LEFT_W - 16, H - 52], radius=10, fill=PANEL, outline=(210, 214, 222), width=1)
    draw.text((32, 80), "Done — routing complete", fill=INK, font=F_H1)
    y = 112
    for line in wrap_text(
        draw,
        "Nets detailed & clean. Timing closed enough for extraction / signoff.",
        F_BODY,
        LEFT_W - 64,
    ):
        draw.text((32, y), line, fill=MUTED, font=F_BODY)
        y += 20
    y += 10
    draw.text((32, y), "BUILD-UP (nothing resets)", fill=INK, font=F_SMALL)
    y += 28
    for i, name in enumerate(STEPS):
        draw.text((36, y), f"✓  {i+1}. {name}", fill=DONE, font=F_BODY)
        y += 32

    paint_base(draw, die, core, macros, cells, root, hubs, csegs)
    draw_detail_routes(draw, fixed_routes)
    draw_macros(draw, macros)
    draw_timing(draw, crit, improved=True)
    legend(draw, die, [("M1", M1), ("M2", M2), ("M3", M3), ("crit", OK)])
    x0, y0, x1, y1 = die
    draw.rounded_rectangle([x0 + 10, y1 - 70, x0 + 260, y1 - 14], radius=6, fill=WHITE, outline=(180, 185, 195), width=2)
    draw.text((x0 + 20, y1 - 58), "defOut route.def", fill=INK, font=F_TINY)
    draw.text((x0 + 20, y1 - 40), "saveDesign route_done.enc", fill=INK, font=F_TINY)
    draw.rounded_rectangle([x1 - 240, y1 - 70, x1 - 10, y1 - 14], radius=6, fill=WHITE, outline=OK, width=2)
    draw.text((x1 - 228, y1 - 58), "ROUTE SAVED", fill=OK, font=F_LABEL)
    draw.text((x1 - 228, y1 - 38), "next → signoff / fill", fill=MUTED, font=F_TINY)
    p = FRAMES / "f06.png"
    im.save(p)
    frames.append(p)

    images = [Image.open(fp).convert("P", palette=Image.ADAPTIVE, colors=180) for fp in frames]
    durations = [1600] * (len(images) - 1) + [3200]
    images[0].save(GIF, save_all=True, append_images=images[1:], duration=durations, loop=0, optimize=True)
    ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
    images[0].save(ARTIFACT, save_all=True, append_images=images[1:], duration=durations, loop=0, optimize=True)
    print(f"Wrote {len(frames)} frames → {GIF}")
    print(f"Artifact → {ARTIFACT}")


if __name__ == "__main__":
    render_frames()
