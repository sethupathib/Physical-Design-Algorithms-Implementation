#!/usr/bin/env python3
"""Parse a minimal LSF-like accounting fixture and score parallel efficiency.

On TSRI EDA Cloud, use `bacct -l <jobId>` / rep files. This script accepts a
simplified YAML fixture so the lab is clone-ready without LSF.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def score(rec: dict) -> dict:
    slots = float(rec["slots_requested"])
    cpu_time = float(rec["cpu_time_sec"])
    wall = float(rec["wall_time_sec"])
    # Rough analogs to guide metrics:
    # HOG_FACTOR ~ cpu_time / wall  (closer to slots_requested is better)
    # CPU_EFFICIENCY ~ (cpu_time / (wall * slots)) * 100
    hog = cpu_time / wall if wall else 0.0
    eff = (cpu_time / (wall * slots) * 100.0) if wall and slots else 0.0
    return {
        "job_id": rec.get("job_id"),
        "slots_requested": slots,
        "hog_factor": round(hog, 3),
        "cpu_efficiency_pct": round(eff, 2),
        "hog_target": slots,
        "verdict": "GOOD"
        if hog >= 0.7 * slots and eff >= 70.0
        else "POOR_PARALLEL_OR_OVERREQUESTED",
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--fixture",
        type=Path,
        default=ROOT / "fixtures" / "bacct_sample.yaml",
    )
    args = p.parse_args()
    doc = yaml.safe_load(args.fixture.read_text())
    jobs = doc if isinstance(doc, list) else doc.get("jobs", [])
    for rec in jobs:
        s = score(rec)
        print(
            f"job_id={s['job_id']} hog_factor={s['hog_factor']} "
            f"(target≈{s['hog_target']}) cpu_efficiency_pct={s['cpu_efficiency_pct']} "
            f"verdict={s['verdict']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
