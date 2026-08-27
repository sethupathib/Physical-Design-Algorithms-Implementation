#!/usr/bin/env python3
"""Generate a synthetic PD/signoff-style log for fair comparisons."""

from __future__ import annotations

import argparse
import random
from pathlib import Path

NOISE = [
    "INFO: reading liberty ...",
    "INFO: linking design blockA",
    "INFO: updating timing graph",
    "INFO: CTS iteration complete",
    "INFO: route optimization pass",
    "WARNING: low drive strength on net n_unused_{i}",
    "INFO: parasitics annotated",
]

SIGNAL = [
    ("setup", "VIOLATED setup path endpoint ff_reg_{i}/D slack -0.{j}"),
    ("setup", "Setup slack -{j} on path launch_clk -> ff_reg_{i}/D"),
    ("hold", "VIOLATED hold path endpoint ff_reg_{i}/D slack -0.0{j}"),
    ("hold", "Hold slack -{j}ps on capture edge"),
    ("maxtran", "MaxTran violation net net_{i} max_transition 0.2"),
    ("maxtran", "MAXTRAN fail pin buf_{i}/Z"),
    ("drc", "ERROR: DRC short metal2 shape_{i}"),
    ("drc", "DRC violation spacing M3 net_{i}"),
    ("antenna", "ANTENNA violation net ant_{i}"),
    ("antenna", "antenna violation ratio exceeded net_{i}"),
    ("cong", "Congestion > 0.9 Gcell ({i},{j})"),
    ("cong", "Overflow > 55 edge e_{i}"),
    ("fatal", "FATAL: license checkout failed"),
    ("fatal", "INTERNAL ERROR aborting — stack trace follows"),
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--lines", type=int, default=200_000)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--signal-every", type=int, default=500, help="inject a signal line every N noise lines")
    args = ap.parse_args()
    rng = random.Random(args.seed)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w") as f:
        f.write(f"# synthetic PD log lines={args.lines} seed={args.seed}\n")
        for i in range(args.lines):
            if i > 0 and i % args.signal_every == 0:
                kind, tmpl = SIGNAL[rng.randrange(len(SIGNAL))]
                f.write(tmpl.format(i=i % 10000, j=rng.randint(1, 9)) + "\n")
            else:
                f.write(NOISE[rng.randrange(len(NOISE))].format(i=i % 1000) + "\n")
    print(f"wrote {args.out} ({args.lines} lines, ~{args.out.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
