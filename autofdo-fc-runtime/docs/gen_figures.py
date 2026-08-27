#!/usr/bin/env python3
"""Generate figures for autofdo-fc-runtime white paper."""
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

OUT = Path(__file__).resolve().parent / "figures"
OUT.mkdir(parents=True, exist_ok=True)


def fig_three_levers():
    fig, ax = plt.subplots(figsize=(10, 4.2))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 4)
    ax.axis("off")
    ax.set_title("Three levers to reduce FC / signoff wall time via FDO", fontsize=13, pad=12)

    boxes = [
        (0.4, 1.2, 2.8, 2.0, "#dbeafe", "Vendor binary\n(FC / PT / …)", "Ask AE for\nPGO builds"),
        (3.6, 1.2, 2.8, 2.0, "#dcfce7", "Your CAD helpers\n(owned source)", "GCC/Clang PGO\n(this repo)"),
        (6.8, 1.2, 2.8, 2.0, "#fef3c7", "Linux kernel\n(farm host)", "AutoFDO\n~10% latency*"),
    ]
    for x, y, w, h, c, t1, t2 in boxes:
        ax.add_patch(mpatches.FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.05",
                                             facecolor=c, edgecolor="#334155", linewidth=1.5))
        ax.text(x + w / 2, y + h * 0.62, t1, ha="center", va="center", fontsize=10, fontweight="bold")
        ax.text(x + w / 2, y + h * 0.28, t2, ha="center", va="center", fontsize=9, color="#334155")
    ax.text(5, 0.45, "* Published Neper tcp_rr kernel latency — not an automatic FC wall-time guarantee",
            ha="center", fontsize=8, color="#64748b")
    fig.tight_layout()
    fig.savefig(OUT / "fig_three_levers.png", dpi=140)
    plt.close()


def fig_pipeline():
    fig, ax = plt.subplots(figsize=(10, 3.2))
    ax.set_xlim(0, 12)
    ax.set_ylim(0, 3)
    ax.axis("off")
    ax.set_title("AutoFDO / PGO pipeline (mechanism — not a benchmark)", fontsize=12)
    steps = ["Build\n(+debug)", "Run\nrepresentative\nload", "Collect\nprofile\n(perf/PGO)", "Rebuild\nwith profile", "A/B\nmeasure"]
    for i, s in enumerate(steps):
        x = 0.4 + i * 2.3
        ax.add_patch(mpatches.FancyBboxPatch((x, 0.7), 2.0, 1.6, boxstyle="round,pad=0.04",
                                             facecolor="#f1f5f9", edgecolor="#0f172a"))
        ax.text(x + 1.0, 1.5, s, ha="center", va="center", fontsize=9)
        if i < len(steps) - 1:
            ax.annotate("", xy=(x + 2.25, 1.5), xytext=(x + 2.05, 1.5),
                        arrowprops=dict(arrowstyle="->", color="#0f172a"))
    fig.tight_layout()
    fig.savefig(OUT / "fig_pipeline.png", dpi=140)
    plt.close()


def fig_literature_10():
    fig, ax = plt.subplots(figsize=(7.5, 4))
    labels = ["Neper tcp_rr\nlatency", "Warehouse\nservices"]
    vals = [10.6, 5.0]
    bars = ax.bar(labels, vals, color=["#0ea5e9", "#6366f1"], width=0.55)
    ax.set_ylabel("Published improvement (%)")
    ax.set_title("Literature: Linux kernel AutoFDO (not this microbench)")
    ax.set_ylim(0, 14)
    for b, v in zip(bars, vals):
        ax.text(b.get_x() + b.get_width() / 2, v + 0.4, f"{v:g}%", ha="center", fontsize=11)
    ax.text(0.5, -0.22, "Sources: LPC 2024 / LLVM discourse / LWN — cite papers, not results/SUMMARY.txt",
            transform=ax.transAxes, ha="center", fontsize=8, color="#64748b")
    fig.tight_layout()
    fig.savefig(OUT / "fig_literature_10pct.png", dpi=140)
    plt.close()


def fig_claim_scope():
    fig, ax = plt.subplots(figsize=(8, 3.5))
    ax.axis("off")
    ax.set_title("Claim scope — what you may say", fontsize=12)
    rows = [
        ("OK", "Kernel AutoFDO ~10% latency on Neper (literature)", "#dcfce7"),
        ("OK", "Our proxy PGO: see CLAIM_GATE on this host", "#dcfce7"),
        ("OK", "Farm FC deck median −X% on AutoFDO kernel (if A/B)", "#dcfce7"),
        ("NO", "We AutoFDO’d Fusion Compiler by 10%", "#fee2e2"),
        ("NO", "Every signoff job is 10% faster", "#fee2e2"),
    ]
    for i, (tag, text, c) in enumerate(rows):
        y = 2.6 - i * 0.5
        ax.add_patch(mpatches.FancyBboxPatch((0.3, y), 7.4, 0.42, boxstyle="round,pad=0.02",
                                             facecolor=c, edgecolor="#94a3b8"))
        ax.text(0.55, y + 0.21, tag, va="center", fontsize=9, fontweight="bold")
        ax.text(1.3, y + 0.21, text, va="center", fontsize=9)
    ax.set_xlim(0, 8)
    ax.set_ylim(0, 3.2)
    fig.tight_layout()
    fig.savefig(OUT / "fig_claim_scope.png", dpi=140)
    plt.close()


if __name__ == "__main__":
    fig_three_levers()
    fig_pipeline()
    fig_literature_10()
    fig_claim_scope()
    print(f"wrote figures under {OUT}")
