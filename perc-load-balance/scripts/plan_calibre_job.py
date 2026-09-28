#!/usr/bin/env python3
"""Plan Calibre DRC/PERC LSF launches under slot + license constraints.

Critical thesis
---------------
Distributed DRC/PERC load balancing fails in practice when engineers size only
CPU/memory and ignore:

1. License tokens (master + MT/remote consumption)
2. Per-slot resource semantics (1 LSF slot == 1 core; hosts×turbo must fit
   max_slots_per_user; mem select does not reserve RAM)

This planner takes a farm profile + job intent and emits a *feasible* plan
or an explicit BLOCKED reason (never silently over-request).
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]


@dataclass
class Plan:
    status: str  # FEASIBLE | BLOCKED | REDUCED
    flow: str
    queue: str
    master_slots: int
    remote_slaves: int
    turbo: int
    total_compute_slots: int  # slaves * turbo (children)
    total_slots_charged: int  # master + compute (planning view)
    mem_gb_per_slave: int
    enable_hyperflex: bool
    licenses_needed: dict[str, int]
    licenses_available: dict[str, int]
    blockers: list[str]
    warnings: list[str]
    bsub_master: str
    calibre_args: str
    rationale: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def load_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text())
    if not isinstance(data, dict):
        raise SystemExit(f"invalid yaml: {path}")
    return data


def _license_need(farm: dict, slaves: int, turbo: int, flow: str) -> dict[str, int]:
    lic = farm["licenses"]
    base = lic["calibre_base"]
    mt = lic["calibre_mt"]
    # Allow per-flow feature override
    feature = base.get("feature_by_flow", {}).get(flow, base["feature"])
    if flow == "perc" and "feature_perc" in base:
        feature = base["feature_perc"]
    need = {
        feature: int(base["tokens_per_master"]),
        mt["feature"]: int(mt.get("tokens_per_remote_slave", 0)) * slaves
        + int(mt.get("tokens_per_turbo_thread", 0)) * slaves * turbo,
    }
    return {k: v for k, v in need.items() if v > 0}


def _license_avail(farm: dict, flow: str) -> dict[str, int]:
    lic = farm["licenses"]
    base = lic["calibre_base"]
    feature = base.get("feature_by_flow", {}).get(flow, base["feature"])
    if flow == "perc" and "feature_perc" in base:
        feature = base["feature_perc"]
    return {
        feature: int(base["tokens_available"]),
        lic["calibre_mt"]["feature"]: int(lic["calibre_mt"]["tokens_available"]),
    }


def _fits_licenses(need: dict[str, int], avail: dict[str, int], headroom: int) -> list[str]:
    blockers = []
    for feat, n in need.items():
        a = avail.get(feat, 0)
        if n + headroom > a:
            blockers.append(
                f"license:{feat} need={n}+headroom={headroom} available={a}"
            )
    return blockers


def plan_job(farm: dict, job: dict) -> Plan:
    defaults = farm.get("defaults", {})
    queue = job.get("queue", defaults.get("queue", "bat.l"))
    qconf = farm["farm"]["queues"][queue]
    max_slots = min(
        int(farm["farm"]["max_slots_per_user"]),
        int(qconf.get("max_slots_per_user", farm["farm"]["max_slots_per_user"])),
    )
    master = int(defaults.get("master_slots", 1))
    slot_headroom = int(defaults.get("slot_headroom", 0))
    lic_headroom = int(defaults.get("license_headroom", 0))

    want_slaves = int(job["want_remote_slaves"])
    want_turbo = int(job["want_turbo"])
    mem = int(job.get("mem_gb_per_slave", defaults.get("mem_gb_per_slave", 64)))
    hyper = bool(job.get("enable_hyperflex", False))
    flow = str(job.get("flow", "drc"))

    max_dram = int(qconf.get("max_dram_gb_per_job", 250))
    warnings: list[str] = []
    rationale: list[str] = []

    if hyper:
        warnings.append(
            "hyperflex/hyper enabled: TSRI guide warns LSF may kill jobs that "
            "overrun memory; prefer disable on large layouts until measured."
        )
    if mem > max_dram:
        warnings.append(
            f"mem_gb_per_slave={mem} exceeds queue max_dram_gb_per_job={max_dram}"
        )
    if not farm["farm"].get("mem_select_reserves", False):
        warnings.append(
            "LSF -R select[mem>N] does NOT reserve memory (TSRI guide); "
            "size slaves from bacct/rep, expect contention."
        )

    turbo_min = int(defaults.get("turbo_min", 1))
    turbo_max = int(defaults.get("turbo_max", 64))
    if want_turbo < turbo_min or want_turbo > turbo_max:
        warnings.append(
            f"want_turbo={want_turbo} outside suggested band "
            f"[{turbo_min},{turbo_max}] (guide mmDRC suggests 4–8)."
        )

    avail = _license_avail(farm, flow)
    # Search feasible (slaves, turbo) from want downward — prefer keeping turbo,
    # reducing slaves first (common when licenses bind).
    candidates: list[tuple[int, int]] = []
    for slaves in range(want_slaves, 0, -1):
        for turbo in range(want_turbo, 0, -1):
            candidates.append((slaves, turbo))

    chosen = None
    last_blockers: list[str] = []
    for slaves, turbo in candidates:
        compute = slaves * turbo
        charged = master + compute
        blockers = []
        if charged + slot_headroom > max_slots:
            blockers.append(
                f"slots: master({master})+slaves×turbo({slaves}×{turbo}={compute})"
                f"+headroom({slot_headroom})={charged + slot_headroom} > max={max_slots}"
            )
        need = _license_need(farm, slaves, turbo, flow)
        blockers.extend(_fits_licenses(need, avail, lic_headroom))
        if not blockers:
            chosen = (slaves, turbo, need, charged, compute)
            break
        last_blockers = blockers

    if chosen is None:
        return Plan(
            status="BLOCKED",
            flow=flow,
            queue=queue,
            master_slots=master,
            remote_slaves=0,
            turbo=0,
            total_compute_slots=0,
            total_slots_charged=master,
            mem_gb_per_slave=mem,
            enable_hyperflex=hyper,
            licenses_needed=_license_need(farm, want_slaves, want_turbo, flow),
            licenses_available=avail,
            blockers=last_blockers
            or ["no feasible (slaves,turbo) under slot+license caps"],
            warnings=warnings,
            bsub_master="",
            calibre_args="",
            rationale=[
                "Refused to emit an over-capacity launch. "
                "Increase tokens, free slots, or lower want_*."
            ],
        )

    slaves, turbo, need, charged, compute = chosen
    status = "FEASIBLE"
    if slaves != want_slaves or turbo != want_turbo:
        status = "REDUCED"
        rationale.append(
            f"Reduced from want slaves={want_slaves} turbo={want_turbo} "
            f"to slaves={slaves} turbo={turbo} to satisfy caps."
        )
    else:
        rationale.append("Requested parallelism fits slot and license caps.")

    rationale.append(
        f"Slot math (TSRI semantics): 1 slot=1 core; "
        f"children use {slaves}×{turbo}={compute} slots; "
        f"master planning charge={master}; total={charged} "
        f"(max_slots_per_user={max_slots}, headroom={slot_headroom})."
    )
    rationale.append(
        "Guide: for remote Calibre, master often needs only 1 core; "
        "children are LSF-dispatched."
    )

    # Launch recipes — placeholders; sites wire mmDRC/GUI or -remote formats.
    if flow == "perc":
        tool_flags = f"-perc -hier -turbo {turbo}"
    else:
        tool_flags = f"-drc -hier -turbo {turbo}"

    calibre_args = (
        f"calibre {tool_flags} {job.get('ruledeck', 'RULE.rule')}"
        + (" -hyper" if hyper else "")
    )
    # Master bsub: 1 slot; remote slaves configured inside Calibre/LSF form /
    # remote.cfg with Concurrent Jobs = slaves, turbo as above.
    bsub_master = (
        f"module load calibre; "
        f"bsub -q {queue} -n {master} "
        f"-R \"select[mem>{mem}]\" "
        f"# then configure remote: ConcurrentJobs={slaves}, "
        f"turbo/CPU-per-host={turbo}, Limit Jobs on"
    )

    return Plan(
        status=status,
        flow=flow,
        queue=queue,
        master_slots=master,
        remote_slaves=slaves,
        turbo=turbo,
        total_compute_slots=compute,
        total_slots_charged=charged,
        mem_gb_per_slave=mem,
        enable_hyperflex=hyper,
        licenses_needed=need,
        licenses_available=avail,
        blockers=[],
        warnings=warnings,
        bsub_master=bsub_master,
        calibre_args=calibre_args,
        rationale=rationale,
    )


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--farm",
        type=Path,
        default=ROOT / "configs" / "farm.yaml",
    )
    p.add_argument(
        "--job",
        type=Path,
        required=True,
        help="Job YAML (see configs/job_*_example.yaml)",
    )
    p.add_argument("--json", action="store_true", help="Emit JSON only")
    p.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Write plan JSON to this path",
    )
    args = p.parse_args(argv)

    farm = load_yaml(args.farm)
    job_doc = load_yaml(args.job)
    job = job_doc.get("job", job_doc)
    plan = plan_job(farm, job)
    payload = plan.to_dict()
    payload["job_name"] = job.get("name")
    payload["design"] = job.get("design")

    text = json.dumps(payload, indent=2)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text + "\n")
    if args.json:
        print(text)
    else:
        print(f"status={plan.status}")
        print(f"flow={plan.flow} queue={plan.queue}")
        print(
            f"plan: master_slots={plan.master_slots} "
            f"remote_slaves={plan.remote_slaves} turbo={plan.turbo} "
            f"compute_slots={plan.total_compute_slots} "
            f"charged_slots={plan.total_slots_charged}"
        )
        print(f"licenses_needed={plan.licenses_needed}")
        print(f"licenses_available={plan.licenses_available}")
        if plan.blockers:
            print("blockers:")
            for b in plan.blockers:
                print(f"  - {b}")
        if plan.warnings:
            print("warnings:")
            for w in plan.warnings:
                print(f"  - {w}")
        print("rationale:")
        for r in plan.rationale:
            print(f"  - {r}")
        if plan.bsub_master:
            print(f"bsub_master={plan.bsub_master}")
            print(f"calibre_args={plan.calibre_args}")
    return 0 if plan.status in ("FEASIBLE", "REDUCED") else 2


if __name__ == "__main__":
    sys.exit(main())
