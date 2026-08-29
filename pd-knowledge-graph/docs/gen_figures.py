#!/usr/bin/env python3
from pathlib import Path
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

OUT = Path(__file__).resolve().parent / "figures"
OUT.mkdir(parents=True, exist_ok=True)


def fig_chipmind_map():
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.axis("off")
    ax.set_title("ChipMind → PDKG mapping (arXiv:2512.05371)", fontsize=13)
    rows = [
        ("ChipMind ChipKG", "PDKG", "#dbeafe", "#dcfce7"),
        ("CSA (type, entity)", "FlowStage / FailureMode / …", "#dbeafe", "#dcfce7"),
        ("T_B / T_A / T_L / T_N", "backbone / aux / link / norm", "#dbeafe", "#dcfce7"),
        ("Spec signal chains", "PD causal chains (density→setup)", "#dbeafe", "#dcfce7"),
        ("SpecEval 0.95 F1 (paper)", "Offline atomic-F1 on gold (this repo)", "#fee2e2", "#fef3c7"),
    ]
    ax.add_patch(mpatches.FancyBboxPatch((0.4, 3.2), 4.2, 0.5, boxstyle="round,pad=0.02", facecolor="#1e293b"))
    ax.add_patch(mpatches.FancyBboxPatch((5.2, 3.2), 4.2, 0.5, boxstyle="round,pad=0.02", facecolor="#1e293b"))
    ax.text(2.5, 3.45, rows[0][0], ha="center", color="white", fontsize=10, fontweight="bold")
    ax.text(7.3, 3.45, rows[0][1], ha="center", color="white", fontsize=10, fontweight="bold")
    for i, (a, b, c1, c2) in enumerate(rows[1:]):
        y = 2.5 - i * 0.65
        ax.add_patch(mpatches.FancyBboxPatch((0.4, y), 4.2, 0.5, boxstyle="round,pad=0.02", facecolor=c1, edgecolor="#64748b"))
        ax.add_patch(mpatches.FancyBboxPatch((5.2, y), 4.2, 0.5, boxstyle="round,pad=0.02", facecolor=c2, edgecolor="#64748b"))
        ax.text(2.5, y + 0.25, a, ha="center", va="center", fontsize=9)
        ax.text(7.3, y + 0.25, b, ha="center", va="center", fontsize=9)
        ax.annotate("", xy=(5.15, y + 0.25), xytext=(4.65, y + 0.25), arrowprops=dict(arrowstyle="->"))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 4)
    fig.tight_layout()
    fig.savefig(OUT / "fig_chipmind_mapping.png", dpi=140)
    plt.close()


def fig_causal():
    fig, ax = plt.subplots(figsize=(10, 2.8))
    ax.axis("off")
    ax.set_title("Gold multi-hop: density → setup (PD analogue of signal tracing)", fontsize=12)
    nodes = ["High_Placement\n_Density", "Routing\n_Congestion", "Detour\n_Wirelength", "Setup\n_Violation"]
    for i, n in enumerate(nodes):
        x = 0.5 + i * 2.4
        ax.add_patch(mpatches.FancyBboxPatch((x, 0.8), 2.0, 1.2, boxstyle="round,pad=0.04",
                                             facecolor="#fef3c7", edgecolor="#92400e", lw=1.5))
        ax.text(x + 1.0, 1.4, n, ha="center", va="center", fontsize=9)
        if i < 3:
            ax.annotate("", xy=(x + 2.15, 1.4), xytext=(x + 2.05, 1.4),
                        arrowprops=dict(arrowstyle="->", color="#92400e", lw=2))
            ax.text(x + 2.2, 1.85, "causes", fontsize=8, color="#92400e")
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 2.6)
    fig.tight_layout()
    fig.savefig(OUT / "fig_causal_chain.png", dpi=140)
    plt.close()


def fig_accuracy():
    fig, ax = plt.subplots(figsize=(7, 3.5))
    ax.bar(["Gold triples", "Auto-merge\nedges", "Atomic-F1\nproxy ×100"], [62, 73, 100],
           color=["#0ea5e9", "#6366f1", "#22c55e"])
    ax.set_title("PDKG accuracy snapshot (this build)")
    ax.set_ylabel("count / score")
    fig.tight_layout()
    fig.savefig(OUT / "fig_accuracy_snapshot.png", dpi=140)
    plt.close()


if __name__ == "__main__":
    fig_chipmind_map()
    fig_causal()
    fig_accuracy()
    print("wrote", OUT)
