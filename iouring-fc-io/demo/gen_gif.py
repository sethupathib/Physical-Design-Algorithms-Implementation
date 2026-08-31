#!/usr/bin/env python3
"""Mechanism GIF for white paper / README — not a benchmark."""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).resolve().parents[1] / "demo"
OUT.mkdir(parents=True, exist_ok=True)
W, H = 920, 400
BG, CARD, ACC, OK, TEXT, MUTED = (
    (15, 23, 42),
    (30, 41, 59),
    (14, 165, 233),
    (34, 197, 94),
    (248, 250, 252),
    (148, 163, 184),
)


def font(n):
    for p in (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ):
        try:
            return ImageFont.truetype(p, n)
        except OSError:
            pass
    return ImageFont.load_default()


def frame(i: int) -> Image.Image:
    im = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(im)
    d.text((36, 22), "io_uring around Fusion Compiler", fill=TEXT, font=font(26))
    d.text((36, 58), "Mechanism storyboard — measure stage-in ≠ FC wall", fill=MUTED, font=font(14))
    steps = ["NFS deck", "io_uring\nhydrate", "Local NVMe", "fc_shell", "Log ingest"]
    for s, lab in enumerate(steps):
        x = 36 + s * 175
        fill = ACC if s == i else (OK if s < i else CARD)
        d.rounded_rectangle((x, 110, x + 155, 220), radius=12, fill=fill)
        d.text((x + 16, 145), lab, fill=TEXT, font=font(15))
    notes = [
        "Cold libraries and design inputs live on shared storage.",
        "Batch open/read via liburing into scratch (you own this code).",
        "Point FC_WORK_DIR at the hydrated tree.",
        "Closed binary runs as today — CPU/NUMA still dominate compute.",
        "Optional: uring-read multi-GB logs into Vortex / QA.",
    ]
    d.rounded_rectangle((36, 255, W - 36, 360), radius=10, fill=CARD)
    d.text((56, 295), notes[i], fill=TEXT, font=font(17))
    return im


def main():
    frames = [frame(i) for i in range(5)]
    gif = []
    for fr in frames:
        gif.extend([fr] * 12)
    path = OUT / "iouring_fc_pipeline.gif"
    gif[0].save(path, save_all=True, append_images=gif[1:], duration=90, loop=0)
    frames[-1].save(OUT / "iouring_fc_pipeline_still.png")
    print("wrote", path)


if __name__ == "__main__":
    main()
