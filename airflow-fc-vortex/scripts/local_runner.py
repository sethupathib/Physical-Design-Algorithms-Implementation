#!/usr/bin/env python3
"""
Local workflow runner — same FC → Vortex graph as the Airflow DAGs,
without installing Airflow. Perfect for laptop demos and CI.

Implements the "excellent hacks" as plain Python so the ideas stay clear.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FC = ROOT / "mock_tools" / "fc_mock.py"
VORTEX = ROOT / "mock_tools" / "vortex_mock.py"
POLICY = ROOT / "config" / "design_health.yaml"


@dataclass
class Pool:
    """Hack #3 — license seat limiter (Airflow Pool analogue)."""

    name: str
    slots: int
    in_use: int = 0

    def acquire(self) -> bool:
        if self.in_use >= self.slots:
            return False
        self.in_use += 1
        return True

    def release(self) -> None:
        self.in_use = max(0, self.in_use - 1)


@dataclass
class RunResult:
    design: str
    corner: str
    scenario: str
    fc_rc: int
    vortex_overall: str | None
    vortex_triggered: list[str] = field(default_factory=list)
    log: str = ""
    report: str = ""
    wall_s: float = 0.0
    skipped_vortex: bool = False
    branch: str = ""
    retries: int = 0


def run_cmd(cmd: list[str], env: dict | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, env=env)


def fc_once(
    design: str,
    corner: str,
    scenario: str,
    out_dir: Path,
    work_secs: float,
    fail_license: bool = False,
) -> tuple[int, dict]:
    log = out_dir / f"{design}__{corner}.log"
    meta = out_dir / f"{design}__{corner}.fc.json"
    cmd = [
        sys.executable,
        str(FC),
        "--design",
        design,
        "--corner",
        corner,
        "--scenario",
        scenario,
        "--out-log",
        str(log),
        "--work-secs",
        str(work_secs),
        "--json-meta",
        str(meta),
    ]
    if fail_license:
        cmd.append("--fail-license")
    cp = run_cmd(cmd)
    meta_obj = {}
    if meta.exists():
        meta_obj = json.loads(meta.read_text())
    elif cp.stdout.strip():
        try:
            meta_obj = json.loads(cp.stdout.strip().splitlines()[-1])
        except json.JSONDecodeError:
            meta_obj = {"log": str(log)}
    return cp.returncode, meta_obj


def vortex_once(log: Path, out_dir: Path, fail_on: str = "fatal") -> tuple[int, dict]:
    report = out_dir / (log.stem + ".vortex.json")
    cmd = [
        sys.executable,
        str(VORTEX),
        "--policy",
        str(POLICY),
        "--log",
        str(log),
        "--json-out",
        str(report),
        "--fail-on",
        fail_on,
    ]
    cp = run_cmd(cmd)
    data = json.loads(report.read_text()) if report.exists() else {}
    return cp.returncode, data


def branch_on_severity(overall: str) -> str:
    """Hack #2 — severity router (BranchPythonOperator analogue)."""
    if overall == "fatal":
        return "page_oncall"
    if overall == "error":
        return "open_jira_timing"
    if overall == "warning":
        return "notify_slack_warn"
    return "archive_green"


def run_pipeline_one(
    design: str,
    corner: str,
    scenario: str,
    out_dir: Path,
    work_secs: float,
    pool: Pool | None,
    retries: int,
    short_circuit_fatal_fc: bool,
) -> RunResult:
    """Hack #1 chain + #5 short-circuit + #7 retry."""
    t0 = time.perf_counter()
    attempt = 0
    fc_rc = 1
    meta: dict = {}
    while attempt <= retries:
        # pool acquire
        if pool is not None:
            waited = 0.0
            while not pool.acquire():
                time.sleep(0.05)
                waited += 0.05
                if waited > 30:
                    raise RuntimeError(f"pool {pool.name} starve")
        try:
            fail_lic = attempt == 0 and scenario == "license_flaky"
            real_scenario = "timing_fail" if scenario == "license_flaky" else scenario
            fc_rc, meta = fc_once(
                design,
                corner,
                real_scenario,
                out_dir,
                work_secs,
                fail_license=fail_lic,
            )
        finally:
            if pool is not None:
                pool.release()

        if fc_rc == 3 and attempt < retries:
            attempt += 1
            time.sleep(0.1 * (2**attempt))  # backoff
            continue
        break

    log_path = Path(meta.get("log", out_dir / f"{design}__{corner}.log"))
    # Hack #5 — short-circuit Vortex if FC fatal exit
    if short_circuit_fatal_fc and fc_rc == 2:
        return RunResult(
            design=design,
            corner=corner,
            scenario=scenario,
            fc_rc=fc_rc,
            vortex_overall=None,
            log=str(log_path),
            wall_s=time.perf_counter() - t0,
            skipped_vortex=True,
            branch="fc_fatal_short_circuit",
            retries=attempt,
        )

    v_rc, vdata = vortex_once(log_path, out_dir)
    overall = vdata.get("overall", "clean")
    branch = branch_on_severity(overall)
    return RunResult(
        design=design,
        corner=corner,
        scenario=scenario,
        fc_rc=fc_rc,
        vortex_overall=overall,
        vortex_triggered=list(vdata.get("triggered", [])),
        log=str(log_path),
        report=str(out_dir / (log_path.stem + ".vortex.json")),
        wall_s=time.perf_counter() - t0,
        skipped_vortex=False,
        branch=branch,
        retries=attempt,
    )


def hack_demo_all(out_dir: Path, work_secs: float) -> dict:
    """Run a tour of the hacks; return a structured summary."""
    out_dir.mkdir(parents=True, exist_ok=True)
    events: list[dict] = []

    # --- Hack #1+#2: single FC → Vortex → branch ---
    r = run_pipeline_one(
        "block_a", "ss_0p75", "timing_fail", out_dir / "h1", work_secs, None, 0, True
    )
    events.append({"hack": "1_2_chain_branch", **r.__dict__})

    # --- Hack #3+#4: multi-corner with license pool (slots=1 vs unlimited) ---
    corners = ["ss_0p75", "tt_0p85", "ff_0p95", "ss_0p70"]
    pool = Pool("fc_licenses", slots=1)

    def one(c: str, pooled: bool) -> RunResult:
        return run_pipeline_one(
            "block_b",
            c,
            "drc_fail" if c.endswith("70") else "clean",
            out_dir / ("h3_pooled" if pooled else "h3_unlimited"),
            work_secs,
            pool if pooled else None,
            0,
            True,
        )

    t_pool = time.perf_counter()
    with ThreadPoolExecutor(max_workers=4) as ex:
        futs = [ex.submit(one, c, True) for c in corners]
        pooled_results = [f.result() for f in as_completed(futs)]
    pooled_wall = time.perf_counter() - t_pool

    t_un = time.perf_counter()
    with ThreadPoolExecutor(max_workers=4) as ex:
        futs = [ex.submit(one, c, False) for c in corners]
        unlimited_results = [f.result() for f in as_completed(futs)]
    unlimited_wall = time.perf_counter() - t_un

    events.append(
        {
            "hack": "3_4_pool_vs_unlimited",
            "corners": corners,
            "pool_slots": 1,
            "pooled_wall_s": round(pooled_wall, 3),
            "unlimited_wall_s": round(unlimited_wall, 3),
            "pooled_peak_meaning": "max 1 FC at a time (license safe)",
            "unlimited_peak_meaning": "4 FC at once (license thrash risk)",
            "pooled_branches": sorted({x.branch for x in pooled_results}),
            "unlimited_ok": all(x.fc_rc != 3 for x in unlimited_results),
        }
    )

    # --- Hack #5: short-circuit on FC fatal ---
    r5 = run_pipeline_one(
        "block_c", "ss_0p75", "fatal", out_dir / "h5", work_secs, None, 0, True
    )
    events.append({"hack": "5_short_circuit", **r5.__dict__})

    # --- Hack #7: retry on license flake ---
    r7 = run_pipeline_one(
        "block_d",
        "ss_0p75",
        "license_flaky",
        out_dir / "h7",
        work_secs,
        None,
        retries=2,
        short_circuit_fatal_fc=True,
    )
    events.append({"hack": "7_retry_backoff", **r7.__dict__})

    # --- Hack #8: YAML workflow factory (read config) ---
    wf = json.loads((ROOT / "config" / "workflows.json").read_text())
    factory_runs = []
    for job in wf["jobs"]:
        rr = run_pipeline_one(
            job["design"],
            job["corner"],
            job["scenario"],
            out_dir / "h8_factory",
            work_secs,
            None,
            job.get("retries", 0),
            True,
        )
        factory_runs.append(rr.__dict__)
    events.append({"hack": "8_yaml_factory", "jobs": factory_runs})

    summary = {
        "utc": datetime.now(timezone.utc).isoformat(),
        "root": str(ROOT),
        "events": events,
        "hacks_covered": [
            "1 FC→Vortex XCom/path chain",
            "2 severity branch",
            "3 license pool",
            "4 multi-corner fanout",
            "5 short-circuit",
            "7 retry/backoff",
            "8 workflow-as-YAML factory",
        ],
    }
    (out_dir / "runner_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "results" / "run"))
    ap.add_argument("--work-secs", type=float, default=0.25)
    args = ap.parse_args()
    summary = hack_demo_all(Path(args.out), args.work_secs)
    print(json.dumps({"ok": True, "out": args.out, "n_events": len(summary["events"])}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
