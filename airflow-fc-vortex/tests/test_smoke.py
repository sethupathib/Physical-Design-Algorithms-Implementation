#!/usr/bin/env python3
"""Smoke tests for mocks + local_runner (no Airflow required)."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_fc_and_vortex_chain():
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        log = td / "t.log"
        subprocess.check_call(
            [
                sys.executable,
                str(ROOT / "mock_tools" / "fc_mock.py"),
                "--scenario",
                "timing_fail",
                "--out-log",
                str(log),
                "--work-secs",
                "0.05",
            ]
        )
        report = td / "t.vortex.json"
        cp = subprocess.run(
            [
                sys.executable,
                str(ROOT / "mock_tools" / "vortex_mock.py"),
                "--policy",
                str(ROOT / "config" / "design_health.yaml"),
                "--log",
                str(log),
                "--json-out",
                str(report),
            ],
            capture_output=True,
            text=True,
        )
        data = json.loads(report.read_text())
        assert data["overall"] in ("error", "warning", "fatal", "clean")
        assert "setup_violation" in data["triggered"] or data["overall"] != "clean"
        print("test_fc_and_vortex_chain OK", data["overall"], data["triggered"])


def test_local_runner():
    with tempfile.TemporaryDirectory() as td:
        cp = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts" / "local_runner.py"),
                "--out",
                td,
                "--work-secs",
                "0.05",
            ],
            capture_output=True,
            text=True,
        )
        assert cp.returncode == 0, cp.stderr
        summary = json.loads((Path(td) / "runner_summary.json").read_text())
        hacks = {e["hack"] for e in summary["events"]}
        assert "1_2_chain_branch" in hacks
        assert "5_short_circuit" in hacks
        print("test_local_runner OK", sorted(hacks))


if __name__ == "__main__":
    test_fc_and_vortex_chain()
    test_local_runner()
    print("ALL PASS")
