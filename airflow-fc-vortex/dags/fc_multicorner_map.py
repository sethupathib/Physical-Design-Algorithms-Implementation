"""
DAG: fc_multicorner_map  — Hack #4 dynamic task mapping + Hack #3 pool

One mapped FC→Vortex task per corner. Add a corner = change params, not code.
"""
from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

try:
    from airflow import DAG
    from airflow.decorators import task
except ImportError as e:  # pragma: no cover
    raise ImportError("Need apache-airflow, or use scripts/local_runner.py") from e

ROOT = Path(os.environ.get("AFV_ROOT", Path(__file__).resolve().parents[1]))
FC_MOCK = ROOT / "mock_tools" / "fc_mock.py"
VORTEX_MOCK = ROOT / "mock_tools" / "vortex_mock.py"
POLICY = Path(os.environ.get("VORTEX_POLICY", ROOT / "config" / "design_health.yaml"))
WORK = Path(os.environ.get("AFV_WORK", "/tmp/airflow_fc_vortex_map"))

with DAG(
    dag_id="fc_multicorner_map",
    start_date=datetime(2024, 1, 1),
    schedule=None,
    catchup=False,
    tags=["pd", "fc", "vortex", "mapping"],
    default_args={"owner": "cad", "retries": 1, "retry_delay": timedelta(seconds=15)},
    params={
        "design": "cpu_top",
        "corners": ["ss_0p75", "tt_0p85", "ff_0p95", "ss_0p70"],
        "scenario_by_corner": {"ss_0p70": "drc_fail"},
    },
) as dag:

    @task
    def expand_corners(**context) -> list[dict]:
        p = context["params"]
        default_scenario = p.get("scenario", "clean")
        override = p.get("scenario_by_corner") or {}
        return [
            {
                "design": p["design"],
                "corner": c,
                "scenario": override.get(c, default_scenario),
            }
            for c in p["corners"]
        ]

    @task(pool="fc_licenses", max_active_tis_per_dag=4)
    def fc_and_vortex(job: dict) -> dict:
        WORK.mkdir(parents=True, exist_ok=True)
        log = WORK / f"{job['design']}__{job['corner']}.log"
        report = WORK / f"{job['design']}__{job['corner']}.vortex.json"
        subprocess.run(
            [
                "python3",
                str(FC_MOCK),
                "--design",
                job["design"],
                "--corner",
                job["corner"],
                "--scenario",
                job["scenario"],
                "--out-log",
                str(log),
            ],
            check=False,
        )
        subprocess.run(
            [
                "python3",
                str(VORTEX_MOCK),
                "--policy",
                str(POLICY),
                "--log",
                str(log),
                "--json-out",
                str(report),
            ],
            check=False,
        )
        data = json.loads(report.read_text())
        return {
            "corner": job["corner"],
            "overall": data["overall"],
            "triggered": data["triggered"],
            "log": str(log),
        }

    @task
    def summarize(rows: list[dict]) -> dict:
        bad = [r for r in rows if r["overall"] in ("error", "fatal")]
        return {"n": len(rows), "bad": bad, "all_overall": [r["overall"] for r in rows]}

    jobs = expand_corners()
    results = fc_and_vortex.expand(job=jobs)  # Hack #4
    summarize(results)
