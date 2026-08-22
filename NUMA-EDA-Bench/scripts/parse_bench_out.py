#!/usr/bin/env python3
"""
Parse numa_mem_bench stdout and print a comparison table.

Usage:
  ./scripts/parse_bench_out.py results/unbound.txt results/local.txt [results/remote.txt]
"""

from __future__ import annotations

import re
import sys
from pathlib import Path


def parse(path: Path) -> dict:
    text = path.read_text(errors="replace")
    out: dict = {"path": str(path)}
    m = re.search(
        r"STREAM-triad bandwidth:\s*([\d.]+)\s*GiB/s", text, re.I
    )
    if m:
        out["triad_gibs"] = float(m.group(1))
    m = re.search(
        r"pointer-chase latency:\s*([\d.]+)\s*ns/hop", text, re.I
    )
    if m:
        out["latency_ns"] = float(m.group(1))
    m = re.search(r"threads=(\d+)", text)
    if m:
        out["threads"] = int(m.group(1))
    return out


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    rows = [parse(Path(p)) for p in sys.argv[1:]]
    print(f"{'file':40} {'triad GiB/s':>12} {'lat ns/hop':>12}")
    for r in rows:
        triad = r.get("triad_gibs", float("nan"))
        lat = r.get("latency_ns", float("nan"))
        print(f"{r['path'][:40]:40} {triad:12.3f} {lat:12.2f}")
    if len(rows) >= 2 and "triad_gibs" in rows[0] and "triad_gibs" in rows[1]:
        a, b = rows[0]["triad_gibs"], rows[1]["triad_gibs"]
        if a > 0:
            print(f"\ntriad ratio (file2/file1): {b / a:.3f}")
    if len(rows) >= 2 and "latency_ns" in rows[0] and "latency_ns" in rows[1]:
        a, b = rows[0]["latency_ns"], rows[1]["latency_ns"]
        if a > 0:
            print(f"latency ratio (file2/file1): {b / a:.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
