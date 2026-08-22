#!/usr/bin/env python3
"""
LinkedIn demo GIF — NUMA local vs remote for Fusion Compiler–class jobs.

Story (one composition, continuous build-up):
  1. Dual-socket machine appears
  2. Unbound FC: CPUs on node0, pages on node1 → traffic burns UPI
  3. Meters tank (bandwidth ↓ latency ↑ wall-time ↑)
  4. The policy: numactl --cpunodebind=0 --membind=0
  5. Bind: CPU + DRAM same node → local path, meters recover
  6. Punchline card

Output: numa_fc_demo.gif (1280×720)
"""

from __future__ import annotations

import math
import os
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUT_DIR = Path(__file__).resolve().parent
FRAMES_DIR = OUT_DIR / "frames"
GIF = OUT_DIR / "numa_fc_demo.gif"
ARTIFACT = Path("/opt/cursor/artifacts/numa_fc_demo.gif")

W, H = 1280, 720

# Palette — cool steel / amber accent (not purple, not cream-serif)
BG0 = (14, 22, 34)
BG1 = (22, 34, 52)
PANEL = (28, 42, 62)
INK = (232, 238, 246)
MUTED = (140, 156, 176)
DIM = (90, 104, 124)
ACCENT = (232, 148, 48)       # amber — policy / CTA
GOOD = (56, 196, 120)         # local / healthy
BAD = (232, 72, 72)           # remote / UPI burn
NODE0 = (64, 140, 220)        # socket 0
NODE1 = (100, 128, 148)       # socket 1 — steel, not purple
DRAM = (48, 168, 180)
WHITE = (255, 255, 255)
TERM = (18, 28, 40)


def font(size: int, mono: bool = False, bold: bool = False) -> ImageFont.ImageFont:
    if mono:
        cands = [
            "/usr/share/fonts/truetype/jetbrains-mono/JetBrainsMono-Bold.ttf"
            if bold
            else "/usr/share/fonts/truetype/jetbrains-mono/JetBrainsMono-Regular.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf"
            if bold
            else "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
        ]
    else:
        cands = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
            if bold
            else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        ]
    for p in cands:
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


F_BRAND = font(28, bold=True)
F_H = font(22, bold=True)
F_B = font(16)
F_S = font(14)
F_T = font(12)
F_MONO = font(15, mono=True, bold=True)
F_MONO_S = font(13, mono=True)
F_BIG = font(36, bold=True)
F_METER = font(13, bold=True)


def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def lerp_rgb(c0, c1, t):
    return tuple(int(lerp(c0[i], c1[i], t)) for i in range(3))


def clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def new_frame() -> Image.Image:
    img = Image.new("RGB", (W, H), BG0)
    d = ImageDraw.Draw(img)
    # subtle vertical gradient feel via bands
    for y in range(H):
        t = y / H
        c = lerp_rgb(BG0, BG1, t * 0.55)
        d.line([(0, y), (W, y)], fill=c)
    # soft vignette-ish side fades
    return img


def rounded(d: ImageDraw.ImageDraw, box, fill, radius=14, outline=None, width=1):
    d.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def draw_header(d: ImageDraw.ImageDraw, phase: str, subtitle: str):
    d.text((36, 22), "NUMA × Fusion Compiler", font=F_BRAND, fill=INK)
    d.text((36, 56), phase, font=F_H, fill=ACCENT)
    d.text((36, 86), subtitle, font=F_B, fill=MUTED)
    # right brand chip
    chip = "ops · memory locality"
    bbox = d.textbbox((0, 0), chip, font=F_T)
    tw = bbox[2] - bbox[0]
    rounded(d, (W - tw - 56, 28, W - 28, 54), PANEL, radius=8, outline=DIM)
    d.text((W - tw - 42, 33), chip, font=F_T, fill=MUTED)


def socket_geometry():
    # two sockets mid canvas
    left = (80, 150, 520, 520)
    right = (760, 150, 1200, 520)
    return left, right


def draw_socket(
    d: ImageDraw.ImageDraw,
    box,
    title: str,
    color,
    cores_lit: float,
    mem_lit: float,
    label_cores: str,
    label_dram: str,
):
    x0, y0, x1, y1 = box
    rounded(d, box, PANEL, radius=18, outline=color, width=2)
    d.text((x0 + 20, y0 + 14), title, font=F_H, fill=color)

    # cores grid 4x4
    gx0, gy0 = x0 + 28, y0 + 60
    cell, gap = 36, 10
    for r in range(4):
        for c in range(4):
            i = r * 4 + c
            on = (i / 15.0) < cores_lit
            cx0 = gx0 + c * (cell + gap)
            cy0 = gy0 + r * (cell + gap)
            fill = color if on else (40, 52, 72)
            rounded(d, (cx0, cy0, cx0 + cell, cy0 + cell), fill, radius=6)
    d.text((gx0, gy0 + 4 * (cell + gap) + 8), label_cores, font=F_S, fill=MUTED)

    # DRAM bar under cores
    mx0, my0 = x0 + 28, y1 - 90
    mw, mh = (x1 - x0) - 56, 42
    rounded(d, (mx0, my0, mx0 + mw, my0 + mh), (36, 48, 68), radius=8)
    fill_w = int(mw * clamp01(mem_lit))
    if fill_w > 4:
        rounded(d, (mx0, my0, mx0 + fill_w, my0 + mh), DRAM, radius=8)
    d.text((mx0, my0 - 22), label_dram, font=F_S, fill=MUTED)


def draw_upi(
    d: ImageDraw.ImageDraw,
    left,
    right,
    intensity: float,
    remote: bool,
    t_anim: float,
):
    """Interconnect between sockets. intensity 0..1; remote=True → red burn."""
    lx1 = left[2]
    rx0 = right[0]
    cy = (left[1] + left[3]) // 2
    color = BAD if remote and intensity > 0.05 else (GOOD if intensity > 0.05 else DIM)
    # trunk
    d.line([(lx1 + 8, cy), (rx0 - 8, cy)], fill=color, width=max(2, int(4 + 6 * intensity)))
    d.text(((lx1 + rx0) // 2 - 40, cy - 28), "UPI / IF", font=F_S, fill=color)

    # packets
    if intensity < 0.05:
        return
    n = int(4 + 10 * intensity)
    span = rx0 - lx1 - 40
    for i in range(n):
        phase = (t_anim * (1.2 + 0.15 * i) + i * 0.17) % 1.0
        # half go left→right, half reverse when remote thrash
        if remote and i % 2:
            phase = 1.0 - phase
        x = lx1 + 20 + phase * span
        y = cy + int(12 * math.sin(phase * math.pi * 2 + i))
        r = 5 + int(3 * intensity)
        d.ellipse((x - r, y - r, x + r, y + r), fill=color)


def draw_fc_badge(d: ImageDraw.ImageDraw, x: float, y: float, mode: str):
    label = "fc_shell"
    if mode == "unbound":
        sub = "unbound · first-touch scattered"
        col = BAD
    elif mode == "bound":
        sub = "cpunodebind=0 · membind=0"
        col = GOOD
    else:
        sub = "process"
        col = ACCENT
    rounded(d, (x, y, x + 280, y + 64), TERM, radius=10, outline=col, width=2)
    d.text((x + 14, y + 10), label, font=F_MONO, fill=INK)
    d.text((x + 14, y + 36), sub, font=F_T, fill=col)


def draw_meters(
    d: ImageDraw.ImageDraw,
    bw: float,
    lat: float,
    wall: float,
):
    """bw/lat/wall normalized 0..1 where high bw good, high lat/wall bad."""
    x0, y0 = 80, 560
    w = W - 160
    rounded(d, (x0, y0, x0 + w, y0 + 120), PANEL, radius=14)

    items = [
        ("DRAM bandwidth", bw, True),
        ("load latency", lat, False),
        ("wall time", wall, False),
    ]
    gap = 24
    bar_w = (w - 60 - gap * 2) // 3
    for i, (name, val, higher_better) in enumerate(items):
        bx = x0 + 24 + i * (bar_w + gap)
        by = y0 + 28
        d.text((bx, by - 18), name, font=F_METER, fill=MUTED)
        rounded(d, (bx, by + 14, bx + bar_w, by + 36), (40, 52, 72), radius=6)
        fill = int(bar_w * clamp01(val))
        if higher_better:
            col = lerp_rgb(BAD, GOOD, clamp01(val))
        else:
            col = lerp_rgb(GOOD, BAD, clamp01(val))
        if fill > 2:
            rounded(d, (bx, by + 14, bx + fill, by + 36), col, radius=6)
        # readout
        if higher_better:
            txt = f"{int(val * 100)}%"
        else:
            txt = f"{int(val * 100)}%"
        d.text((bx, by + 46), txt, font=F_S, fill=INK)


def draw_terminal(d: ImageDraw.ImageDraw, typed: str, y: int = 200):
    box = (120, y, 1160, y + 110)
    rounded(d, box, TERM, radius=12, outline=ACCENT, width=2)
    # wrap long command visually on two lines if needed
    line1 = typed
    line2 = ""
    soft = 58
    if len(typed) > soft:
        # break after membind=0
        br = typed.find(" fc_shell")
        if br > 0:
            line1 = typed[:br]
            line2 = typed[br + 1 :]
        else:
            line1, line2 = typed[:soft], typed[soft:]
    d.text((140, y + 18), "$  " + line1, font=F_MONO, fill=GOOD)
    if line2:
        d.text((140, y + 46), "   " + line2, font=F_MONO, fill=GOOD)
        d.text(
            (140, y + 78),
            "# pin cores + DRAM to the SAME NUMA node",
            font=F_MONO_S,
            fill=DIM,
        )
    else:
        d.text(
            (140, y + 58),
            "# pin cores + DRAM to the SAME NUMA node",
            font=F_MONO_S,
            fill=DIM,
        )


def draw_end_card(d: ImageDraw.ImageDraw):
    rounded(d, (180, 200, 1100, 480), PANEL, radius=20, outline=ACCENT, width=2)
    d.text((220, 240), "Same silicon.", font=F_BIG, fill=INK)
    d.text((220, 300), "Better memory policy.", font=F_BIG, fill=ACCENT)
    d.text(
        (220, 380),
        "numactl --cpunodebind=0 --membind=0   →   local DRAM, quiet interconnect",
        font=F_MONO_S,
        fill=MUTED,
    )
    d.text(
        (220, 420),
        "Only when the working set fits one node’s free RAM.",
        font=F_B,
        fill=DIM,
    )


def render_scene(kind: str, t: float) -> Image.Image:
    """
    kind: intro | unbound | problem | command | bound | end
    t: 0..1 progress within scene (for motion)
    """
    img = new_frame()
    d = ImageDraw.Draw(img)
    left, right = socket_geometry()

    if kind == "intro":
        draw_header(
            d,
            "Dual-socket server",
            "Each socket owns its own DRAM. Crossing the link is not free.",
        )
        appear = clamp01(t * 1.4)
        draw_socket(
            d,
            left,
            "NUMA node 0",
            NODE0,
            cores_lit=appear,
            mem_lit=appear * 0.35,
            label_cores="cores",
            label_dram="local DRAM",
        )
        draw_socket(
            d,
            right,
            "NUMA node 1",
            NODE1,
            cores_lit=appear,
            mem_lit=appear * 0.35,
            label_cores="cores",
            label_dram="local DRAM",
        )
        draw_upi(d, left, right, intensity=0.15 * appear, remote=False, t_anim=t)
        draw_meters(d, bw=0.55, lat=0.35, wall=0.4)

    elif kind == "unbound":
        draw_header(
            d,
            "Unbound Fusion Compiler",
            "Threads on node 0 · heap first-touched on node 1 → remote fills",
        )
        draw_socket(
            d,
            left,
            "NUMA node 0",
            NODE0,
            cores_lit=0.95,
            mem_lit=0.15,
            label_cores="fc threads HOT",
            label_dram="almost empty",
        )
        draw_socket(
            d,
            right,
            "NUMA node 1",
            NODE1,
            cores_lit=0.2,
            mem_lit=0.9,
            label_cores="mostly idle",
            label_dram="fc working set",
        )
        draw_upi(d, left, right, intensity=0.55 + 0.45 * abs(math.sin(t * math.pi)), remote=True, t_anim=t)
        draw_fc_badge(d, 500, 130, "unbound")
        # meters degrade over scene
        bw = lerp(0.55, 0.28, clamp01(t))
        lat = lerp(0.35, 0.88, clamp01(t))
        wall = lerp(0.4, 0.92, clamp01(t))
        draw_meters(d, bw, lat, wall)

    elif kind == "problem":
        draw_header(
            d,
            "The trap",
            "top shows 100% CPU. The interconnect is the real bottleneck.",
        )
        draw_socket(
            d,
            left,
            "NUMA node 0",
            NODE0,
            cores_lit=1.0,
            mem_lit=0.12,
            label_cores="busy cores",
            label_dram="cold",
        )
        draw_socket(
            d,
            right,
            "NUMA node 1",
            NODE1,
            cores_lit=0.15,
            mem_lit=0.95,
            label_cores="",
            label_dram="hot pages (remote)",
        )
        draw_upi(d, left, right, intensity=1.0, remote=True, t_anim=t)
        # callout
        rounded(d, (340, 250, 940, 360), TERM, radius=14, outline=BAD, width=2)
        d.text((370, 270), "CPU busy ≠ memory local", font=F_H, fill=BAD)
        d.text(
            (370, 310),
            "Every remote load pays UPI latency + steals bandwidth from everyone.",
            font=F_B,
            fill=MUTED,
        )
        draw_meters(d, 0.25, 0.9, 0.95)

    elif kind == "command":
        draw_header(
            d,
            "The policy",
            "Pin the process to one node’s CPUs and allocate only that node’s DRAM.",
        )
        # sockets first (background), terminal on top
        draw_socket(
            d,
            left,
            "NUMA node 0",
            lerp_rgb(NODE0, DIM, 0.35),
            cores_lit=0.25,
            mem_lit=0.15,
            label_cores="",
            label_dram="",
        )
        draw_socket(
            d,
            right,
            "NUMA node 1",
            lerp_rgb(NODE1, DIM, 0.55),
            cores_lit=0.05,
            mem_lit=0.05,
            label_cores="",
            label_dram="",
        )
        draw_upi(d, left, right, intensity=0.05, remote=False, t_anim=t)
        cmd = "numactl --cpunodebind=0 --membind=0 fc_shell -f run.tcl"
        # finish typing by ~55% of scene, then hold full command
        type_t = clamp01(t / 0.55)
        n = int(len(cmd) * type_t)
        done = n >= len(cmd)
        typed = cmd[:n] + ("▌" if (not done and int(t * 12) % 2 == 0) else "")
        draw_terminal(d, typed, y=300)
        draw_meters(d, 0.3, 0.85, 0.9)

    elif kind == "bound":
        draw_header(
            d,
            "Bound · local",
            "Same job. CPU + pages on node 0. Interconnect goes quiet.",
        )
        draw_socket(
            d,
            left,
            "NUMA node 0",
            NODE0,
            cores_lit=0.95,
            mem_lit=0.88,
            label_cores="fc threads",
            label_dram="working set (local)",
        )
        draw_socket(
            d,
            right,
            "NUMA node 1",
            lerp_rgb(NODE1, DIM, 0.35),
            cores_lit=0.0,
            mem_lit=0.05,
            label_cores="left alone",
            label_dram="free for other jobs",
        )
        # quiet green local pulse inside node0 — UPI nearly off
        draw_upi(d, left, right, intensity=0.08, remote=False, t_anim=t)
        draw_fc_badge(d, 140, 130, "bound")
        bw = lerp(0.3, 0.92, clamp01(t))
        lat = lerp(0.85, 0.22, clamp01(t))
        wall = lerp(0.9, 0.35, clamp01(t))
        draw_meters(d, bw, lat, wall)
        # green local arrows hint inside left socket
        if t > 0.2:
            x0, y0, x1, y1 = left
            for i in range(5):
                phase = (t * 1.5 + i * 0.2) % 1.0
                px = x0 + 60 + phase * (x1 - x0 - 120)
                py = y0 + 280 + int(8 * math.sin(phase * 6 + i))
                d.ellipse((px - 4, py - 4, px + 4, py + 4), fill=GOOD)

    elif kind == "end":
        draw_header(d, "Takeaway", "Policy is free performance — when the design fits the node.")
        draw_end_card(d)
        draw_meters(d, 0.9, 0.22, 0.32)

    return img


def build_timeline():
    """Return list of (kind, duration_frames, hold_extra)."""
    # ~12–14s GIF at 80ms/frame → ~150-180 frames
    return [
        ("intro", 18),
        ("unbound", 36),
        ("problem", 28),
        ("command", 40),
        ("bound", 36),
        ("end", 32),
    ]


def main() -> None:
    FRAMES_DIR.mkdir(parents=True, exist_ok=True)
    ARTIFACT.parent.mkdir(parents=True, exist_ok=True)

    timeline = build_timeline()
    frames: list[Image.Image] = []
    idx = 0
    for kind, n in timeline:
        for i in range(n):
            t = i / max(1, n - 1)
            img = render_scene(kind, t)
            path = FRAMES_DIR / f"f{idx:03d}.png"
            img.save(path)
            frames.append(img)
            idx += 1

    # durations: slightly longer holds on problem/end
    durations = []
    fi = 0
    for kind, n in timeline:
        base = 90 if kind in ("problem", "end") else 70
        for i in range(n):
            # linger last frames of each scene
            dur = base + (40 if i >= n - 3 else 0)
            durations.append(dur)
            fi += 1

    frames[0].save(
        GIF,
        save_all=True,
        append_images=frames[1:],
        duration=durations,
        loop=0,
        optimize=False,
    )
    frames[0].save(
        ARTIFACT,
        save_all=True,
        append_images=frames[1:],
        duration=durations,
        loop=0,
        optimize=False,
    )
    # also save a still for LinkedIn cover / thumbnail
    still = render_scene("bound", 1.0)
    still_path = OUT_DIR / "numa_fc_demo_still.png"
    still.save(still_path)
    still.save(Path("/opt/cursor/artifacts/numa_fc_demo_still.png"))

    print(f"Wrote {len(frames)} frames → {GIF}")
    print(f"Artifact → {ARTIFACT}")
    print(f"Still → {still_path}")


if __name__ == "__main__":
    main()
