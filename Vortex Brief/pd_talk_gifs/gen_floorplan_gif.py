#!/usr/bin/env python3
"""Generate continuous-build-up floorplan teaching GIF (1280x720)."""

from __future__ import annotations

import os
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUT_DIR = Path(__file__).resolve().parent
FRAMES = OUT_DIR / "floorplan_frames"
GIF = OUT_DIR / "floorplan_flow.gif"
ARTIFACT = Path("/opt/cursor/artifacts/floorplan_flow.gif")

W, H = 1280, 720
LEFT_W = 360
PAD = 28

# Colors
BG = (236, 238, 242)
HEADER = (18, 42, 74)
PANEL = (248, 249, 252)
INK = (28, 34, 48)
MUTED = (120, 128, 140)
DONE = (34, 140, 78)
ACTIVE = (28, 96, 196)
DIE_EDGE = (20, 24, 32)
CORE = (230, 120, 40)
UTIL = (170, 210, 235)
PIN_TB = (40, 70, 140)
PIN_LR = (210, 120, 50)
PWR_H = (200, 55, 55)
PWR_V = (55, 95, 190)
MACRO_FILL = (190, 210, 160)
MACRO_FILL_ALT = (225, 205, 150)
MACRO_EDGE = (70, 95, 55)
HALO = (210, 40, 40)
OK = (40, 140, 70)
WHITE = (255, 255, 255)


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    ]
    for p in candidates:
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


F_TITLE = font(22, True)
F_H1 = font(20, True)
F_BODY = font(14)
F_SMALL = font(12)
F_TINY = font(11)
F_MACRO = font(12, True)

STEPS = [
    "Util definition",
    "Die dimensions",
    "Pin / IO planning",
    "Power planning",
    "Macro placement",
    "Verify DRC / checks",
    "FP exit: DEF + saveDesign",
]


# Die geometry (right panel canvas coords)
def die_box():
    x0 = LEFT_W + 70
    y0 = 90
    size = 520
    return x0, y0, x0 + size, y0 + size


def core_box(die):
    x0, y0, x1, y1 = die
    m = 36
    return x0 + m, y0 + m, x1 - m, y1 - m


# Macro rects relative to core: (nx0, ny0, nx1, ny1) in 0..1 of core
# CLEAN layout — explicit channels (≥~8% core) so blocks never look fused
CLEAN_MACROS = [
    ("SRAM0", 0.04, 0.05, 0.26, 0.28, MACRO_FILL),
    ("SRAM1", 0.38, 0.05, 0.60, 0.26, MACRO_FILL),
    ("DDR PHY", 0.78, 0.10, 0.95, 0.68, MACRO_FILL),
    ("PLL/ANA", 0.04, 0.40, 0.24, 0.60, MACRO_FILL_ALT),
    ("MACRO", 0.34, 0.56, 0.60, 0.82, MACRO_FILL_ALT),
]

# BAD layout for DRC frame — SRAM0/SRAM1 abut (halo/spacing violation only)
BAD_MACROS = [
    ("SRAM0", 0.04, 0.05, 0.32, 0.28, MACRO_FILL),
    ("SRAM1", 0.325, 0.05, 0.55, 0.26, MACRO_FILL),  # ~1–2 px → halo!
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


def draw_header(draw: ImageDraw.ImageDraw):
    draw.rectangle([0, 0, W, 48], fill=HEADER)
    draw.text((22, 12), "Physical Design · FLOORPLAN · continuous build-up", fill=WHITE, font=F_TITLE)


def draw_footer(draw: ImageDraw.ImageDraw):
    draw.rectangle([0, H - 36, W, H], fill=(220, 223, 230))
    draw.text(
        (22, H - 26),
        "Same die accumulates features → final saveDesign shows the FULL floorplan",
        fill=INK,
        font=F_SMALL,
    )


def draw_sidebar(draw: ImageDraw.ImageDraw, step_idx: int, title: str, blurb: str):
    """step_idx: -1 start, 0..6 for steps 1..7"""
    draw.rounded_rectangle([16, 64, LEFT_W - 16, H - 52], radius=10, fill=PANEL, outline=(210, 214, 222), width=1)
    draw.text((32, 80), title, fill=INK, font=F_H1)

    # wrap blurb
    y = 112
    words = blurb.split()
    line = ""
    for w in words:
        trial = (line + " " + w).strip()
        if draw.textlength(trial, font=F_BODY) > LEFT_W - 64:
            draw.text((32, y), line, fill=MUTED, font=F_BODY)
            y += 20
            line = w
        else:
            line = trial
    if line:
        draw.text((32, y), line, fill=MUTED, font=F_BODY)
        y += 28

    draw.text((32, y + 8), "BUILD-UP (nothing resets)", fill=INK, font=F_SMALL)
    y += 34
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
        y += 28


def draw_util(draw, core, fraction=0.62):
    cx0, cy0, cx1, cy1 = core
    # util wash as a solid region inside core (left portion early; full later looks busy — keep ~full after macros)
    ux1 = int(cx0 + (cx1 - cx0) * fraction)
    draw.rectangle([cx0 + 2, cy0 + 2, ux1, cy1 - 2], fill=UTIL)


def draw_die(draw, die, show_core=False, show_dims=False):
    x0, y0, x1, y1 = die
    draw.rectangle([x0, y0, x1, y1], outline=DIE_EDGE, width=3, fill=WHITE)
    if show_core:
        c = core_box(die)
        draw.rectangle(c, outline=CORE, width=2)
    if show_dims:
        mx = (x0 + x1) // 2
        draw.line([x0, y1 + 18, x1, y1 + 18], fill=INK, width=1)
        draw.line([x0, y1 + 12, x0, y1 + 24], fill=INK, width=1)
        draw.line([x1, y1 + 12, x1, y1 + 24], fill=INK, width=1)
        tw = draw.textlength("WIDTH × HEIGHT", font=F_SMALL)
        draw.text((mx - tw / 2, y1 + 24), "WIDTH × HEIGHT", fill=INK, font=F_SMALL)


def draw_pins(draw, die):
    x0, y0, x1, y1 = die
    s = 14
    gap = 28
    # top / bottom
    x = x0 + 40
    while x + s < x1 - 30:
        draw.rectangle([x, y0 + 8, x + s, y0 + 8 + s], fill=PIN_TB, outline=DIE_EDGE)
        draw.rectangle([x, y1 - 8 - s, x + s, y1 - 8], fill=PIN_TB, outline=DIE_EDGE)
        x += gap
    # left / right
    y = y0 + 40
    while y + s < y1 - 30:
        draw.rectangle([x0 + 8, y, x0 + 8 + s, y + s], fill=PIN_LR, outline=DIE_EDGE)
        draw.rectangle([x1 - 8 - s, y, x1 - 8, y + s], fill=PIN_LR, outline=DIE_EDGE)
        y += gap


def draw_power(draw, core):
    cx0, cy0, cx1, cy1 = core
    # ring
    draw.rectangle([cx0, cy0, cx1, cy1], outline=CORE, width=3)
    # straps
    for i in range(1, 6):
        y = cy0 + i * (cy1 - cy0) // 6
        draw.line([cx0 + 4, y, cx1 - 4, y], fill=PWR_H, width=2)
    for i in range(1, 6):
        x = cx0 + i * (cx1 - cx0) // 6
        draw.line([x, cy0 + 4, x, cy1 - 4], fill=PWR_V, width=2)


def draw_macros(draw, macros):
    for name, x0, y0, x1, y1, fill in macros:
        # light pad so power straps don't visually fuse neighboring macros
        draw.rectangle([x0 - 2, y0 - 2, x1 + 2, y1 + 2], fill=WHITE, outline=WHITE)
        draw.rectangle([x0, y0, x1, y1], fill=fill, outline=MACRO_EDGE, width=2)
        tw = draw.textlength(name, font=F_MACRO)
        th = 14
        tx = x0 + (x1 - x0 - tw) / 2
        ty = y0 + (y1 - y0 - th) / 2
        draw.text((tx, ty), name, fill=MACRO_EDGE, font=F_MACRO)


def status_box(draw, die, text, color=INK, border=None):
    x0, y0, x1, y1 = die
    bx0, by0 = x0 + 10, y1 - 52
    bx1, by1 = x1 - 10, y1 - 14
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


def assert_no_overlap(macros, label: str):
    for i, a in enumerate(macros):
        for b in macros[i + 1 :]:
            ax0, ay0, ax1, ay1 = a[1:5]
            bx0, by0, bx1, by1 = b[1:5]
            if ax0 < bx1 and ax1 > bx0 and ay0 < by1 and ay1 > by0:
                raise SystemExit(f"overlap in {label}: {a[0]} vs {b[0]}")


def make_base():
    im = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(im)
    draw_header(draw)
    draw_footer(draw)
    return im, draw


def render_frames():
    FRAMES.mkdir(parents=True, exist_ok=True)
    die = die_box()
    core = core_box(die)
    clean = abs_macros(core, CLEAN_MACROS)
    bad = abs_macros(core, BAD_MACROS)
    assert_no_overlap(clean, "CLEAN_MACROS")
    # bad may have near-touch; check only real area overlap (>1px)
    for i, a in enumerate(bad):
        for b in bad[i + 1 :]:
            ax0, ay0, ax1, ay1 = a[1:5]
            bx0, by0, bx1, by1 = b[1:5]
            # allow touching/near for halo demo between SRAM0/SRAM1 only
            if {a[0], b[0]} == {"SRAM0", "SRAM1"}:
                continue
            if ax0 < bx1 and ax1 > bx0 and ay0 < by1 and ay1 > by0:
                raise SystemExit(f"unexpected overlap in BAD: {a[0]} vs {b[0]}")

    frames_meta = []

    # f00 start
    im, draw = make_base()
    draw_sidebar(
        draw,
        -1,
        "Start — empty die",
        "Each next frame KEEPS prior layers — no reset.",
    )
    draw_die(draw, die)
    status_box(draw, die, "Empty die — build-up begins")
    path = FRAMES / "f00.png"
    im.save(path)
    frames_meta.append(path)

    # f01 util
    im, draw = make_base()
    draw_sidebar(draw, 0, "1 / 7 Util definition", "Add utilization budget. (core wash appears).")
    draw_die(draw, die, show_core=True)
    draw_util(draw, core, 0.58)
    status_box(draw, die, "Layer added: util | still no pins/power/macros")
    path = FRAMES / "f01.png"
    im.save(path)
    frames_meta.append(path)

    # f02 dimensions
    im, draw = make_base()
    draw_sidebar(draw, 1, "2 / 7 Die dimensions", "Add die/core dimensions. Util layer remains.")
    draw_die(draw, die, show_core=True, show_dims=True)
    draw_util(draw, core, 0.58)
    status_box(draw, die, "Layers: util + WIDTH×HEIGHT / core")
    path = FRAMES / "f02.png"
    im.save(path)
    frames_meta.append(path)

    # f03 pins
    im, draw = make_base()
    draw_sidebar(draw, 2, "3 / 7 Pin / IO planning", "Add pin/IO map. Util + dimensions remain.")
    draw_die(draw, die, show_core=True, show_dims=True)
    draw_util(draw, core, 0.58)
    draw_pins(draw, die)
    status_box(draw, die, "Layers: util + size + pins")
    path = FRAMES / "f03.png"
    im.save(path)
    frames_meta.append(path)

    # f04 power
    im, draw = make_base()
    draw_sidebar(draw, 3, "4 / 7 Power planning", "Add power rings/straps. All prior layers remain.")
    draw_die(draw, die, show_core=True, show_dims=True)
    draw_util(draw, core, 0.85)
    draw_pins(draw, die)
    draw_power(draw, core)
    status_box(draw, die, "Layers: util + size + pins + POWER", color=PWR_H, border=PWR_H)
    path = FRAMES / "f04.png"
    im.save(path)
    frames_meta.append(path)

    # f05 macros — CLEAN, no overlaps
    im, draw = make_base()
    draw_sidebar(
        draw,
        4,
        "5 / 7 Macro placement",
        "Place macros with clearance. Power/pins/util still visible.",
    )
    draw_die(draw, die, show_core=True, show_dims=True)
    draw_util(draw, core, 0.92)
    draw_pins(draw, die)
    draw_power(draw, core)
    draw_macros(draw, clean)
    legend(
        draw,
        die,
        [("util", UTIL), ("core/pins", CORE), ("power", PWR_H), ("macros", MACRO_FILL)],
    )
    status_box(draw, die, "Layers: util + size + pins + power + MACROS")
    path = FRAMES / "f05.png"
    im.save(path)
    frames_meta.append(path)

    # f06 DRC — intentional near-miss halo between SRAM0/SRAM1
    im, draw = make_base()
    draw_sidebar(
        draw,
        5,
        "6 / 7 Verify DRC / checks",
        "Verify on the FULL picture. Catch halo/spacing before exit.",
    )
    draw_die(draw, die, show_core=True, show_dims=True)
    draw_util(draw, core, 0.92)
    draw_pins(draw, die)
    draw_power(draw, core)
    draw_macros(draw, bad)
    # halo callout around SRAM0/SRAM1 abutment
    s0 = next(m for m in bad if m[0] == "SRAM0")
    s1 = next(m for m in bad if m[0] == "SRAM1")
    hx = (s0[3] + s1[1]) // 2
    hy = (min(s0[2], s1[2]) + max(s0[4], s1[4])) // 2
    r = 38
    draw.ellipse([hx - r, hy - r, hx + r, hy + r], outline=HALO, width=3)
    draw.text((hx + r + 6, hy - 8), "halo!", fill=HALO, font=F_MACRO)
    status_box(draw, die, "Same full FP — violation highlighted — fix in place", color=HALO, border=HALO)
    path = FRAMES / "f06.png"
    im.save(path)
    frames_meta.append(path)

    # f06b fixed — CLEAN again
    im, draw = make_base()
    draw_sidebar(
        draw,
        5,
        "6 / 7 Verify DRC / checks",
        "Fix on the same die. Everything else stays.",
    )
    draw_die(draw, die, show_core=True, show_dims=True)
    draw_util(draw, core, 0.92)
    draw_pins(draw, die)
    draw_power(draw, core)
    draw_macros(draw, clean)
    status_box(
        draw,
        die,
        "Clean ✓ — full FP intact (util+pins+PG+macros)",
        color=OK,
        border=OK,
    )
    path = FRAMES / "f06b.png"
    im.save(path)
    frames_meta.append(path)

    # f07 exit
    im, draw = make_base()
    draw_sidebar(
        draw,
        6,
        "7 / 7 FP exit: DEF + saveDesign",
        "Final frame shows the complete floorplan (FP).",
    )
    draw_die(draw, die, show_core=True, show_dims=True)
    draw_util(draw, core, 0.92)
    draw_pins(draw, die)
    draw_power(draw, core)
    draw_macros(draw, clean)
    legend(
        draw,
        die,
        [("util", UTIL), ("core/pins", CORE), ("power", PWR_H), ("macros", MACRO_FILL)],
    )
    # dual status boxes
    x0, y0, x1, y1 = die
    draw.rounded_rectangle([x0 + 10, y1 - 70, x0 + 250, y1 - 14], radius=6, fill=WHITE, outline=(180, 185, 195), width=2)
    draw.text((x0 + 20, y1 - 58), "defOut floorplan.def", fill=INK, font=F_TINY)
    draw.text((x0 + 20, y1 - 40), "saveDesign fp_done.enc", fill=INK, font=F_TINY)
    draw.rounded_rectangle([x1 - 230, y1 - 70, x1 - 10, y1 - 14], radius=6, fill=WHITE, outline=OK, width=2)
    draw.text((x1 - 218, y1 - 58), "FULL FP SAVED", fill=OK, font=F_MACRO)
    draw.text((x1 - 218, y1 - 38), "all layers → Placement", fill=MUTED, font=F_TINY)
    path = FRAMES / "f07.png"
    im.save(path)
    frames_meta.append(path)

    # GIF
    images = [Image.open(p).convert("P", palette=Image.ADAPTIVE, colors=128) for p in frames_meta]
    # durations: hold final longer
    durations = [1700] * (len(images) - 1) + [3000]
    images[0].save(
        GIF,
        save_all=True,
        append_images=images[1:],
        duration=durations,
        loop=0,
        optimize=True,
    )
    ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
    images[0].save(
        ARTIFACT,
        save_all=True,
        append_images=images[1:],
        duration=durations,
        loop=0,
        optimize=True,
    )
    print(f"Wrote {len(frames_meta)} frames → {GIF}")
    print(f"Artifact → {ARTIFACT}")


if __name__ == "__main__":
    render_frames()
