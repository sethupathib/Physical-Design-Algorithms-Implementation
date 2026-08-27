#!/usr/bin/env python3
from pathlib import Path
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

OUT = Path(__file__).resolve().parent / "figures"
OUT.mkdir(parents=True, exist_ok=True)


def fig_flow():
    fig, ax = plt.subplots(figsize=(10, 3.4))
    ax.axis("off")
    ax.set_title("Hack #1–2: FC → Vortex → severity branch", fontsize=13)
    boxes = [
        (0.3, 1.0, 1.8, 1.4, "#dbeafe", "run_fc\n(pool)"),
        (2.5, 1.0, 1.8, 1.4, "#fef3c7", "short_circuit?"),
        (4.7, 1.0, 1.8, 1.4, "#dcfce7", "run_vortex\n(policy YAML)"),
        (6.9, 1.0, 2.4, 1.4, "#ede9fe", "branch\nfatal/error/\nwarn/clean"),
    ]
    for x, y, w, h, c, t in boxes:
        ax.add_patch(mpatches.FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.04",
                                             facecolor=c, edgecolor="#334155", lw=1.4))
        ax.text(x + w / 2, y + h / 2, t, ha="center", va="center", fontsize=9)
        if x < 6:
            ax.annotate("", xy=(x + w + 0.15, y + h / 2), xytext=(x + w + 0.02, y + h / 2),
                        arrowprops=dict(arrowstyle="->", color="#334155"))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 3.2)
    fig.tight_layout()
    fig.savefig(OUT / "fig_fc_vortex_flow.png", dpi=140)
    plt.close()


def fig_hacks():
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.axis("off")
    ax.set_title("Ten Airflow hacks (CAD / methodology)", fontsize=13)
    items = [
        "1 Chain FC→Vortex", "2 Severity branch", "3 License pool", "4 Map corners",
        "5 Short-circuit", "6 Dataset on log", "7 Retry/backoff", "8 Workflow JSON",
        "9 SLA alert", "10 UI params",
    ]
    for i, t in enumerate(items):
        r, c = divmod(i, 2)
        x, y = 0.4 + c * 4.4, 4.0 - r * 0.7
        ax.add_patch(mpatches.FancyBboxPatch((x, y), 4.0, 0.55, boxstyle="round,pad=0.03",
                                             facecolor="#f1f5f9", edgecolor="#64748b"))
        ax.text(x + 0.2, y + 0.27, t, va="center", fontsize=11)
    ax.set_xlim(0, 9)
    ax.set_ylim(0, 5)
    fig.tight_layout()
    fig.savefig(OUT / "fig_ten_hacks.png", dpi=140)
    plt.close()


def fig_grep_trap():
    fig, ax = plt.subplots(figsize=(8, 3.6))
    ax.bar(["Naive grep\nfalse routes", "JSON overall\nARCHIVE (clean)"], [2, 2],
           color=["#f87171", "#4ade80"])
    ax.set_ylabel("Clean corners in demo (count)")
    ax.set_title("Killer insight: grepping rule names ≠ reading overall")
    ax.set_ylim(0, 3.5)
    fig.tight_layout()
    fig.savefig(OUT / "fig_grep_trap.png", dpi=140)
    plt.close()


if __name__ == "__main__":
    fig_flow()
    fig_hacks()
    fig_grep_trap()
    print("wrote", OUT)
