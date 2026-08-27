#!/usr/bin/env bash
# 1:1 comparison: YAML DSL (Vortex-style policy) vs Bash / Python / Perl ad-hoc.
#
# Measures:
#   - policy / script LOC (non-blank, non-comment where applicable)
#   - wall time on the same synthetic log
#   - triggered-rule agreement
#
# Optional real Vortex binary:
#   export VORTEX_BIN=/path/to/vortex
#   (must support search_by_rule against policy/design_health.yaml — see README)
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="${ROOT}/results"
POLICY="${ROOT}/policy/design_health.yaml"
LOG="${OUT}/synthetic_pd.log"
LINES="${LINES:-200000}"

mkdir -p "$OUT"
chmod +x \
  "${ROOT}/adhoc/bash_search_by_rule.sh" \
  "${ROOT}/adhoc/python_search_by_rule.py" \
  "${ROOT}/adhoc/perl_search_by_rule.pl" \
  "${ROOT}/runners/yaml_dsl_runner.py" \
  "${ROOT}/scripts/gen_synthetic_log.py" \
  2>/dev/null || true

echo "================================================================"
echo " Vortex-style YAML DSL  vs  Bash / Python / Perl ad-hoc"
echo "================================================================"
echo "root=$ROOT"
echo

# --- LOC ---
loc_file() {
  local f="$1"
  # non-blank, non-full-line-comment (# or //)
  grep -cvE '^\s*(#|//|$)' "$f" 2>/dev/null || echo 0
}

LOC_YAML="$(loc_file "$POLICY")"
LOC_BASH="$(loc_file "${ROOT}/adhoc/bash_search_by_rule.sh")"
LOC_PY="$(loc_file "${ROOT}/adhoc/python_search_by_rule.py")"
LOC_PL="$(loc_file "${ROOT}/adhoc/perl_search_by_rule.pl")"
LOC_RUNNER="$(loc_file "${ROOT}/runners/yaml_dsl_runner.py")"

{
  echo "loc_yaml_policy=$LOC_YAML"
  echo "loc_bash=$LOC_BASH"
  echo "loc_python=$LOC_PY"
  echo "loc_perl=$LOC_PL"
  echo "loc_yaml_runner_reference=$LOC_RUNNER"
} | tee "$OUT/loc.txt"

echo
echo "---- LOC (non-blank, non-comment) ----"
printf "  %-28s %5s\n" "policy YAML (intent)" "$LOC_YAML"
printf "  %-28s %5s\n" "bash ad-hoc" "$LOC_BASH"
printf "  %-28s %5s\n" "python ad-hoc" "$LOC_PY"
printf "  %-28s %5s\n" "perl ad-hoc" "$LOC_PL"
printf "  %-28s %5s\n" "yaml runner (reference)" "$LOC_RUNNER"
echo "  note: YAML is the shared policy. Runner/Vortex is the engine."
echo "        Ad-hoc scripts embed policy INSIDE implementation."
echo

# --- generate log ---
if [[ ! -f "$LOG" || "${REGEN_LOG:-0}" == "1" ]]; then
  echo "---- generating synthetic log ($LINES lines) ----"
  python3 "${ROOT}/scripts/gen_synthetic_log.py" --out "$LOG" --lines "$LINES"
fi
ls -lh "$LOG"
echo

time_cmd() {
  local label="$1"
  shift
  local t0 t1
  t0=$(date +%s.%N)
  "$@" >"$OUT/${label}.stdout" 2>"$OUT/${label}.stderr" || true
  t1=$(date +%s.%N)
  python3 -c "print(f'{float('$t1')-float('$t0'):.3f}')" >"$OUT/${label}.time"
  echo "  $label  $(cat "$OUT/${label}.time")s"
}

echo "---- runtime (same log) ----"
OUT_DIR="$OUT" time_cmd bash \
  bash "${ROOT}/adhoc/bash_search_by_rule.sh" "$LOG"
time_cmd python \
  python3 "${ROOT}/adhoc/python_search_by_rule.py" "$LOG" --json-out "$OUT/python_report.json"
OUT_DIR="$OUT" time_cmd perl \
  perl "${ROOT}/adhoc/perl_search_by_rule.pl" "$LOG"
time_cmd yaml_dsl \
  python3 "${ROOT}/runners/yaml_dsl_runner.py" --policy "$POLICY" --log "$LOG" --json

# Optional Vortex
if [[ -n "${VORTEX_BIN:-}" && -x "${VORTEX_BIN}" ]]; then
  echo "  (VORTEX_BIN set — attempting product path)"
  # Best-effort; flags vary by build — see README if this fails
  t0=$(date +%s.%N)
  if "$VORTEX_BIN" --search_by_rule --policy "$POLICY" --log "$LOG" \
      >"$OUT/vortex.stdout" 2>"$OUT/vortex.stderr"; then
    t1=$(date +%s.%N)
    python3 -c "print(f'{float('$t1')-float('$t0'):.3f}')" >"$OUT/vortex.time"
    echo "  vortex  $(cat "$OUT/vortex.time")s"
  else
    echo "  vortex  SKIP (binary present but CLI flags did not match — see stderr)"
    echo "skip" >"$OUT/vortex.time"
  fi
else
  echo "  vortex  SKIP (set VORTEX_BIN to measure the product binary)"
  echo "skip" >"$OUT/vortex.time"
fi
echo

# --- agreement on triggered set ---
OUT="$OUT" python3 - <<'PY' | tee "$OUT/SUMMARY.txt"
import json, os
from pathlib import Path

out = Path(os.environ["OUT"])

def load_yaml_dsl():
    return json.loads((out / "yaml_dsl.stdout").read_text())

def load_python():
    return json.loads((out / "python_report.json").read_text())

def load_bash():
    return json.loads((out / "bash_report.json").read_text())

def load_perl():
    return json.loads((out / "perl_report.json").read_text())

def triggered(rep):
    return {r["name"] for r in rep["results"] if r.get("triggered")}

yd = load_yaml_dsl()
py = load_python()
ba = load_bash()
pe = load_perl()

sets = {
    "yaml_dsl": triggered(yd),
    "python": triggered(py),
    "bash": triggered(ba),
    "perl": triggered(pe),
}
counts = {}
for label, rep in [("yaml_dsl", yd), ("python", py), ("bash", ba), ("perl", pe)]:
    counts[label] = {r["name"]: r["count"] for r in rep["results"]}

loc = dict(
    line.strip().split("=", 1)
    for line in (out / "loc.txt").read_text().splitlines()
    if "=" in line
)
times = {}
for label in ("bash", "python", "perl", "yaml_dsl", "vortex"):
    p = out / f"{label}.time"
    times[label] = p.read_text().strip() if p.exists() else "n/a"

print("=" * 72)
print("SUMMARY — YAML DSL policy vs ad-hoc Bash / Python / Perl")
print("=" * 72)
print()
print("1) Lines of code (non-blank, non-comment)")
print(f"   YAML policy (intent)     {loc.get('loc_yaml_policy','?'):>6}")
print(f"   Bash ad-hoc              {loc.get('loc_bash','?'):>6}")
print(f"   Python ad-hoc            {loc.get('loc_python','?'):>6}")
print(f"   Perl ad-hoc              {loc.get('loc_perl','?'):>6}")
print(f"   YAML reference runner*   {loc.get('loc_yaml_runner_reference','?'):>6}")
print("   * engine glue — not edited when changing rules; Vortex replaces this.")
yb, bb = int(loc["loc_yaml_policy"]), int(loc["loc_bash"])
print(f"   Bash / YAML LOC ratio    {bb/yb:.2f}x")
print()
print("2) Wall time (seconds) on same synthetic log")
for k in ("yaml_dsl", "bash", "python", "perl", "vortex"):
    print(f"   {k:<12} {times.get(k,'n/a')}")
print()
print("3) Triggered-rule agreement vs YAML DSL")
base = sets["yaml_dsl"]
for k, s in sets.items():
    mark = "MATCH" if s == base else f"DIFF missing={sorted(base-s)} extra={sorted(s-base)}"
    print(f"   {k:<12} {sorted(s)}  {mark}")
print()
print("4) Per-rule hit counts (yaml_dsl vs bash)")
names = [r["name"] for r in yd["results"]]
print(f"   {'rule':<22} {'yaml':>8} {'bash':>8} {'python':>8} {'perl':>8}")
for n in names:
    print(
        f"   {n:<22} {counts['yaml_dsl'][n]:8d} {counts['bash'][n]:8d} "
        f"{counts['python'][n]:8d} {counts['perl'][n]:8d}"
    )
print()
print("5) Methodological takeaway")
print("   - YAML encodes INTENT (what to find) in ~one screen.")
print("   - Ad-hoc scripts encode IMPLEMENTATION (how) and bury thresholds in code.")
print("   - Editing a threshold: YAML one field; Bash find/replace + retest.")
print("   - Team alignment: one policy file vs N personal scripts.")
print("   - Vortex product = industrial engine for this DSL (perf + audit), not the YAML itself.")
print("=" * 72)
PY

echo
echo "Artifacts under $OUT/"
echo "  SUMMARY.txt  loc.txt  *.time  *_report.json  synthetic_pd.log"
