#!/usr/bin/env python3
"""Generate white-paper figures (PNG) under docs/figures/."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
FIG = ROOT / "docs" / "figures"
DEMO = ROOT / "demo"
FIG.mkdir(parents=True, exist_ok=True)

# Import GIF scene renderer
sys.path.insert(0, str(DEMO))
import gen_gif as g  # noqa: E402


def font(size: int, bold: bool = False, mono: bool = False):
    if mono:
        cands = [
            "/usr/share/fonts/truetype/jetbrains-mono/JetBrainsMono-Bold.ttf"
            if bold
            else "/usr/share/fonts/truetype/jetbrains-mono/JetBrainsMono-Regular.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
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


def save_scene(name: str, kind: str, t: float = 1.0):
    img = g.scene(kind, t)
    # scale down slightly for PDF readability
    img = img.resize((960, 540), Image.Resampling.LANCZOS)
    path = FIG / f"{name}.png"
    img.save(path)
    print("wrote", path)


def terminal_shot(path: Path, title: str, lines: list[str], w=960, h=420):
    img = Image.new("RGB", (w, h), (18, 24, 34))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((16, 16, w - 16, h - 16), radius=12, fill=(28, 36, 48), outline=(70, 90, 110), width=2)
    d.text((36, 32), title, font=font(18, bold=True), fill=(232, 148, 48))
    y = 70
    fm = font(13, mono=True)
    for line in lines:
        color = (120, 220, 140) if line.startswith("$") or line.startswith("#") else (220, 228, 236)
        if line.startswith("ERROR") or "DO_NOT" in line or "Refusing" in line:
            color = (232, 120, 100)
        if line.startswith("WARNING"):
            color = (232, 180, 80)
        d.text((36, y), line[:110], font=fm, fill=color)
        y += 20
        if y > h - 40:
            break
    img.save(path)
    print("wrote", path)


def flow_diagram(path: Path):
    w, h = 960, 520
    img = Image.new("RGB", (w, h), (248, 249, 252))
    d = ImageDraw.Draw(img)
    boxes = [
        (40, 40, 280, 120, "1. Topology", "numa_report.sh\nnumactl -H"),
        (340, 40, 580, 120, "2. Fit check", "peak RSS vs\nnode MemFree"),
        (640, 40, 880, 120, "3. Policy", "cpunodebind=N\nmembind / preferred"),
        (40, 200, 280, 280, "4. Wrap", "run_with_numactl.sh\nfc_shell …"),
        (340, 200, 580, 280, "5. Observe", "numastat -p\nstage wall time"),
        (640, 200, 880, 280, "6. Measure*", "compare_numa.sh\n(≥2 nodes only)"),
    ]
    for x0, y0, x1, y1, title, body in boxes:
        d.rounded_rectangle((x0, y0, x1, y1), radius=10, fill=(255, 255, 255), outline=(40, 70, 120), width=2)
        d.text((x0 + 16, y0 + 12), title, font=font(16, bold=True), fill=(20, 40, 70))
        d.text((x0 + 16, y0 + 42), body, font=font(13), fill=(60, 70, 85))
    # arrows
    for x in (290, 590):
        d.polygon([(x, 75), (x + 40, 80), (x, 85)], fill=(232, 148, 48))
    d.polygon([(160, 130), (170, 190), (150, 190)], fill=(232, 148, 48))
    for x in (290, 590):
        d.polygon([(x, 235), (x + 40, 240), (x, 245)], fill=(232, 148, 48))
    d.text(
        (40, 320),
        "* Step 6 is citeable only on multi-socket hosts. Single-node VMs correctly refuse.",
        font=font(13),
        fill=(90, 100, 110),
    )
    d.text((40, 360), "Decision: RSS fits node MemFree?", font=font(15, bold=True), fill=(20, 40, 70))
    d.rounded_rectangle((40, 400, 450, 480), radius=8, fill=(230, 255, 240), outline=(40, 140, 80), width=2)
    d.text((56, 420), "YES → membind (hard) on that node", font=font(14, bold=True), fill=(20, 90, 50))
    d.text((56, 448), "./scripts/run_with_numactl.sh N <cmd>", font=font(13, mono=True), fill=(30, 60, 40))
    d.rounded_rectangle((510, 400, 920, 480), radius=8, fill=(255, 244, 230), outline=(180, 100, 40), width=2)
    d.text((526, 420), "NO / unsure → preferred, or don't bind", font=font(14, bold=True), fill=(120, 60, 20))
    d.text((526, 448), "POLICY=preferred ./scripts/run_with_numactl.sh …", font=font(12, mono=True), fill=(80, 50, 30))
    img.save(path)
    print("wrote", path)


def metrics_card(path: Path):
    w, h = 960, 360
    img = Image.new("RGB", (w, h), (248, 249, 252))
    d = ImageDraw.Draw(img)
    d.text((40, 24), "Microbench metrics (hardware compare only)", font=font(18, bold=True), fill=(20, 40, 70))
    cards = [
        (40, 70, 460, 200, "triad (GiB/s)", "STREAM a[i]=b[i]+s*c[i]\nover a large array", "Higher is better", "Bandwidth proxy"),
        (500, 70, 920, 200, "chase (ns/hop)", "Shuffled pointer chase\nover a large index cycle", "Lower is better", "Latency proxy"),
    ]
    for x0, y0, x1, y1, title, body, better, note in cards:
        d.rounded_rectangle((x0, y0, x1, y1), radius=10, fill=(255, 255, 255), outline=(40, 70, 120), width=2)
        d.text((x0 + 16, y0 + 14), title, font=font(16, bold=True), fill=(20, 40, 70))
        d.text((x0 + 16, y0 + 50), body, font=font(13), fill=(60, 70, 85))
        d.text((x0 + 16, y0 + 100), better, font=font(13, bold=True), fill=(40, 140, 80))
        d.text((x0 + 200, y0 + 100), note, font=font(13), fill=(120, 90, 40))
    d.rounded_rectangle((40, 230, 920, 330), radius=10, fill=(255, 240, 240), outline=(180, 60, 60), width=2)
    d.text((56, 250), "Not FC wall time. Not QoR. Not a 1-node result.", font=font(15, bold=True), fill=(140, 40, 40))
    d.text(
        (56, 285),
        "Cite CLAIM_GATE=CITEABLE=yes microbench only from ≥2 NUMA nodes; pair with stage time + numastat for farm claims.",
        font=font(13),
        fill=(90, 40, 40),
    )
    img.save(path)
    print("wrote", path)


def local_vs_remote_schematic(path: Path):
    w, h = 960, 400
    img = Image.new("RGB", (w, h), (16, 24, 36))
    d = ImageDraw.Draw(img)
    d.text((30, 20), "Local vs remote (schematic)", font=font(18, bold=True), fill=(236, 240, 246))

    # left: bad
    d.rounded_rectangle((30, 60, 460, 360), radius=12, fill=(28, 40, 58), outline=(232, 78, 78), width=2)
    d.text((50, 75), "BEFORE — remote fills", font=font(15, bold=True), fill=(232, 78, 78))
    d.rounded_rectangle((50, 120, 210, 260), radius=8, fill=(40, 55, 75), outline=(64, 148, 220), width=2)
    d.text((70, 140), "Node 0", font=font(13, bold=True), fill=(64, 148, 220))
    d.text((70, 170), "threads HOT", font=font(12), fill=(200, 210, 220))
    d.text((70, 195), "DRAM cold", font=font(12), fill=(140, 150, 160))
    d.rounded_rectangle((280, 120, 440, 260), radius=8, fill=(40, 55, 75), outline=(110, 130, 150), width=2)
    d.text((300, 140), "Node 1", font=font(13, bold=True), fill=(110, 130, 150))
    d.text((300, 170), "threads idle", font=font(12), fill=(200, 210, 220))
    d.text((300, 195), "working set", font=font(12), fill=(48, 168, 180))
    d.line([(210, 190), (280, 190)], fill=(232, 78, 78), width=4)
    d.text((215, 160), "UPI", font=font(12, bold=True), fill=(232, 78, 78))
    d.text((50, 290), "Every miss crosses the interconnect.", font=font(12), fill=(180, 190, 200))
    d.text((50, 315), "top still shows busy CPUs.", font=font(12), fill=(180, 190, 200))

    # right: good
    d.rounded_rectangle((500, 60, 930, 360), radius=12, fill=(28, 40, 58), outline=(56, 196, 120), width=2)
    d.text((520, 75), "AFTER — local bind", font=font(15, bold=True), fill=(56, 196, 120))
    d.rounded_rectangle((520, 120, 680, 260), radius=8, fill=(40, 55, 75), outline=(64, 148, 220), width=2)
    d.text((540, 140), "Node 0", font=font(13, bold=True), fill=(64, 148, 220))
    d.text((540, 170), "threads HOT", font=font(12), fill=(200, 210, 220))
    d.text((540, 195), "working set", font=font(12), fill=(48, 168, 180))
    d.rounded_rectangle((750, 120, 910, 260), radius=8, fill=(40, 55, 75), outline=(80, 90, 100), width=2)
    d.text((770, 140), "Node 1", font=font(13, bold=True), fill=(110, 130, 150))
    d.text((770, 170), "left alone", font=font(12), fill=(140, 150, 160))
    d.text((770, 195), "free RAM", font=font(12), fill=(140, 150, 160))
    d.line([(680, 190), (750, 190)], fill=(80, 100, 90), width=2)
    d.text((685, 160), "quiet", font=font(12), fill=(56, 196, 120))
    d.text((520, 290), "numactl --cpunodebind=0 --membind=0", font=font(12, mono=True), fill=(120, 220, 140))
    d.text((520, 315), "Only if peak RSS fits node MemFree.", font=font(12), fill=(180, 190, 200))
    img.save(path)
    print("wrote", path)


def main():
    # GIF storyboard frames
    save_scene("fig_intro", "intro", 1.0)
    save_scene("fig_unbound", "unbound", 0.85)
    save_scene("fig_policy", "policy", 1.0)
    save_scene("fig_bound", "bound", 1.0)
    save_scene("fig_end", "end", 1.0)

    # still from demo
    still = DEMO / "numa_fc_bind_still.png"
    if still.exists():
        Image.open(still).resize((960, 540), Image.Resampling.LANCZOS).save(FIG / "fig_still.png")
        print("wrote", FIG / "fig_still.png")

    flow_diagram(FIG / "fig_ops_flow.png")
    metrics_card(FIG / "fig_metrics.png")
    local_vs_remote_schematic(FIG / "fig_local_remote.png")

    # Live demo captures from this host
    report = subprocess.check_output([str(ROOT / "scripts" / "numa_report.sh")], text=True, cwd=ROOT)
    terminal_shot(
        FIG / "demo_numa_report.png",
        "Demo — ./scripts/numa_report.sh (this host)",
        report.strip().splitlines(),
        h=520,
    )

    smoke = subprocess.check_output(
        [str(ROOT / "build" / "numa_mem_bench"), "--bytes", "128M", "--threads", "4"],
        text=True,
        cwd=ROOT,
    )
    terminal_shot(
        FIG / "demo_smoke_bench.png",
        "Demo — make smoke / numa_mem_bench (1-node smoke only)",
        ["$ ./build/numa_mem_bench --bytes 128M --threads 4", ""] + smoke.strip().splitlines(),
        h=280,
    )

    cmp = subprocess.run(
        [str(ROOT / "examples" / "compare_numa.sh")],
        text=True,
        cwd=ROOT,
        capture_output=True,
    )
    cmp_lines = (cmp.stderr or cmp.stdout or "").strip().splitlines()
    terminal_shot(
        FIG / "demo_compare_refuse.png",
        "Demo — compare_numa.sh on 1-node host (correct refusal)",
        ["$ ./examples/compare_numa.sh", f"# exit={cmp.returncode}"] + cmp_lines,
        h=280,
    )

    wrap = subprocess.run(
        ["env", "FORCE=1", str(ROOT / "scripts" / "run_with_numactl.sh"), "0", "/bin/true"],
        text=True,
        cwd=ROOT,
        capture_output=True,
    )
    wrap_out = (wrap.stdout + wrap.stderr).strip().splitlines()
    terminal_shot(
        FIG / "demo_wrapper.png",
        "Demo — run_with_numactl.sh 0 /bin/true (FORCE=1 for low MemFree)",
        ["$ FORCE=1 ./scripts/run_with_numactl.sh 0 /bin/true", ""] + wrap_out,
        h=420,
    )

    # GIF file note card
    gif_card = Image.new("RGB", (960, 200), (248, 249, 252))
    d = ImageDraw.Draw(gif_card)
    d.rounded_rectangle((20, 20, 940, 180), radius=12, fill=(255, 255, 255), outline=(40, 70, 120), width=2)
    d.text((40, 50), "Animated GIF in the repository", font=font(18, bold=True), fill=(20, 40, 70))
    d.text((40, 90), "Path:  demo/numa_fc_bind.gif", font=font(14, mono=True), fill=(30, 60, 40))
    d.text((40, 120), "Regenerate:  make gif", font=font(14, mono=True), fill=(30, 60, 40))
    d.text((40, 150), "Labeled on every frame: mechanism · not a benchmark", font=font(13), fill=(90, 100, 110))
    gif_card.save(FIG / "fig_gif_pointer.png")
    print("wrote", FIG / "fig_gif_pointer.png")


if __name__ == "__main__":
    # ensure bench built
    bin_path = ROOT / "build" / "numa_mem_bench"
    if not bin_path.exists():
        subprocess.check_call(["make", "-j"], cwd=ROOT)
    main()
