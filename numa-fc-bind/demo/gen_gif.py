#!/usr/bin/env python3
"""
Mechanism GIF for NUMA × Fusion Compiler binding.

Shows topology → remote fills → numactl policy → local binding.
No fake percentage meters. No invented speedup numbers.
"""

from __future__ import annotations

import math
import os
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).resolve().parent
FRAMES = OUT / "frames"
GIF = OUT / "numa_fc_bind.gif"
STILL = OUT / "numa_fc_bind_still.png"
ARTIFACT = Path("/opt/cursor/artifacts/numa_fc_bind.gif")

W, H = 1280, 720
BG0, BG1 = (16, 24, 36), (24, 36, 52)
PANEL = (30, 44, 64)
INK, MUTED, DIM = (236, 240, 246), (148, 162, 180), (96, 110, 128)
ACCENT = (232, 148, 48)
GOOD, BAD = (56, 196, 120), (232, 78, 78)
NODE0, DRAM = (64, 148, 220), (48, 168, 180)
NODE1 = (110, 130, 150)


def font(size: int, mono: bool = False, bold: bool = False):
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


F_BRAND, F_H, F_B = font(28, bold=True), font(22, bold=True), font(16)
F_S, F_T = font(14), font(12)
F_MONO = font(16, mono=True, bold=True)
F_MONO_S = font(13, mono=True)
F_BIG = font(34, bold=True)


def lerp(a, b, t):
    return a + (b - a) * t


def lerp_rgb(c0, c1, t):
    return tuple(int(lerp(c0[i], c1[i], t)) for i in range(3))


def clamp01(x):
    return max(0.0, min(1.0, x))


def new_frame():
    img = Image.new("RGB", (W, H), BG0)
    d = ImageDraw.Draw(img)
    for y in range(H):
        d.line([(0, y), (W, y)], fill=lerp_rgb(BG0, BG1, (y / H) * 0.55))
    return img


def rr(d, box, fill, radius=14, outline=None, width=2):
    d.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def header(d, phase, sub):
    d.text((36, 24), "numa-fc-bind", font=F_BRAND, fill=INK)
    d.text((36, 60), phase, font=F_H, fill=ACCENT)
    d.text((36, 92), sub, font=F_B, fill=MUTED)
    chip = "mechanism · not a benchmark"
    bb = d.textbbox((0, 0), chip, font=F_T)
    tw = bb[2] - bb[0]
    rr(d, (W - tw - 56, 28, W - 28, 54), PANEL, radius=8, outline=DIM)
    d.text((W - tw - 42, 33), chip, font=F_T, fill=MUTED)


def sockets():
    return (70, 160, 520, 560), (760, 160, 1210, 560)


def draw_socket(d, box, title, color, cores_on, mem_fill, core_lbl, mem_lbl, dimmed=False):
    col = lerp_rgb(color, DIM, 0.45) if dimmed else color
    rr(d, box, PANEL, outline=col, width=2)
    d.text((box[0] + 20, box[1] + 16), title, font=F_H, fill=col)
    gx0, gy0 = box[0] + 28, box[1] + 70
    cell, gap = 38, 10
    for r in range(4):
        for c in range(4):
            on = (r * 4 + c) / 15.0 < cores_on
            x = gx0 + c * (cell + gap)
            y = gy0 + r * (cell + gap)
            rr(d, (x, y, x + cell, y + cell), col if on else (42, 54, 72), radius=6)
    d.text((gx0, gy0 + 4 * (cell + gap) + 10), core_lbl, font=F_S, fill=MUTED)
    mx0, my0 = box[0] + 28, box[3] - 88
    mw = box[2] - box[0] - 56
    rr(d, (mx0, my0, mx0 + mw, my0 + 44), (38, 50, 70), radius=8)
    fw = int(mw * clamp01(mem_fill))
    if fw > 4:
        rr(d, (mx0, my0, mx0 + fw, my0 + 44), DRAM, radius=8)
    d.text((mx0, my0 - 22), mem_lbl, font=F_S, fill=MUTED)


def draw_upi(d, left, right, intensity, remote, t):
    lx1, rx0 = left[2], right[0]
    cy = (left[1] + left[3]) // 2
    if intensity < 0.05:
        col = DIM
    else:
        col = BAD if remote else GOOD
    d.line([(lx1 + 10, cy), (rx0 - 10, cy)], fill=col, width=max(2, int(3 + 7 * intensity)))
    d.text(((lx1 + rx0) // 2 - 36, cy - 28), "UPI / IF", font=F_S, fill=col)
    if intensity < 0.08:
        return
    n = int(3 + 9 * intensity)
    span = rx0 - lx1 - 40
    for i in range(n):
        phase = (t * (1.1 + 0.12 * i) + i * 0.19) % 1.0
        if remote and i % 2:
            phase = 1.0 - phase
        x = lx1 + 20 + phase * span
        y = cy + int(10 * math.sin(phase * math.pi * 2 + i))
        r = 4 + int(3 * intensity)
        d.ellipse((x - r, y - r, x + r, y + r), fill=col)


def badge(d, x, y, mode):
    if mode == "unbound":
        sub, col = "unbound · first-touch can scatter pages", BAD
    else:
        sub, col = "cpunodebind=0 · membind=0", GOOD
    rr(d, (x, y, x + 340, y + 66), (18, 28, 40), outline=col, width=2)
    d.text((x + 14, y + 12), "fc_shell", font=F_MONO, fill=INK)
    d.text((x + 14, y + 38), sub, font=F_T, fill=col)


def terminal(d, typed, y=290):
    rr(d, (100, y, 1180, y + 120), (18, 28, 40), outline=ACCENT, width=2)
    soft = 54
    if len(typed) > soft and " fc_shell" in typed:
        a, b = typed.split(" fc_shell", 1)
        line1, line2 = a, "fc_shell" + b
    else:
        line1, line2 = typed, ""
    d.text((120, y + 22), "$  " + line1, font=F_MONO, fill=GOOD)
    if line2:
        d.text((120, y + 52), "   " + line2, font=F_MONO, fill=GOOD)
    d.text((120, y + 88), "# same node for cores + DRAM  (only if RSS fits MemFree)", font=F_MONO_S, fill=DIM)


def end_card(d):
    rr(d, (160, 200, 1120, 500), PANEL, outline=ACCENT, width=2)
    d.text((200, 240), "Same silicon.", font=F_BIG, fill=INK)
    d.text((200, 300), "Aligned memory policy.", font=F_BIG, fill=ACCENT)
    d.text(
        (200, 380),
        "numactl --cpunodebind=0 --membind=0 …",
        font=F_MONO,
        fill=GOOD,
    )
    d.text(
        (200, 430),
        "Measure remote vs local on a real 2S/4S box — never invent numbers on 1-node hosts.",
        font=F_B,
        fill=MUTED,
    )


def scene(kind: str, t: float) -> Image.Image:
    img = new_frame()
    d = ImageDraw.Draw(img)
    left, right = sockets()

    if kind == "intro":
        header(d, "Dual-socket server", "Each socket owns DRAM. Crossing the link is not free.")
        a = clamp01(t * 1.3)
        draw_socket(d, left, "NUMA node 0", NODE0, a, a * 0.3, "cores", "local DRAM")
        draw_socket(d, right, "NUMA node 1", NODE1, a, a * 0.3, "cores", "local DRAM")
        draw_upi(d, left, right, 0.12 * a, False, t)

    elif kind == "unbound":
        header(
            d,
            "Unbound FC (failure mode)",
            "Threads hot on node 0 · working set on node 1 → remote fills",
        )
        draw_socket(d, left, "NUMA node 0", NODE0, 0.95, 0.12, "fc threads", "almost empty")
        draw_socket(d, right, "NUMA node 1", NODE1, 0.15, 0.9, "mostly idle", "fc working set")
        draw_upi(d, left, right, 0.55 + 0.4 * abs(math.sin(t * math.pi)), True, t)
        badge(d, 470, 130, "unbound")
        rr(d, (340, 580, 940, 680), (18, 28, 40), outline=BAD, width=2)
        d.text((370, 600), "CPU busy ≠ memory local", font=F_H, fill=BAD)
        d.text((370, 640), "Remote loads pay UPI latency and burn interconnect bandwidth.", font=F_B, fill=MUTED)

    elif kind == "policy":
        header(d, "The policy", "Pin CPUs and allocations to the same NUMA node.")
        draw_socket(d, left, "NUMA node 0", lerp_rgb(NODE0, DIM, 0.25), 0.25, 0.15, "", "", True)
        draw_socket(d, right, "NUMA node 1", lerp_rgb(NODE1, DIM, 0.45), 0.05, 0.05, "", "", True)
        draw_upi(d, left, right, 0.05, False, t)
        cmd = "numactl --cpunodebind=0 --membind=0 fc_shell -f run.tcl"
        tt = clamp01(t / 0.55)
        n = int(len(cmd) * tt)
        typed = cmd[:n] + ("▌" if (n < len(cmd) and int(t * 12) % 2 == 0) else "")
        terminal(d, typed)

    elif kind == "bound":
        header(d, "Bound · local", "Same job. CPU + pages on node 0. Interconnect quiet.")
        draw_socket(d, left, "NUMA node 0", NODE0, 0.95, 0.88, "fc threads", "working set (local)")
        draw_socket(
            d, right, "NUMA node 1", NODE1, 0.0, 0.05, "left alone", "free for other jobs", True
        )
        draw_upi(d, left, right, 0.06, False, t)
        badge(d, 120, 130, "bound")
        if t > 0.15:
            for i in range(5):
                phase = (t * 1.4 + i * 0.2) % 1.0
                px = left[0] + 70 + phase * (left[2] - left[0] - 140)
                py = left[1] + 300 + int(8 * math.sin(phase * 6 + i))
                d.ellipse((px - 4, py - 4, px + 4, py + 4), fill=GOOD)

    elif kind == "end":
        header(d, "Takeaway", "Policy is placement — measure on real multi-socket silicon.")
        end_card(d)

    return img


def main():
    FRAMES.mkdir(parents=True, exist_ok=True)
    ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
    timeline = [
        ("intro", 20),
        ("unbound", 36),
        ("policy", 44),
        ("bound", 36),
        ("end", 28),
    ]
    frames = []
    idx = 0
    durations = []
    for kind, n in timeline:
        for i in range(n):
            t = i / max(1, n - 1)
            img = scene(kind, t)
            img.save(FRAMES / f"f{idx:03d}.png")
            frames.append(img)
            base = 95 if kind in ("unbound", "end") else 70
            durations.append(base + (35 if i >= n - 3 else 0))
            idx += 1

    frames[0].save(GIF, save_all=True, append_images=frames[1:], duration=durations, loop=0)
    frames[0].save(ARTIFACT, save_all=True, append_images=frames[1:], duration=durations, loop=0)
    still = scene("bound", 1.0)
    still.save(STILL)
    still.save(Path("/opt/cursor/artifacts/numa_fc_bind_still.png"))
    print(f"Wrote {len(frames)} frames → {GIF}")
    print(f"Still → {STILL}")


if __name__ == "__main__":
    main()
