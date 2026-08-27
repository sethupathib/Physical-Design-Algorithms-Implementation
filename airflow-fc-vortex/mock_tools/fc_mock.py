#!/usr/bin/env python3
"""mock fc_shell — writes a PD-shaped log. NOT Synopsys Fusion Compiler."""
from __future__ import annotations

import argparse
import json
import random
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


TEMPLATES = {
    "clean": [
        "INFO: FusionCompiler mock start design={design} corner={corner}",
        "INFO: place_opt complete",
        "INFO: route complete",
        "INFO: Setup slack +12.4ps",
        "INFO: Hold slack +3.1ps",
        "INFO: DRC clean",
        "INFO: FusionCompiler mock done status=OK",
    ],
    "timing_fail": [
        "INFO: FusionCompiler mock start design={design} corner={corner}",
        "INFO: place_opt complete",
        "WARN: MaxTran violations count=42",
        "ERROR: VIOLATED setup path u12/inst_9 slack=-18.2ps",
        "ERROR: Setup slack -18.2",
        "ERROR: VIOLATED hold path u3/inst_1 slack=-2.0ps",
        "INFO: FusionCompiler mock done status=TIMING_FAIL",
    ],
    "fatal": [
        "INFO: FusionCompiler mock start design={design} corner={corner}",
        "INFO: place_opt complete",
        "FATAL: INTERNAL ERROR in legalize",
        "ABORT: stack trace 0xdeadbeef",
        "INFO: FusionCompiler mock done status=FATAL",
    ],
    "drc_fail": [
        "INFO: FusionCompiler mock start design={design} corner={corner}",
        "INFO: route complete",
        "ERROR: DRC violation metal2 spacing cell X",
        "ERROR: DRC error count=17",
        "WARN: ANTENNA violation net n42",
        "INFO: Congestion > 0.9 region R7",
        "INFO: FusionCompiler mock done status=DRC_FAIL",
    ],
}


def main() -> int:
    ap = argparse.ArgumentParser(description="Mock Fusion Compiler (demo only)")
    ap.add_argument("--design", default="block_a")
    ap.add_argument("--corner", default="ss_0p75v_125c")
    ap.add_argument("--scenario", choices=sorted(TEMPLATES), default="timing_fail")
    ap.add_argument("--out-log", required=True)
    ap.add_argument("--work-secs", type=float, default=0.4, help="Fake runtime")
    ap.add_argument("--fail-license", action="store_true")
    ap.add_argument("--json-meta", default="")
    args = ap.parse_args()

    if args.fail_license:
        print("ERROR: Failed to checkout FC_Compiler license", file=sys.stderr)
        return 3

    out = Path(args.out_log)
    out.parent.mkdir(parents=True, exist_ok=True)
    time.sleep(max(0.0, args.work_secs))

    lines = [
        t.format(design=args.design, corner=args.corner) for t in TEMPLATES[args.scenario]
    ]
    # sprinkle noise so Vortex counts vary a bit
    rng = random.Random(f"{args.design}:{args.corner}:{args.scenario}")
    extra = []
    if args.scenario != "clean":
        for _ in range(rng.randint(2, 8)):
            extra.append(f"INFO: filler cell place tick={rng.randint(1, 9999)}")
    stamp = datetime.now(timezone.utc).isoformat()
    body = [f"# mock_fc watermark utc={stamp}", *lines, *extra, ""]
    out.write_text("\n".join(body), encoding="utf-8")

    meta = {
        "tool": "fc_mock",
        "design": args.design,
        "corner": args.corner,
        "scenario": args.scenario,
        "log": str(out.resolve()),
        "status": args.scenario,
        "utc": stamp,
    }
    print(json.dumps(meta))
    if args.json_meta:
        Path(args.json_meta).write_text(json.dumps(meta, indent=2), encoding="utf-8")

    # non-zero only for fatal (mimic hard tool death)
    return 2 if args.scenario == "fatal" else 0


if __name__ == "__main__":
    raise SystemExit(main())
