#!/usr/bin/env python3
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).resolve().parents[1] / "demo"
OUT.mkdir(parents=True, exist_ok=True)
W, H = 900, 400
BG, CARD, ACC, TEXT, MUTED = (15, 23, 42), (30, 41, 59), (14, 165, 233), (248, 250, 252), (148, 163, 184)


def font(n):
    for p in ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
              "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(p, n)
        except OSError:
            pass
    return ImageFont.load_default()


def frame(i):
    im = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(im)
    d.text((36, 20), "PDKG — ChipMind-inspired PD knowledge graph", fill=TEXT, font=font(24))
    d.text((36, 56), "Accurate curation first · arXiv:2512.05371 methodology", fill=MUTED, font=font(14))
    steps = ["Ontology", "Gold triples", "CSA + IR", "Hierarchical\ntriples", "Multi-hop\nquery"]
    for s, lab in enumerate(steps):
        x = 40 + s * 165
        fill = ACC if s == i else ((34, 197, 94) if s < i else CARD)
        d.rounded_rectangle((x, 110, x + 145, 220), radius=12, fill=fill)
        d.text((x + 12, 145), lab, fill=TEXT, font=font(15))
    notes = [
        "Closed types/relations — validator rejects unknown edges.",
        "Each gold fact has confidence + provenance.",
        "Declarative vs procedural → Circuit Semantic Anchor.",
        "T_B / T_A / T_L / T_N exactly as ChipMind schema.",
        "Density→congestion→detour→setup — PD signal-chain analogue.",
    ]
    d.rounded_rectangle((40, 260, W - 40, 360), radius=10, fill=CARD)
    d.text((60, 300), notes[i], fill=TEXT, font=font(17))
    return im


def main():
    frames = [frame(i) for i in range(5)]
    gif = []
    for fr in frames:
        gif.extend([fr] * 12)
    path = OUT / "pdkg_construction.gif"
    gif[0].save(path, save_all=True, append_images=gif[1:], duration=90, loop=0)
    frames[-1].save(OUT / "pdkg_construction_still.png")
    print("wrote", path)


if __name__ == "__main__":
    main()
