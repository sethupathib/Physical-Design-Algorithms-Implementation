#!/usr/bin/env python3
"""Generate continuous-build-up PLACEMENT teaching GIF (1280x720).

Starts from a finished floorplan (macros + power + pins) and accumulates:
  global place → HFNS → detail place → legalize → density/congestion → timing opt
"""

from __future__ import annotations

import os
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUT_DIR = Path(__file__).resolve().parent
FRAMES = OUT_DIR / "placement_frames"
GIF = OUT_DIR / "placement_flow.gif"
ARTIFACT = Path("/opt/cursor/artifacts/placement_flow.gif")

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
CELL = (70, 110, 170)
CELL_LIGHT = (120, 155, 205)
BUF = (180, 90, 40)
BUF_EDGE = (120, 50, 20)
LEGAL = (50, 130, 90)
HOT = (220, 70, 50)
WARM = (230, 160, 60)
COOL = (90, 170, 120)
CRIT = (200, 40, 50)
OK = (40, 140, 70)
WHITE = (255, 255, 255)
ROW = (200, 210, 220)

STEPS = [
    "Global placement",
    "HFNS (high-fanout)",
    "Detail placement",
    "Legalization",
    "Density / congestion",
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
F_H1 = font(19, True)
F_BODY = font(14)
F_SMALL = font(12)
F_TINY = font(11)
F_MACRO = font(11, True)
F_LABEL = font(12, True)


def die_box():
    x0 = LEFT_W + 70
    y0 = 90
    size = 520
    return x0, y0, x0 + size, y0 + size


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
    out = []
    for name, nx0, ny0, nx1, ny1, fill in macros:
        out.append(
            (
                name,
                int(cx0 + nx0 * cw),
                int(cy0 + ny0 * ch),
                int(cx0 + nx1 * cw),
                int(cy0 + ny1 * ch),
                fill,
            )
        )
    return out


def macro_rects(macros):
    return [(m[1], m[2], m[3], m[4]) for m in macros]


def in_macro(x, y, rects, pad=2):
    for x0, y0, x1, y1 in rects:
        if x0 - pad <= x <= x1 + pad and y0 - pad <= y <= y1 + pad:
            return True
    return False


def free_regions(core, macros):
    """Rough free-space pockets between macros (normalized later as point clouds)."""
    cx0, cy0, cx1, cy1 = core
    rects = macro_rects(macros)
    # sample candidate points in core, keep those outside macros
    return cx0, cy0, cx1, cy1, rects


def make_cells(core, macros, n=220, seed=7, mode="global"):
    """Return list of (x, y, w, h) cell boxes in free space."""
    rng = random.Random(seed)
    cx0, cy0, cx1, cy1, rects = free_regions(core, macros)
    cells = []
    # attraction centers (logic clusters)
    centers = [
        (0.32, 0.38),
        (0.55, 0.40),
        (0.48, 0.72),
        (0.68, 0.78),
        (0.30, 0.78),
    ]
    cw, ch = cx1 - cx0, cy1 - cy0
    row_h = 8 if mode in ("detail", "legal", "density", "timing") else 6
    attempts = 0
    while len(cells) < n and attempts < n * 40:
        attempts += 1
        cxn, cyn = rng.choice(centers)
        if mode == "global":
            jx, jy = rng.gauss(0, 0.10), rng.gauss(0, 0.10)
            w, h = rng.choice([4, 5, 6, 7]), row_h
        elif mode == "hfns":
            jx, jy = rng.gauss(0, 0.08), rng.gauss(0, 0.08)
            w, h = rng.choice([4, 5, 6]), row_h
        elif mode == "detail":
            jx, jy = rng.gauss(0, 0.045), rng.gauss(0, 0.04)
            w, h = rng.choice([5, 6, 7, 8]), row_h
        else:  # legal / density / timing — row snapped
            jx, jy = rng.gauss(0, 0.035), rng.gauss(0, 0.03)
            w, h = rng.choice([5, 6, 7, 8, 9]), 8
        nx = min(0.96, max(0.04, cxn + jx))
        ny = min(0.96, max(0.04, cyn + jy))
        x = int(cx0 + nx * cw)
        y = int(cy0 + ny * ch)
        if mode in ("legal", "density", "timing"):
            # snap to rows
            y0 = cy0 + 4
            row = max(0, (y - y0) // 10)
            y = int(y0 + row * 10)
            x = cx0 + 4 + ((x - cx0 - 4) // 3) * 3
        if in_macro(x, y, rects, pad=4) or in_macro(x + w, y + h, rects, pad=4):
            continue
        if x < cx0 + 3 or y < cy0 + 3 or x + w > cx1 - 3 or y + h > cy1 - 3:
            continue
        cells.append((x, y, w, h))
    return cells


def hfns_tree(core, macros):
    """Driver + buffer tree points for a high-fanout net (e.g. reset).

    Coordinates stay in free channels between macros (not on MACRO / DDR / SRAM).
    """
    cx0, cy0, cx1, cy1 = core
    cw, ch = cx1 - cx0, cy1 - cy0
    rects = macro_rects(macros)

    def pt(nx, ny):
        return (int(cx0 + nx * cw), int(cy0 + ny * ch))

    # Free-channel anchors (validated against CLEAN_MACROS packing)
    driver = pt(0.30, 0.34)
    level1 = [pt(0.42, 0.33), pt(0.50, 0.42), pt(0.30, 0.72)]
    level2 = [
        pt(0.54, 0.30),
        pt(0.56, 0.40),
        pt(0.66, 0.48),
        pt(0.48, 0.50),
        pt(0.28, 0.84),
        pt(0.68, 0.84),
    ]
    rng = random.Random(11)
    # sink bands in free pockets only
    bands = [(0.28, 0.36, 0.30, 0.38), (0.40, 0.66, 0.30, 0.52), (0.26, 0.32, 0.66, 0.90), (0.64, 0.74, 0.72, 0.90)]
    sinks = []
    for _ in range(16):
        x0, x1, y0, y1 = rng.choice(bands)
        s = pt(rng.uniform(x0, x1), rng.uniform(y0, y1))
        if not in_macro(s[0], s[1], rects, pad=6):
            sinks.append(s)
    for p in [driver] + level1 + level2:
        if in_macro(p[0], p[1], rects, pad=4):
            raise SystemExit(f"HFNS point landed on macro: {p}")
    return driver, level1, level2, sinks


def critical_path(core, macros):
    """Critical path through free channels (avoid macro interiors)."""
    cx0, cy0, cx1, cy1 = core
    cw, ch = cx1 - cx0, cy1 - cy0
    rects = macro_rects(macros)
    pts = [
        (cx0 + 0.30 * cw, cy0 + 0.34 * ch),
        (cx0 + 0.44 * cw, cy0 + 0.36 * ch),
        (cx0 + 0.54 * cw, cy0 + 0.44 * ch),
        (cx0 + 0.66 * cw, cy0 + 0.50 * ch),
        (cx0 + 0.68 * cw, cy0 + 0.78 * ch),
    ]
    out = [(int(x), int(y)) for x, y in pts]
    for p in out:
        if in_macro(p[0], p[1], rects, pad=2):
            raise SystemExit(f"crit path on macro: {p}")
    return out


def draw_header(draw):
    draw.rectangle([0, 0, W, 48], fill=HEADER)
    draw.text((22, 12), "Physical Design · PLACEMENT · continuous build-up", fill=WHITE, font=F_TITLE)


def draw_footer(draw):
    draw.rectangle([0, H - 36, W, H], fill=(220, 223, 230))
    draw.text(
        (22, H - 26),
        "Same die accumulates features → final place_opt shows LEGAL + timed placement",
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
        y += 30


def draw_die(draw, die, show_dims=True):
    x0, y0, x1, y1 = die
    draw.rectangle([x0, y0, x1, y1], outline=DIE_EDGE, width=3, fill=WHITE)
    c = core_box(die)
    draw.rectangle(c, outline=CORE, width=2)
    if show_dims:
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


def draw_rows(draw, core, macros):
    cx0, cy0, cx1, cy1 = core
    rects = macro_rects(macros)
    y = cy0 + 4
    while y < cy1 - 6:
        # draw row guide segments that skip macros
        x = cx0 + 4
        segs = []
        while x < cx1 - 4:
            if in_macro(x, y + 4, rects, pad=1):
                x += 2
                continue
            x2 = x
            while x2 < cx1 - 4 and not in_macro(x2, y + 4, rects, pad=1):
                x2 += 2
            if x2 - x > 8:
                draw.line([x, y + 8, x2, y + 8], fill=ROW, width=1)
            x = x2 + 2
        y += 10


def draw_cells(draw, cells, color=CELL, outline=None):
    for x, y, w, h in cells:
        draw.rectangle([x, y, x + w, y + h], fill=color, outline=outline)


def draw_hfns(draw, tree, show_sinks=True):
    driver, level1, level2, sinks = tree
    # edges
    for b in level1:
        draw.line([driver, b], fill=BUF, width=2)
    for i, b in enumerate(level2):
        parent = level1[i % len(level1)]
        draw.line([parent, b], fill=BUF, width=1)
    if show_sinks:
        for i, s in enumerate(sinks):
            parent = level2[i % len(level2)]
            draw.line([parent, s], fill=(210, 150, 100), width=1)
            draw.ellipse([s[0] - 2, s[1] - 2, s[0] + 2, s[1] + 2], fill=(160, 100, 50))
    # buffers
    for p in [driver] + level1 + level2:
        draw.rectangle([p[0] - 5, p[1] - 4, p[0] + 5, p[1] + 4], fill=BUF, outline=BUF_EDGE)
    draw.text((driver[0] + 8, driver[1] - 10), "HFNS", fill=BUF_EDGE, font=F_LABEL)


def density_overlay(im, core, cells, macros):
    """Soft congestion heatmap over free space."""
    overlay = Image.new("RGBA", im.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    cx0, cy0, cx1, cy1 = core
    gw, gh = 14, 12
    # count cells per bin
    bins = {}
    for x, y, w, h in cells:
        bx = (x - cx0) // gw
        by = (y - cy0) // gh
        bins[(bx, by)] = bins.get((bx, by), 0) + 1
    rects = macro_rects(macros)
    for (bx, by), cnt in bins.items():
        x0 = cx0 + bx * gw
        y0 = cy0 + by * gh
        if in_macro(x0 + gw // 2, y0 + gh // 2, rects):
            continue
        # map count to color
        t = min(1.0, cnt / 6.0)
        if t < 0.35:
            col = (*COOL, int(50 + 80 * t))
        elif t < 0.7:
            col = (*WARM, int(70 + 90 * t))
        else:
            col = (*HOT, int(90 + 100 * t))
        d.rectangle([x0, y0, x0 + gw, y0 + gh], fill=col)
    return Image.alpha_composite(im.convert("RGBA"), overlay).convert("RGB")


def draw_timing(draw, path, improved=False):
    # path polyline
    for a, b in zip(path, path[1:]):
        draw.line([a, b], fill=CRIT if not improved else OK, width=3)
    for i, p in enumerate(path):
        r = 6 if i in (0, len(path) - 1) else 4
        col = CRIT if not improved else OK
        draw.ellipse([p[0] - r, p[1] - r, p[0] + r, p[1] + r], fill=col, outline=WHITE)
    # upsizing / buffer callouts
    mid = path[2]
    if not improved:
        draw.text((mid[0] + 10, mid[1] - 18), "WNS < 0", fill=CRIT, font=F_LABEL)
    else:
        draw.text((mid[0] + 10, mid[1] - 18), "VT/size + buf → WNS≥0", fill=OK, font=F_LABEL)
        # show a sized cell
        draw.rectangle([mid[0] - 8, mid[1] - 6, mid[0] + 10, mid[1] + 6], outline=OK, width=2)


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
        x += 16 + int(draw.textlength(label, font=F_TINY)) + 14


def make_base():
    im = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(im)
    draw_header(draw)
    draw_footer(draw)
    return im, draw


def paint_floorplan(draw, die, core, macros, cells=None, cell_color=CELL, rows=False):
    draw_die(draw, die)
    draw_util(draw, core)
    draw_pins(draw, die)
    draw_power(draw, core)
    if rows:
        draw_rows(draw, core, macros)
    draw_macros(draw, macros)
    if cells:
        draw_cells(draw, cells, color=cell_color)


def render_frames():
    FRAMES.mkdir(parents=True, exist_ok=True)
    die = die_box()
    core = core_box(die)
    macros = abs_macros(core, CLEAN_MACROS)
    tree = hfns_tree(core, macros)
    path = critical_path(core, macros)

    cells_global = make_cells(core, macros, n=200, seed=7, mode="global")
    cells_detail = make_cells(core, macros, n=240, seed=9, mode="detail")
    cells_legal = make_cells(core, macros, n=260, seed=11, mode="legal")

    frames = []

    # f00 — start from FP
    im, draw = make_base()
    draw_sidebar(
        draw,
        -1,
        "Start — floorplan ready",
        "Placement begins on the saved FP. Macros/power/pins stay.",
    )
    paint_floorplan(draw, die, core, macros)
    status_box(draw, die, "Input: floorplan.def / fp_done.enc — stdcells not placed yet")
    p = FRAMES / "f00.png"
    im.save(p)
    frames.append(p)

    # f01 — global place
    im, draw = make_base()
    draw_sidebar(
        draw,
        0,
        "1 / 6 Global placement",
        "Spread stdcells by wirelength/density. Overlaps OK for now.",
    )
    paint_floorplan(draw, die, core, macros, cells_global, cell_color=CELL_LIGHT)
    legend(draw, die, [("macros", MACRO_FILL), ("stdcells", CELL_LIGHT), ("power", PWR_H)])
    status_box(draw, die, "Layer: GLOBAL place (approx positions, overlaps allowed)")
    p = FRAMES / "f01.png"
    im.save(p)
    frames.append(p)

    # f02 — HFNS
    im, draw = make_base()
    draw_sidebar(
        draw,
        1,
        "2 / 6 HFNS (high-fanout)",
        "Build buffer trees for reset/scan/en. Global cells remain.",
    )
    paint_floorplan(draw, die, core, macros, cells_global, cell_color=CELL_LIGHT)
    draw_hfns(draw, tree)
    legend(draw, die, [("stdcells", CELL_LIGHT), ("HFNS buf", BUF)])
    status_box(draw, die, "Layers: global + HFNS buffer tree", color=BUF, border=BUF)
    p = FRAMES / "f02.png"
    im.save(p)
    frames.append(p)

    # f03 — detail place
    im, draw = make_base()
    draw_sidebar(
        draw,
        2,
        "3 / 6 Detail placement",
        "Tighten clusters, refine local WL. HFNS buffers stay.",
    )
    paint_floorplan(draw, die, core, macros, cells_detail, cell_color=CELL)
    draw_hfns(draw, tree, show_sinks=False)
    status_box(draw, die, "Layers: global→DETAIL + HFNS")
    p = FRAMES / "f03.png"
    im.save(p)
    frames.append(p)

    # f04 — legalization
    im, draw = make_base()
    draw_sidebar(
        draw,
        3,
        "4 / 6 Legalization",
        "Snap to rows/sites. Remove overlaps. Legal = manufacturable.",
    )
    paint_floorplan(draw, die, core, macros, cells_legal, cell_color=LEGAL, rows=True)
    draw_hfns(draw, tree, show_sinks=False)
    legend(draw, die, [("rows", ROW), ("legal cells", LEGAL), ("HFNS", BUF)])
    status_box(draw, die, "LEGAL: on-row, site-aligned, no overlap", color=OK, border=OK)
    p = FRAMES / "f04.png"
    im.save(p)
    frames.append(p)

    # f05 — density / congestion
    im, draw = make_base()
    draw_sidebar(
        draw,
        4,
        "5 / 6 Density / congestion",
        "Check hotspots. May inflate/spread before timing opt.",
    )
    paint_floorplan(draw, die, core, macros, cells=None, rows=True)
    im = density_overlay(im, core, cells_legal, macros)
    draw = ImageDraw.Draw(im)
    draw_macros(draw, macros)
    draw_cells(draw, cells_legal, color=LEGAL)
    draw_hfns(draw, tree, show_sinks=False)
    legend(draw, die, [("cool", COOL), ("warm", WARM), ("hot", HOT)])
    status_box(draw, die, "Overlay: density / congestion map on LEGAL place", color=HOT, border=HOT)
    p = FRAMES / "f05.png"
    im.save(p)
    frames.append(p)

    # f06 — timing opt (pre)
    im, draw = make_base()
    draw_sidebar(
        draw,
        5,
        "6 / 6 Timing optimization",
        "Fix WNS/TNS: resize, VT swap, buffer critical paths.",
    )
    paint_floorplan(draw, die, core, macros, cells_legal, cell_color=LEGAL, rows=True)
    draw_hfns(draw, tree, show_sinks=False)
    draw_timing(draw, path, improved=False)
    status_box(draw, die, "Critical path highlighted — optimize in place", color=CRIT, border=CRIT)
    p = FRAMES / "f06.png"
    im.save(p)
    frames.append(p)

    # f06b — timing opt done
    im, draw = make_base()
    draw_sidebar(
        draw,
        5,
        "6 / 6 Timing optimization",
        "Path closed. Legal placement + HFNS still intact.",
    )
    paint_floorplan(draw, die, core, macros, cells_legal, cell_color=LEGAL, rows=True)
    draw_hfns(draw, tree, show_sinks=False)
    draw_timing(draw, path, improved=True)
    status_box(draw, die, "place_opt done — LEGAL + timed → ready for CTS", color=OK, border=OK)
    p = FRAMES / "f06b.png"
    im.save(p)
    frames.append(p)

    # f07 — exit / handoff
    im, draw = make_base()
    draw.rounded_rectangle([16, 64, LEFT_W - 16, H - 52], radius=10, fill=PANEL, outline=(210, 214, 222), width=1)
    draw.text((32, 80), "Done — placement complete", fill=INK, font=F_H1)
    y = 112
    for line in wrap_text(
        draw,
        "Export LEGAL placement. Density checked. Timing closed enough for CTS.",
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
        y += 30

    paint_floorplan(draw, die, core, macros, cells_legal, cell_color=LEGAL, rows=True)
    draw_hfns(draw, tree, show_sinks=False)
    draw_timing(draw, path, improved=True)
    legend(draw, die, [("legal", LEGAL), ("HFNS", BUF), ("crit path", OK)])
    x0, y0, x1, y1 = die
    draw.rounded_rectangle([x0 + 10, y1 - 70, x0 + 260, y1 - 14], radius=6, fill=WHITE, outline=(180, 185, 195), width=2)
    draw.text((x0 + 20, y1 - 58), "defOut place.def", fill=INK, font=F_TINY)
    draw.text((x0 + 20, y1 - 40), "saveDesign place_done.enc", fill=INK, font=F_TINY)
    draw.rounded_rectangle([x1 - 230, y1 - 70, x1 - 10, y1 - 14], radius=6, fill=WHITE, outline=OK, width=2)
    draw.text((x1 - 218, y1 - 58), "PLACE SAVED", fill=OK, font=F_LABEL)
    draw.text((x1 - 218, y1 - 38), "next → CTS", fill=MUTED, font=F_TINY)
    p = FRAMES / "f07.png"
    im.save(p)
    frames.append(p)

    images = [Image.open(fp).convert("P", palette=Image.ADAPTIVE, colors=160) for fp in frames]
    durations = [1600] * (len(images) - 1) + [3200]
    images[0].save(GIF, save_all=True, append_images=images[1:], duration=durations, loop=0, optimize=True)
    ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
    images[0].save(ARTIFACT, save_all=True, append_images=images[1:], duration=durations, loop=0, optimize=True)
    print(f"Wrote {len(frames)} frames → {GIF}")
    print(f"Artifact → {ARTIFACT}")


if __name__ == "__main__":
    render_frames()
