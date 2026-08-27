#!/usr/bin/env python3
"""Mechanism GIF: AutoFDO pipeline for farm FC hosts."""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).resolve().parents[1] / "demo"
OUT.mkdir(parents=True, exist_ok=True)

W, H = 900, 420
BG = (15, 23, 42)
CARD = (30, 41, 59)
ACCENT = (14, 165, 233)
OK = (34, 197, 94)
TEXT = (248, 250, 252)
MUTED = (148, 163, 184)


def font(size):
    for p in (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ):
        try:
            return ImageFont.truetype(p, size)
        except OSError:
            continue
    return ImageFont.load_default()


def frame(step: int) -> Image.Image:
    im = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(im)
    d.text((40, 24), "AutoFDO under Fusion Compiler / signoff", fill=TEXT, font=font(28))
    d.text((40, 64), "Mechanism storyboard — not a wall-time benchmark", fill=MUTED, font=font(16))

    stages = [
        "1. Boot profile\n    kernel",
        "2. Run FC /\n    signoff load",
        "3. perf sample\n    (LBR)",
        "4. Rebuild\n    AutoFDO kernel",
        "5. A/B same\n    deck",
    ]
    for i, label in enumerate(stages):
        x = 30 + i * 170
        y = 130
        active = i <= step
        fill = ACCENT if i == step else (OK if active else CARD)
        d.rounded_rectangle((x, y, x + 150, y + 120), radius=12, fill=fill)
        d.text((x + 12, y + 30), label, fill=TEXT if active or i == step else MUTED, font=font(15))
        if i < len(stages) - 1:
            d.polygon([(x + 155, y + 60), (x + 168, y + 52), (x + 168, y + 68)], fill=MUTED)

    notes = [
        "Install AutoFDO-ready kernel on a pilot rack (IT + methodology).",
        "Representative FC/signoff traffic trains the profile — not a toy loop.",
        "Hardware sampling keeps overhead low vs instrumentation FDO.",
        "Clang rebuild with sample profile; watermark the kernel build.",
        "Cite farm median wall-time only if the A/B gate passes.",
    ]
    d.rounded_rectangle((40, 290, W - 40, 380), radius=10, fill=CARD)
    d.text((60, 318), notes[step], fill=TEXT, font=font(18))
    return im


def main():
    frames = [frame(i) for i in range(5)]
    # dwell on each step
    gif_frames = []
    for fr in frames:
        gif_frames.extend([fr] * 12)
    path = OUT / "autofdo_fc_pipeline.gif"
    gif_frames[0].save(
        path,
        save_all=True,
        append_images=gif_frames[1:],
        duration=90,
        loop=0,
        optimize=True,
    )
    frames[-1].save(OUT / "autofdo_fc_pipeline_still.png")
    print(f"wrote {path}")


if __name__ == "__main__":
    main()
