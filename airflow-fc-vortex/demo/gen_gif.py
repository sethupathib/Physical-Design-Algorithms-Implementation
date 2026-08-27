#!/usr/bin/env python3
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).resolve().parents[1] / "demo"
OUT.mkdir(parents=True, exist_ok=True)
W, H = 880, 400
BG, CARD, ACC, TEXT, MUTED = (15, 23, 42), (30, 41, 59), (56, 189, 248), (248, 250, 252), (148, 163, 184)


def font(n):
    for p in ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
              "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(p, n)
        except OSError:
            pass
    return ImageFont.load_default()


def frame(i: int) -> Image.Image:
    im = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(im)
    d.text((36, 22), "Airflow hacks: FC → Vortex → route", fill=TEXT, font=font(26))
    d.text((36, 58), "Laptop-simple workflow control (not AutoFDO)", fill=MUTED, font=font(15))
    steps = ["Trigger FC", "Write log", "Vortex policy", "Branch severity", "Act"]
    for s, lab in enumerate(steps):
        x = 40 + s * 160
        fill = ACC if s == i else (34, 197, 94) if s < i else CARD
        d.rounded_rectangle((x, 120, x + 140, 220), radius=12, fill=fill)
        d.text((x + 18, 155), lab, fill=TEXT, font=font(16))
    notes = [
        "UI/API params: design + corner (Hack #10).",
        "Mock or real fc_shell writes the chamber log.",
        "search_by_rule YAML — shared with methodology.",
        "fatal→page, error→jira, warn→slack, clean→archive.",
        "Humans only where judgment is needed.",
    ]
    d.rounded_rectangle((40, 260, W - 40, 360), radius=10, fill=CARD)
    d.text((60, 300), notes[i], fill=TEXT, font=font(18))
    return im


def main():
    frames = [frame(i) for i in range(5)]
    gif = []
    for fr in frames:
        gif.extend([fr] * 14)
    path = OUT / "airflow_fc_vortex_flow.gif"
    gif[0].save(path, save_all=True, append_images=gif[1:], duration=80, loop=0)
    frames[-1].save(OUT / "airflow_fc_vortex_flow_still.png")
    print("wrote", path)


if __name__ == "__main__":
    main()
