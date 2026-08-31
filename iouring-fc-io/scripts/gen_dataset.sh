#!/usr/bin/env bash
# Generate FC-shaped dataset:
#   data/small/  — many tiny files (liberty/LEF-ish)
#   data/large/  — few large files (DEF/netlist/log-ish)
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DATA="${ROOT}/data"
NSMALL="${NSMALL:-4000}"
SMALL_BYTES="${SMALL_BYTES:-8192}"
NLARGE="${NLARGE:-6}"
LARGE_MIB="${LARGE_MIB:-32}"

rm -rf "$DATA"
mkdir -p "$DATA/small" "$DATA/large"

echo "generating $NSMALL small files × ${SMALL_BYTES}B ..."
# batch via python for speed
python3 - <<PY
from pathlib import Path
root = Path("$DATA/small")
n, sz = int("$NSMALL"), int("$SMALL_BYTES")
blob = bytes([i % 256 for i in range(sz)])
for i in range(n):
    sub = root / f"lib{i % 64}"
    sub.mkdir(exist_ok=True)
    (sub / f"cell_{i}.libview").write_bytes(blob)
print("small done")
PY

echo "generating $NLARGE large files × ${LARGE_MIB}MiB ..."
python3 - <<PY
from pathlib import Path
root = Path("$DATA/large")
n, mib = int("$NLARGE"), int("$LARGE_MIB")
chunk = b"DEF/NETLIST/LOG-PROXY-" + bytes(range(256)) * 32
need = mib * 1024 * 1024
for i in range(n):
    p = root / f"design_corner_{i}.big"
    with p.open("wb") as f:
        left = need
        while left > 0:
            w = chunk if left >= len(chunk) else chunk[:left]
            f.write(w)
            left -= len(w)
print("large done")
PY

du -sh "$DATA" "$DATA/small" "$DATA/large"
find "$DATA" -type f | wc -l
