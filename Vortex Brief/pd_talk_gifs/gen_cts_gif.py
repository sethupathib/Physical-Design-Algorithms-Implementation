#!/usr/bin/env python3
"""Generate continuous-build-up CTS teaching GIF (1280x720).

Starts from LEGAL placement and accumulates:
  cluster → balance → clock route → post-route conditioning → ID/skew/timing opt
"""

from __future__ import annotations

import os
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUT_DIR = Path(__file__).resolve().parent
FRAMES = OUT_DIR / "cts_frames"
GIF = OUT_DIR / "cts_flow.gif"
ARTIFACT = Path("/opt/cursor/artifacts/cts_flow.gif")

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
CLK = (20, 140, 150)  # teal clock (avoid purple default)
CLK_EDGE = (10, 90, 100)
CLK_ROUTE = (15, 110, 120)
BUF = (180, 90, 40)
BUF_EDGE = (120, 50, 20)
CLUSTER = [
    (66, 133, 244, 55),
    (52, 168, 120, 55),
    (242, 153, 50, 55),
    (219, 80, 74, 55),
]
CLUSTER_EDGE = [(40, 90, 200), (30, 120, 85), (190, 110, 30), (170, 50, 45)]
SINK = (40, 50, 70)
DELAY_BAD = (200, 50, 50)
DELAY_OK = (40, 140, 70)
COND = (100, 70, 160)
WHITE = (255, 255, 255)
ROW = (200, 210, 220)

STEPS = [
    "Sink clustering",
    "Tree balancing",
    "Clock routing",
    "Post-route conditioning",
    "Opt: ID / skew / timing",
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


def make_cells(core, macros, n=180, seed=11):
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
        w, h = rng.choice([5, 6, 7, 8]), 8
        if in_macro(x, y, rects, 4) or in_macro(x + w, y + h, rects, 4):
            continue
        if x < cx0 + 3 or y < cy0 + 3 or x + w > cx1 - 3 or y + h > cy1 - 3:
            continue
        cells.append((x, y, w, h))
    return cells


def make_sinks(core, macros, seed=21):
    """Clock sinks (flops) in free clusters — 4 natural groups."""
    rng = random.Random(seed)
    cx0, cy0, cx1, cy1 = core
    cw, ch = cx1 - cx0, cy1 - cy0
    rects = macro_rects(macros)
    # (cluster_id, nx_lo, nx_hi, ny_lo, ny_hi, count)
    bands = [
        (0, 0.28, 0.38, 0.30, 0.42, 14),
        (1, 0.44, 0.68, 0.30, 0.48, 16),
        (2, 0.26, 0.34, 0.66, 0.90, 12),
        (3, 0.62, 0.74, 0.72, 0.90, 14),
    ]
    sinks = []  # (x, y, cluster_id)
    for cid, x0, x1, y0, y1, cnt in bands:
        got = 0
        tries = 0
        while got < cnt and tries < cnt * 30:
            tries += 1
            x = int(cx0 + rng.uniform(x0, x1) * cw)
            y = int(cy0 + rng.uniform(y0, y1) * ch)
            if in_macro(x, y, rects, 6):
                continue
            sinks.append((x, y, cid))
            got += 1
    return sinks


def cluster_centers(sinks):
    centers = {}
    for x, y, cid in sinks:
        centers.setdefault(cid, []).append((x, y))
    out = {}
    for cid, pts in centers.items():
        out[cid] = (sum(p[0] for p in pts) // len(pts), sum(p[1] for p in pts) // len(pts))
    return out


def clock_root(core):
    """Clock root near top/center free channel (from PLL region conceptually)."""
    cx0, cy0, cx1, cy1 = core
    cw, ch = cx1 - cx0, cy1 - cy0
    return int(cx0 + 0.30 * cw), int(cy0 + 0.34 * ch)


def balance_tree(root, centers):
    """2-level balanced tree: root → L1 hubs → cluster centers."""
    # place L1 hubs as midpoints toward clusters (balanced depths)
    c0, c1, c2, c3 = centers[0], centers[1], centers[2], centers[3]
    # two L1 nodes for left/right balance
    l1_a = ((root[0] + (c0[0] + c2[0]) // 2) // 2, (root[1] + (c0[1] + c2[1]) // 2) // 2)
    l1_b = ((root[0] + (c1[0] + c3[0]) // 2) // 2, (root[1] + (c1[1] + c3[1]) // 2) // 2)
    # nudge into free space
    l1_a = (l1_a[0], max(root[1] + 20, l1_a[1]))
    l1_b = (l1_b[0] + 10, max(root[1] + 10, l1_b[1] - 10))
    # L2 = cluster centers (local clock buffers)
    edges = [
        (root, l1_a),
        (root, l1_b),
        (l1_a, c0),
        (l1_a, c2),
        (l1_b, c1),
        (l1_b, c3),
    ]
    nodes = [root, l1_a, l1_b, c0, c1, c2, c3]
    return nodes, edges, (l1_a, l1_b)


def manhattan_route(a, b):
    """L-shaped clock route segments."""
    ax, ay = a
    bx, by = b
    mid = (bx, ay)
    return [(ax, ay), mid, (bx, by)]


def route_tree(edges):
    segs = []
    for a, b in edges:
        pts = manhattan_route(a, b)
        for u, v in zip(pts, pts[1:]):
            if u != v:
                segs.append((u, v))
    return segs


def leaf_routes(centers, sinks):
    """Short Manhattan stubs from cluster center to each sink."""
    segs = []
    for x, y, cid in sinks:
        c = centers[cid]
        pts = manhattan_route(c, (x, y))
        for u, v in zip(pts, pts[1:]):
            if u != v:
                segs.append((u, v))
    return segs


def draw_header(draw):
    draw.rectangle([0, 0, W, 48], fill=HEADER)
    draw.text((22, 12), "Physical Design · CTS · continuous build-up", fill=WHITE, font=F_TITLE)


def draw_footer(draw):
    draw.rectangle([0, H - 36, W, H], fill=(220, 223, 230))
    draw.text(
        (22, H - 26),
        "Same die accumulates features → final cts_opt shows balanced clock + closed skew",
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
    c = core_box(die)
    draw.rectangle(c, outline=CORE, width=2)
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


def draw_sinks(draw, sinks, colored=False):
    for x, y, cid in sinks:
        col = CLUSTER_EDGE[cid] if colored else SINK
        draw.rectangle([x - 2, y - 2, x + 2, y + 2], fill=col)


def cluster_bbox(sinks, cid, pad=14):
    pts = [(x, y) for x, y, c in sinks if c == cid]
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return min(xs) - pad, min(ys) - pad, max(xs) + pad, max(ys) + pad


def draw_clusters(draw, sinks, centers, show_labels=True):
    for cid in range(4):
        x0, y0, x1, y1 = cluster_bbox(sinks, cid)
        fill = CLUSTER[cid]
        edge = CLUSTER_EDGE[cid]
        draw.rounded_rectangle([x0, y0, x1, y1], radius=8, fill=fill, outline=edge, width=2)
        cx, cy = centers[cid]
        draw.ellipse([cx - 6, cy - 6, cx + 6, cy + 6], fill=edge, outline=WHITE)
        if show_labels:
            draw.text((x0 + 4, y0 + 2), f"C{cid}", fill=edge, font=F_TINY)


def draw_tree_logical(draw, nodes, edges, root):
    for a, b in edges:
        draw.line([a, b], fill=CLK, width=2)
    for i, p in enumerate(nodes):
        r = 7 if p == root else 5
        draw.ellipse([p[0] - r, p[1] - r, p[0] + r, p[1] + r], fill=CLK, outline=CLK_EDGE)
    draw.text((root[0] + 10, root[1] - 12), "clk root", fill=CLK_EDGE, font=F_LABEL)


def draw_routes(draw, segs, width=2, color=CLK_ROUTE):
    for a, b in segs:
        draw.line([a, b], fill=color, width=width)


def draw_buffers(draw, nodes, root, size=5):
    for p in nodes:
        if p == root:
            draw.rectangle([p[0] - 7, p[1] - 6, p[0] + 7, p[1] + 6], fill=CLK, outline=CLK_EDGE, width=2)
        else:
            draw.rectangle([p[0] - size, p[1] - size + 1, p[0] + size, p[1] + size - 1], fill=BUF, outline=BUF_EDGE)


def draw_conditioning(draw, segs, nodes):
    """Shield ticks + taper markers along trunk routes."""
    # shield hash marks on first few trunk segments
    for i, (a, b) in enumerate(segs[:8]):
        ax, ay = a
        bx, by = b
        if ax == bx:  # vertical
            x = ax
            y0, y1 = sorted([ay, by])
            for y in range(y0 + 6, y1, 12):
                draw.line([x - 4, y, x + 4, y], fill=COND, width=1)
        else:
            y = ay
            x0, x1 = sorted([ax, bx])
            for x in range(x0 + 6, x1, 12):
                draw.line([x, y - 4, x, y + 4], fill=COND, width=1)
    # taper note near root
    root = nodes[0]
    draw.text((root[0] + 12, root[1] + 14), "taper + shield", fill=COND, font=F_TINY)


def draw_skew_metrics(draw, die, bad=True):
    x0, y0, x1, y1 = die
    bx0, by0 = x0 + 10, y1 - 78
    if bad:
        box = [bx0, by0, bx0 + 250, y1 - 14]
        draw.rounded_rectangle(box, radius=6, fill=WHITE, outline=DELAY_BAD, width=2)
        draw.text((bx0 + 12, by0 + 8), "skew = 48 ps   ID = 312 ps", fill=DELAY_BAD, font=F_TINY)
        draw.text((bx0 + 12, by0 + 28), "WNS < 0  (capture fails)", fill=DELAY_BAD, font=F_TINY)
    else:
        box = [bx0, by0, bx0 + 280, y1 - 14]
        draw.rounded_rectangle(box, radius=6, fill=WHITE, outline=DELAY_OK, width=2)
        draw.text((bx0 + 12, by0 + 8), "skew = 12 ps   ID = 268 ps", fill=DELAY_OK, font=F_TINY)
        draw.text((bx0 + 12, by0 + 28), "WNS ≥ 0  (ID/skew/timing OK)", fill=DELAY_OK, font=F_TINY)


def draw_delay_labels(draw, centers, root, unbalanced=True):
    """Show unequal vs equal insertion delays to clusters."""
    if unbalanced:
        delays = {0: "ID 290", 1: "ID 340", 2: "ID 260", 3: "ID 355"}
        for cid, (cx, cy) in centers.items():
            draw.text((cx + 8, cy - 14), delays[cid], fill=DELAY_BAD, font=F_TINY)
        draw.text((root[0] - 20, root[1] - 28), "unbalanced", fill=DELAY_BAD, font=F_LABEL)
    else:
        for cid, (cx, cy) in centers.items():
            draw.text((cx + 8, cy - 14), "ID 268", fill=DELAY_OK, font=F_TINY)
        draw.text((root[0] - 10, root[1] - 28), "balanced", fill=DELAY_OK, font=F_LABEL)


def status_box(draw, die, text, color=INK, border=None, y_off=52):
    x0, y0, x1, y1 = die
    bx0, by0, bx1, by1 = x0 + 10, y1 - y_off, x1 - 10, y1 - 14
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


def paint_base(draw, die, core, macros, cells):
    draw_die(draw, die)
    draw_util(draw, core)
    draw_pins(draw, die)
    draw_power(draw, core)
    draw_macros(draw, macros)
    draw_cells(draw, cells)


def render_frames():
    FRAMES.mkdir(parents=True, exist_ok=True)
    die = die_box()
    core = core_box(die)
    macros = abs_macros(core, CLEAN_MACROS)
    cells = make_cells(core, macros)
    sinks = make_sinks(core, macros)
    centers = cluster_centers(sinks)
    root = clock_root(core)
    nodes, edges, l1 = balance_tree(root, centers)
    trunk_segs = route_tree(edges)
    leaf_segs = leaf_routes(centers, sinks)

    frames = []

    # f00 start
    im, draw = make_base()
    draw_sidebar(draw, -1, "Start — placement ready", "CTS begins on LEGAL place. Flop sinks waiting for clock.")
    paint_base(draw, die, core, macros, cells)
    draw_sinks(draw, sinks, colored=False)
    status_box(draw, die, "Input: place_done.enc — clock sinks shown (dark)")
    p = FRAMES / "f00.png"
    im.save(p)
    frames.append(p)

    # f01 cluster
    im, draw = make_base()
    draw_sidebar(draw, 0, "1 / 5 Sink clustering", "Group nearby flops. Each cluster gets a local clock buffer target.")
    paint_base(draw, die, core, macros, cells)
    draw_clusters(draw, sinks, centers)
    draw_sinks(draw, sinks, colored=True)
    legend(draw, die, [("sinks", SINK), ("cluster", CLUSTER_EDGE[0]), ("macros", MACRO_FILL)])
    status_box(draw, die, "Layer: sink clusters C0–C3 (centroids marked)", color=ACTIVE, border=ACTIVE)
    p = FRAMES / "f01.png"
    im.save(p)
    frames.append(p)

    # f02 balance
    im, draw = make_base()
    draw_sidebar(draw, 1, "2 / 5 Tree balancing", "Build equal-depth tree. Match insertion delay across clusters.")
    paint_base(draw, die, core, macros, cells)
    draw_clusters(draw, sinks, centers, show_labels=False)
    draw_sinks(draw, sinks, colored=True)
    draw_tree_logical(draw, nodes, edges, root)
    draw_buffers(draw, nodes, root)
    draw_delay_labels(draw, centers, root, unbalanced=False)
    legend(draw, die, [("clk tree", CLK), ("clk buf", BUF)])
    status_box(draw, die, "Layers: clusters + BALANCED logical tree", color=CLK, border=CLK)
    p = FRAMES / "f02.png"
    im.save(p)
    frames.append(p)

    # f03 clock route
    im, draw = make_base()
    draw_sidebar(draw, 2, "3 / 5 Clock routing", "Route Manhattan clock nets root→hubs→sinks. Tree stays.")
    paint_base(draw, die, core, macros, cells)
    draw_clusters(draw, sinks, centers, show_labels=False)
    draw_sinks(draw, sinks, colored=True)
    draw_routes(draw, trunk_segs, width=3, color=CLK_ROUTE)
    draw_routes(draw, leaf_segs, width=1, color=(40, 160, 170))
    draw_buffers(draw, nodes, root)
    draw.text((root[0] + 10, root[1] - 12), "clk root", fill=CLK_EDGE, font=F_LABEL)
    legend(draw, die, [("trunk", CLK_ROUTE), ("leaf", (40, 160, 170)), ("buf", BUF)])
    status_box(draw, die, "Layers: clusters + tree + CLOCK ROUTE", color=CLK_ROUTE, border=CLK_ROUTE)
    p = FRAMES / "f03.png"
    im.save(p)
    frames.append(p)

    # f04 post-route conditioning
    im, draw = make_base()
    draw_sidebar(
        draw,
        3,
        "4 / 5 Post-route conditioning",
        "Taper, shield, NDR, SI cleanup on clock nets. Structure stays.",
    )
    paint_base(draw, die, core, macros, cells)
    draw_clusters(draw, sinks, centers, show_labels=False)
    draw_sinks(draw, sinks, colored=True)
    draw_routes(draw, trunk_segs, width=4, color=CLK_ROUTE)
    draw_routes(draw, leaf_segs, width=1, color=(40, 160, 170))
    draw_conditioning(draw, trunk_segs, nodes)
    draw_buffers(draw, nodes, root, size=6)
    legend(draw, die, [("shield/NDR", COND), ("clk route", CLK_ROUTE)])
    status_box(draw, die, "Layers: + post-route conditioning (taper/shield/NDR)", color=COND, border=COND)
    p = FRAMES / "f04.png"
    im.save(p)
    frames.append(p)

    # f05 opt — before (skew/ID bad) — show intentional imbalance on leaf lengths visually
    im, draw = make_base()
    draw_sidebar(
        draw,
        4,
        "5 / 5 Opt: ID / skew / timing",
        "Measure insertion delay & skew. Fix with sizing / useful skew.",
    )
    paint_base(draw, die, core, macros, cells)
    draw_clusters(draw, sinks, centers, show_labels=False)
    draw_sinks(draw, sinks, colored=True)
    draw_routes(draw, trunk_segs, width=4, color=CLK_ROUTE)
    draw_routes(draw, leaf_segs, width=1, color=(40, 160, 170))
    draw_conditioning(draw, trunk_segs, nodes)
    draw_buffers(draw, nodes, root, size=6)
    # bad delay callouts (pre-opt)
    bad_delays = {0: "ID 290", 1: "ID 340", 2: "ID 255", 3: "ID 360"}
    for cid, (cx, cy) in centers.items():
        draw.text((cx + 8, cy - 16), bad_delays[cid], fill=DELAY_BAD, font=F_TINY)
    # skew arrow between C1 and C2
    a, b = centers[1], centers[2]
    draw.line([a, b], fill=DELAY_BAD, width=2)
    mid = ((a[0] + b[0]) // 2, (a[1] + b[1]) // 2)
    draw.text((mid[0] - 30, mid[1] - 10), "Δskew", fill=DELAY_BAD, font=F_LABEL)
    draw_skew_metrics(draw, die, bad=True)
    p = FRAMES / "f05.png"
    im.save(p)
    frames.append(p)

    # f05b opt done
    im, draw = make_base()
    draw_sidebar(
        draw,
        4,
        "5 / 5 Opt: ID / skew / timing",
        "Resize / rebuffer / useful skew. ID matched, skew down, WNS OK.",
    )
    paint_base(draw, die, core, macros, cells)
    draw_clusters(draw, sinks, centers, show_labels=False)
    draw_sinks(draw, sinks, colored=True)
    draw_routes(draw, trunk_segs, width=4, color=CLK_ROUTE)
    draw_routes(draw, leaf_segs, width=1, color=(40, 160, 170))
    draw_conditioning(draw, trunk_segs, nodes)
    draw_buffers(draw, nodes, root, size=6)
    for cid, (cx, cy) in centers.items():
        draw.text((cx + 8, cy - 16), "ID 268", fill=DELAY_OK, font=F_TINY)
    # show a VT/size bump on one hub
    hub = l1[1]
    draw.rectangle([hub[0] - 9, hub[1] - 8, hub[0] + 9, hub[1] + 8], outline=DELAY_OK, width=2)
    draw.text((hub[0] + 12, hub[1] - 6), "size↑", fill=DELAY_OK, font=F_TINY)
    draw_skew_metrics(draw, die, bad=False)
    p = FRAMES / "f05b.png"
    im.save(p)
    frames.append(p)

    # f06 handoff
    im, draw = make_base()
    draw.rounded_rectangle([16, 64, LEFT_W - 16, H - 52], radius=10, fill=PANEL, outline=(210, 214, 222), width=1)
    draw.text((32, 80), "Done — CTS complete", fill=INK, font=F_H1)
    y = 112
    for line in wrap_text(
        draw,
        "Clock balanced. Skew/ID in budget. Hand off to signal routing.",
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

    paint_base(draw, die, core, macros, cells)
    draw_clusters(draw, sinks, centers, show_labels=False)
    draw_sinks(draw, sinks, colored=True)
    draw_routes(draw, trunk_segs, width=4, color=CLK_ROUTE)
    draw_routes(draw, leaf_segs, width=1, color=(40, 160, 170))
    draw_conditioning(draw, trunk_segs, nodes)
    draw_buffers(draw, nodes, root, size=6)
    for cid, (cx, cy) in centers.items():
        draw.text((cx + 8, cy - 16), "ID 268", fill=DELAY_OK, font=F_TINY)
    legend(draw, die, [("clock", CLK_ROUTE), ("buf", BUF), ("sinks", CLUSTER_EDGE[0])])
    x0, y0, x1, y1 = die
    draw.rounded_rectangle([x0 + 10, y1 - 70, x0 + 250, y1 - 14], radius=6, fill=WHITE, outline=(180, 185, 195), width=2)
    draw.text((x0 + 20, y1 - 58), "defOut cts.def", fill=INK, font=F_TINY)
    draw.text((x0 + 20, y1 - 40), "saveDesign cts_done.enc", fill=INK, font=F_TINY)
    draw.rounded_rectangle([x1 - 230, y1 - 70, x1 - 10, y1 - 14], radius=6, fill=WHITE, outline=DELAY_OK, width=2)
    draw.text((x1 - 218, y1 - 58), "CTS SAVED", fill=DELAY_OK, font=F_LABEL)
    draw.text((x1 - 218, y1 - 38), "next → Route", fill=MUTED, font=F_TINY)
    p = FRAMES / "f06.png"
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
