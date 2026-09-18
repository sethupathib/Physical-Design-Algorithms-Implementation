#!/usr/bin/env python3
"""Render templatized EDA DAGs from configs/designs.yaml → generated/*.yml."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import yaml
from jinja2 import Environment, FileSystemLoader, StrictUndefined

ROOT = Path(__file__).resolve().parents[1]


def slug(s: str) -> str:
    s = s.strip().lower()
    s = re.sub(r"[^a-z0-9]+", "_", s)
    return s.strip("_")


def dag_id_for(design: str, stage: str) -> str:
    return f"eda__{slug(design)}__{slug(stage)}"


def load_designs(path: Path) -> tuple[dict, list[dict]]:
    data = yaml.safe_load(path.read_text())
    defaults = data.get("defaults") or {}
    designs = data.get("designs") or []
    if not isinstance(designs, list) or not designs:
        raise SystemExit(f"no designs listed in {path}")
    return defaults, designs


def render_one(env: Environment, defaults: dict, row: dict) -> tuple[str, str]:
    design = row["design"]
    stage = row["stage"]
    dag_id = dag_id_for(design, stage)
    ctx = {
        "dag_id": dag_id,
        "design": design,
        "stage": stage,
        "owner": row.get("owner", defaults.get("owner", "cad_infra")),
        "retries": int(row.get("retries", defaults.get("retries", 1))),
        "tool_cmd": row["tool_cmd"],
        "log_src": row["log_src"],
        "log_dst": row["log_dst"],
        "enable_vortex": bool(row.get("enable_vortex", False)),
        "vortex_bin": row.get("vortex_bin", defaults.get("vortex_bin", "vortex")),
        "rules_yaml": row.get("rules_yaml", defaults.get("rules_yaml", "rules.yaml")),
    }
    text = env.get_template("eda_flow.yml.j2").render(**ctx)
    return dag_id, text


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--designs",
        type=Path,
        default=ROOT / "configs" / "designs.yaml",
    )
    p.add_argument(
        "--template-dir",
        type=Path,
        default=ROOT / "templates",
    )
    p.add_argument(
        "--out-dir",
        type=Path,
        default=ROOT / "generated",
    )
    p.add_argument(
        "--also-dags",
        action="store_true",
        help="Also write YAML into dags/ for Airflow pickup",
    )
    args = p.parse_args(argv)

    defaults, designs = load_designs(args.designs)
    env = Environment(
        loader=FileSystemLoader(str(args.template_dir)),
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
    )

    args.out_dir.mkdir(parents=True, exist_ok=True)
    # Clean previous generated YAML (keep .gitkeep)
    for old in args.out_dir.glob("eda__*.yml"):
        old.unlink()

    dags_dir = ROOT / "dags"
    if args.also_dags:
        dags_dir.mkdir(parents=True, exist_ok=True)
        for old in dags_dir.glob("eda__*.yml"):
            old.unlink()

    written: list[str] = []
    for row in designs:
        dag_id, text = render_one(env, defaults, row)
        out = args.out_dir / f"{dag_id}.yml"
        out.write_text(text)
        written.append(dag_id)
        print(f"wrote={out}")
        if args.also_dags:
            dest = dags_dir / f"{dag_id}.yml"
            dest.write_text(text)
            print(f"wrote={dest}")

    manifest = args.out_dir / "MANIFEST.txt"
    manifest.write_text("\n".join(written) + "\n")
    print(f"count={len(written)}")
    print(f"manifest={manifest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
