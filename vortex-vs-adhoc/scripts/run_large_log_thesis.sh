#!/usr/bin/env bash
# Large-log thesis harness — Vortex product binary vs bash / python / yaml_dsl.
#
# Real Vortex v25.1 CLI:
#   vortex <logfile> certify_high_quality 1 --search_by_rule <yaml>
#
# CLAIM_GATE_LARGE_LOG passes only if Vortex beats Python by ≥5× and is
# within 1.25× of bash (or faster).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export ROOT
export OUT="${ROOT}/results"
export POLICY_PY="${ROOT}/policy/design_health.yaml"
export POLICY_VX="${ROOT}/policy/design_health_vortex.yaml"
export LINES="${LINES:-10000000}"
export LOG="${OUT}/synthetic_pd_${LINES}.log"
export REGEN_LOG="${REGEN_LOG:-0}"
# Default to extracted eval package if present
export VORTEX_BIN="${VORTEX_BIN:-/workspace/vortex-dist/vortex-v25.1/bin/vortex}"

mkdir -p "$OUT"
chmod +x \
  "${ROOT}/adhoc/bash_search_by_rule.sh" \
  "${ROOT}/adhoc/python_search_by_rule.py" \
  "${ROOT}/runners/yaml_dsl_runner.py" \
  "${ROOT}/scripts/gen_synthetic_log.py" 2>/dev/null || true

exec python3 - <<'PY'
import time, subprocess, os, shutil
from pathlib import Path

root = Path(os.environ["ROOT"])
out = Path(os.environ["OUT"])
policy_py = Path(os.environ["POLICY_PY"])
policy_vx = Path(os.environ["POLICY_VX"])
log = Path(os.environ["LOG"])
lines = int(os.environ["LINES"])
vortex_bin = os.environ.get("VORTEX_BIN", "")

if (not log.exists()) or os.environ.get("REGEN_LOG") == "1":
    print(f"generating {lines} lines -> {log}", flush=True)
    t0 = time.perf_counter()
    subprocess.check_call([
        "python3", str(root / "scripts/gen_synthetic_log.py"),
        "--out", str(log), "--lines", str(lines),
    ])
    print(f"gen_s={time.perf_counter()-t0:.3f}", flush=True)

def run(label, cmd, cwd=None):
    t0 = time.perf_counter()
    p = subprocess.run(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, cwd=cwd
    )
    dt = time.perf_counter() - t0
    (out / f"large_{label}.stdout").write_text(p.stdout)
    (out / f"large_{label}.stderr").write_text(p.stderr)
    (out / f"large_{label}.time").write_text(f"{dt:.3f}\n")
    print(f"{label}_s={dt:.3f} rc={p.returncode}", flush=True)
    return dt, p.returncode

bash_s, _ = run("bash", ["bash", str(root / "adhoc/bash_search_by_rule.sh"), str(log)])
py_s, _ = run("python", [
    "python3", str(root / "adhoc/python_search_by_rule.py"), str(log),
    "--json-out", str(out / "large_python_report.json"),
])
yaml_s, _ = run("yaml", [
    "python3", str(root / "runners/yaml_dsl_runner.py"),
    "--policy", str(policy_py), "--log", str(log), "--json",
])

vortex_s = None
vortex_status = "SKIP"
vx_cwd = out / "vortex_run_cwd"
if vx_cwd.exists():
    shutil.rmtree(vx_cwd)
vx_cwd.mkdir(parents=True)

if vortex_bin and os.path.isfile(vortex_bin) and os.access(vortex_bin, os.X_OK):
    # Vortex CLI: vortex <log> certify_high_quality 1 --search_by_rule <yaml>
    vortex_s, rc = run(
        "vortex",
        [vortex_bin, str(log), "certify_high_quality", "1",
         "--search_by_rule", str(policy_vx)],
        cwd=str(vx_cwd),
    )
    vortex_status = "OK" if rc == 0 else "FAIL_CLI"
else:
    (out / "large_vortex.time").write_text("skip\n")
    print("vortex SKIP — set VORTEX_BIN", flush=True)

mb = log.stat().st_size / 1e6

gate_lines = [
    "CLAIM_GATE_LARGE_LOG",
    f"lines={lines}",
    f"size_MB={mb:.1f}",
    f"bash_s={bash_s:.3f}",
    f"python_s={py_s:.3f}",
    f"yaml_dsl_s={yaml_s:.3f}",
    f"vortex_status={vortex_status}",
    f"vortex_bin={vortex_bin}",
]
if vortex_s is not None and vortex_status == "OK":
    gate_lines.append(f"vortex_s={vortex_s:.3f}")
    gate_lines.append(f"python_over_vortex={py_s/vortex_s:.2f}x")
    gate_lines.append(f"bash_over_vortex={bash_s/vortex_s:.2f}x")
    ok_vs_py = vortex_s <= (py_s / 5.0)
    ok_vs_bash = vortex_s <= (bash_s * 1.25)
    status = "PASS" if (ok_vs_py and ok_vs_bash) else "FAIL"
    gate_lines.append(
        f"rule: vortex <= python/5 ({ok_vs_py}) AND vortex <= bash*1.25 ({ok_vs_bash}) => {status}"
    )
    gate_lines.append(f"POSTABLE_LARGE_LOG_PERF={'yes' if status == 'PASS' else 'no'}")
else:
    gate_lines.append("rule: cannot pass without a successful VORTEX_BIN run")
    gate_lines.append("POSTABLE_LARGE_LOG_PERF=no")
    gate_lines.append("THESIS_STATUS: large-log Vortex performance NOT PROVEN on this host")

vx_line = f"vortex_s: {vortex_s:.3f}" if vortex_s is not None else "vortex_s: skip"
baseline = f"""LARGE_LOG_BASELINE
log: {log}
lines: {lines}
size_MB: {mb:.1f}
bash_s: {bash_s:.3f}
python_s: {py_s:.3f}
yaml_dsl_s: {yaml_s:.3f}
python_over_bash: {py_s/bash_s:.2f}x
yaml_over_bash: {yaml_s/bash_s:.2f}x
MB_per_s: bash={mb/bash_s:.1f} python={mb/py_s:.1f} yaml={mb/yaml_s:.1f}
vortex_status: {vortex_status}
{vx_line}
{f'MB_per_s vortex={mb/vortex_s:.1f}' if vortex_s else ''}
{f'python_over_vortex: {py_s/vortex_s:.2f}x' if vortex_s else ''}
{f'bash_over_vortex: {bash_s/vortex_s:.2f}x' if vortex_s else ''}

Thesis: on large logs, Vortex is highly performant vs ad-hoc Python.
"""
(out / "LARGE_LOG_BASELINE.txt").write_text(baseline)
(out / "CLAIM_GATE_LARGE_LOG.txt").write_text("\n".join(gate_lines) + "\n")
print(baseline)
print("\n".join(gate_lines))
PY
