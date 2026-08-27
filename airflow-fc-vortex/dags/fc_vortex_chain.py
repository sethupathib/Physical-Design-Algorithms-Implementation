"""
DAG: fc_vortex_chain  — Hacks #1, #2, #5, #7

Drop this file into $AIRFLOW_HOME/dags/ (Airflow 2.7+).
Uses mock_tools by default; point env vars at real binaries for production:

  FC_BIN=/path/to/fc_shell
  VORTEX_BIN=/path/to/vortex
  VORTEX_POLICY=/path/to/design_health.yaml
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
    from airflow.operators.empty import EmptyOperator
    from airflow.operators.trigger_dagrun import TriggerDagRunOperator
    from airflow.utils.trigger_rule import TriggerRule
except ImportError as e:  # pragma: no cover
    raise ImportError(
        "Install apache-airflow to load this DAG, or use scripts/local_runner.py for the laptop demo."
    ) from e

ROOT = Path(os.environ.get("AFV_ROOT", Path(__file__).resolve().parents[1]))
FC_MOCK = ROOT / "mock_tools" / "fc_mock.py"
VORTEX_MOCK = ROOT / "mock_tools" / "vortex_mock.py"
POLICY = Path(os.environ.get("VORTEX_POLICY", ROOT / "config" / "design_health.yaml"))
WORK = Path(os.environ.get("AFV_WORK", "/tmp/airflow_fc_vortex"))

default_args = {
    "owner": "methodology",
    "retries": int(os.environ.get("FC_RETRIES", "2")),  # Hack #7
    "retry_delay": timedelta(seconds=10),
    "execution_timeout": timedelta(hours=12),
}

with DAG(
    dag_id="fc_vortex_chain",
    description="FC → Vortex → severity branch (hacks 1/2/5/7)",
    start_date=datetime(2024, 1, 1),
    schedule=None,  # manual / API trigger (Hack #10 params)
    catchup=False,
    tags=["pd", "fc", "vortex", "hack"],
    default_args=default_args,
    params={
        "design": "block_a",
        "corner": "ss_0p75v_125c",
        "scenario": "timing_fail",  # mock only
    },
) as dag:

    @task(pool="fc_licenses")  # Hack #3 — create pool in Airflow UI: slots = license seats
    def run_fc(**context) -> dict:
        p = context["params"]
        WORK.mkdir(parents=True, exist_ok=True)
        log = WORK / f"{p['design']}__{p['corner']}.log"
        fc_bin = os.environ.get("FC_BIN")
        if fc_bin:
            # Production sketch — adapt flags to your wrap script
            cmd = [fc_bin, "-f", str(p.get("tcl", "run.tcl"))]
            cp = subprocess.run(cmd, capture_output=True, text=True)
            log.write_text(cp.stdout + "\n" + cp.stderr)
            return {"log": str(log), "fc_rc": cp.returncode, "design": p["design"]}
        cmd = [
            "python3",
            str(FC_MOCK),
            "--design",
            p["design"],
            "--corner",
            p["corner"],
            "--scenario",
            p["scenario"],
            "--out-log",
            str(log),
        ]
        cp = subprocess.run(cmd, capture_output=True, text=True)
        return {"log": str(log), "fc_rc": cp.returncode, "design": p["design"]}

    @task.short_circuit  # Hack #5 — skip downstream if FC hard-fatal
    def fc_ok(meta: dict) -> bool:
        return meta.get("fc_rc", 1) != 2

    @task
    def run_vortex(meta: dict) -> dict:
        log = meta["log"]
        out = Path(log).with_suffix(".vortex.json")
        vortex_bin = os.environ.get("VORTEX_BIN")
        if vortex_bin:
            cmd = [
                vortex_bin,
                "--search_by_rule",
                "--policy",
                str(POLICY),
                "--log",
                log,
            ]
            cp = subprocess.run(cmd, capture_output=True, text=True)
            out.write_text(cp.stdout)
            # best-effort parse
            overall = "error" if cp.returncode else "clean"
            return {"overall": overall, "log": log, "report": str(out)}
        cmd = [
            "python3",
            str(VORTEX_MOCK),
            "--policy",
            str(POLICY),
            "--log",
            log,
            "--json-out",
            str(out),
            "--fail-on",
            "fatal",
        ]
        subprocess.run(cmd, check=False)
        data = json.loads(out.read_text())
        return {"overall": data["overall"], "log": log, "report": str(out), "triggered": data["triggered"]}

    @task.branch  # Hack #2
    def route(report: dict) -> str:
        o = report.get("overall", "clean")
        return {
            "fatal": "page_oncall",
            "error": "open_jira_timing",
            "warning": "notify_slack_warn",
            "clean": "archive_green",
        }.get(o, "archive_green")

    page = EmptyOperator(task_id="page_oncall")
    jira = EmptyOperator(task_id="open_jira_timing")
    slack = EmptyOperator(task_id="notify_slack_warn")
    green = EmptyOperator(task_id="archive_green")
    done = EmptyOperator(task_id="done", trigger_rule=TriggerRule.NONE_FAILED_MIN_ONE_SUCCESS)

    meta = run_fc()
    ok = fc_ok(meta)
    report = run_vortex(meta)
    branch = route(report)
    ok >> report
    branch >> [page, jira, slack, green] >> done
