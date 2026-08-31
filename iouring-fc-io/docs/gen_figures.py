#!/usr/bin/env python3
"""Figures for io_uring FC white paper — driven by results/summary.json when present."""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(__file__).resolve().parent / "figures"
OUT.mkdir(parents=True, exist_ok=True)


def load_medians():
    p = ROOT / "results" / "summary.json"
    if not p.exists():
        return {}
    data = json.loads(p.read_text())
    return data.get("medians_sec") or {}


def fig_scope():
    fig, ax = plt.subplots(figsize=(9.5, 3.6))
    ax.axis("off")
    ax.set_title("Claim scope — io_uring × Fusion Compiler", fontsize=13)
    rows = [
        ("OK", "Stage-in / hydrate measured with CLAIM_GATE", "#dcfce7"),
        ("OK", "Log ingest in tools you compile (e.g. Vortex)", "#dcfce7"),
        ("OK", "Farm A/B: stage-in vs FC wall separately", "#dcfce7"),
        ("NO", "We recompiled Fusion Compiler with io_uring", "#fee2e2"),
        ("NO", "Every PnR job is X% faster on warm cache", "#fee2e2"),
    ]
    for i, (tag, text, c) in enumerate(rows):
        y = 2.7 - i * 0.5
        ax.add_patch(
            mpatches.FancyBboxPatch(
                (0.35, y), 8.8, 0.42, boxstyle="round,pad=0.02", facecolor=c, edgecolor="#94a3b8"
            )
        )
        ax.text(0.55, y + 0.21, tag, va="center", fontsize=9, fontweight="bold")
        ax.text(1.4, y + 0.21, text, va="center", fontsize=9)
    ax.set_xlim(0, 9.5)
    ax.set_ylim(0, 3.3)
    fig.tight_layout()
    fig.savefig(OUT / "fig_claim_scope.png", dpi=140)
    plt.close()


def fig_architecture():
    fig, ax = plt.subplots(figsize=(10, 3.2))
    ax.axis("off")
    ax.set_title("Where io_uring sits relative to FC", fontsize=13)
    boxes = [
        (0.3, 0.9, 2.6, 1.6, "#dbeafe", "NFS / cold\ndeck + libs"),
        (3.3, 0.9, 3.0, 1.6, "#fef3c7", "io_uring hydrate\n(stage-in)"),
        (6.7, 0.9, 2.8, 1.6, "#e2e8f0", "fc_shell\n(closed binary)"),
    ]
    for x, y, w, h, c, t in boxes:
        ax.add_patch(
            mpatches.FancyBboxPatch(
                (x, y), w, h, boxstyle="round,pad=0.04", facecolor=c, edgecolor="#334155", lw=1.4
            )
        )
        ax.text(x + w / 2, y + h / 2, t, ha="center", va="center", fontsize=10)
    for x in (2.95, 6.35):
        ax.annotate(
            "",
            xy=(x + 0.25, 1.7),
            xytext=(x, 1.7),
            arrowprops=dict(arrowstyle="->", color="#334155", lw=1.5),
        )
    ax.text(5.0, 0.35, "Measure left arrow (stage-in) and right box (FC wall) separately", ha="center", fontsize=8, color="#64748b")
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 3)
    fig.tight_layout()
    fig.savefig(OUT / "fig_architecture.png", dpi=140)
    plt.close()


def fig_speedups():
    med = load_medians()
    # keys like "posix:small_files"
    subsets = ["small_files", "large_files", "mixed"]
    backends = ["iouring", "iouring_openat"]
    # If missing, use last known published ratios from SUMMARY commentary
    speed = {b: [] for b in backends}
    labels = []
    for subset in subsets:
        p = med.get(f"posix:{subset}")
        labels.append(subset)
        for b in backends:
            u = med.get(f"{b}:{subset}")
            if p and u and u > 0:
                speed[b].append(p / u)
            else:
                # fallback placeholders only if empty file — prefer skip
                speed[b].append(float("nan"))

    fig, ax = plt.subplots(figsize=(8.5, 4.2))
    import math

    x = range(len(labels))
    w = 0.35
    vals0 = [v if not math.isnan(v) else 0 for v in speed["iouring"]]
    vals1 = [v if not math.isnan(v) else 0 for v in speed["iouring_openat"]]
    ax.bar([i - w / 2 for i in x], vals0, width=w, label="iouring", color="#0ea5e9")
    ax.bar([i + w / 2 for i in x], vals1, width=w, label="iouring_openat", color="#6366f1")
    ax.axhline(1.0, color="#94a3b8", ls="--", lw=1, label="posix baseline (=1.0)")
    ax.set_xticks(list(x))
    ax.set_xticklabels(labels)
    ax.set_ylabel("Speedup vs posix (>1 = faster)")
    ax.set_title("Warm-cache speedup on authoring host (from results/summary.json)")
    ax.legend(fontsize=8)
    ax.set_ylim(0, max(1.3, max(vals0 + vals1) * 1.15))
    fig.tight_layout()
    fig.savefig(OUT / "fig_speedup.png", dpi=140)
    plt.close()


def fig_workloads():
    fig, ax = plt.subplots(figsize=(9, 3.4))
    ax.axis("off")
    ax.set_title("FC-shaped workloads in the harness", fontsize=13)
    rows = [
        ("small_files", "4 000 × 8 KiB", "Liberty / LEF-ish views"),
        ("large_files", "6 × 32 MiB", "DEF / netlist / log blobs"),
        ("mixed", "all 4 006 files", "Full deck hydrate proxy"),
    ]
    for i, (a, b, c) in enumerate(rows):
        y = 2.2 - i * 0.7
        ax.add_patch(
            mpatches.FancyBboxPatch(
                (0.4, y), 8.8, 0.55, boxstyle="round,pad=0.03", facecolor="#f1f5f9", edgecolor="#64748b"
            )
        )
        ax.text(0.7, y + 0.28, a, va="center", fontsize=10, fontweight="bold")
        ax.text(3.5, y + 0.28, b, va="center", fontsize=10)
        ax.text(6.0, y + 0.28, c, va="center", fontsize=10)
    ax.set_xlim(0, 9.5)
    ax.set_ylim(0, 3)
    fig.tight_layout()
    fig.savefig(OUT / "fig_workloads.png", dpi=140)
    plt.close()


if __name__ == "__main__":
    fig_scope()
    fig_architecture()
    fig_speedups()
    fig_workloads()
    print(f"wrote figures under {OUT}")
