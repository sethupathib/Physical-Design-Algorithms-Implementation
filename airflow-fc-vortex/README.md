# Airflow hacks for Fusion Compiler + Vortex

**Simple idea:** after FC runs, automatically run Vortex, then **route** on severity — with license pools, multi-corner fan-out, retries, and workflow-as-data.

| Artifact | Path |
|---|---|
| Hack cheat sheet | [`HACKS.md`](./HACKS.md) |
| Laptop demo (no Airflow) | [`scripts/local_runner.py`](./scripts/local_runner.py) |
| Drop-in DAGs | [`dags/`](./dags/) |
| Mock FC / Vortex | [`mock_tools/`](./mock_tools/) |
| Shared policy | [`config/design_health.yaml`](./config/design_health.yaml) |
| Compare + numbers | [`examples/compare_all.sh`](./examples/compare_all.sh) → [`results/SUMMARY.txt`](./results/SUMMARY.txt) |
| White paper | [`WHITEPAPER.md`](./WHITEPAPER.md) |
| Defend Q&A | [`DEFEND_QA.md`](./DEFEND_QA.md) |

Unlike AutoFDO, you can **run this on a laptop in one minute** — no kernel rebuild, no PMU, no Synopsys license.

---

## Quick start (your machine)

```bash
cd airflow-fc-vortex
pip install pyyaml

# prove the hacks without installing Airflow
python3 scripts/local_runner.py
./examples/compare_all.sh
cat results/SUMMARY.txt

# unit smoke
python3 tests/test_smoke.py
```

### Optional — real Airflow

```bash
# create pool in UI or CLI: fc_licenses  (slots = number of FC seats)
export AFV_ROOT=$PWD
cp dags/*.py $AIRFLOW_HOME/dags/
# optional production binaries:
export FC_BIN=/path/to/fc_shell
export VORTEX_BIN=/path/to/vortex
export VORTEX_POLICY=$PWD/config/design_health.yaml
airflow dags trigger fc_vortex_chain --conf '{"design":"block_a","corner":"ss_0p75"}'
```

---

## The 10 hacks (plain English)

1. **Chain** — FC finishes → Vortex reads the log path  
2. **Branch** — fatal / error / warning / clean take different paths  
3. **Pool** — never launch more FC jobs than license seats  
4. **Map corners** — one task per PVT corner from a list  
5. **Short-circuit** — FC already dead? skip Vortex  
6. **Dataset** — log lands on disk → Vortex DAG wakes up  
7. **Retry** — license checkout flake? backoff and retry  
8. **Factory** — jobs live in `workflows.json`, not tribal Bash  
9. **SLA** — overrun the night window → alert  
10. **Params** — trigger from UI with design/corner fields  

Full table: [`HACKS.md`](./HACKS.md).

---

## Headline numbers (this run)

| Metric | Value |
|---|---|
| Ad-hoc Bash LOC | ~30–40 |
| Airflow chain DAG LOC | ~130 |
| Policy YAML LOC | ~42 |
| Job list JSON LOC | ~9 |
| Naive grep false positives on clean corners | **>0** (demo) |
| Structured `overall` clean → ARCHIVE | correct |
| Short-circuit on FC fatal | `skipped_vortex=True` |
| Pool slots=1 vs unlimited | serialized vs parallel (license-safe) |

**Killer insight:** grepping Vortex JSON for rule *names* false-fires on clean logs (names always present). Airflow branches on **`overall`** — same lesson as Vortex policy-as-code.

---

## How this optimizes real workflows

| Pain | Hack |
|---|---|
| “Did anyone Vortex last night’s log?” | #1 chain + #6 dataset |
| 40 FC jobs vs 8 licenses | #3 pool |
| Copy-paste for each corner | #4 mapping / #8 JSON |
| On-call at 3am for FATAL | #2 branch → page |
| Cron Bash nobody owns | DAGs + policy YAML |

---

## Layout

```
airflow-fc-vortex/
├── HACKS.md                 # one-page cheat sheet
├── README.md
├── WHITEPAPER.md
├── DEFEND_QA.md
├── config/design_health.yaml
├── config/workflows.json
├── mock_tools/fc_mock.py
├── mock_tools/vortex_mock.py
├── scripts/local_runner.py  # no Airflow needed
├── dags/*.py                # drop into Airflow
├── adhoc/bash_fc_vortex_pipeline.sh
├── examples/compare_all.sh
└── results/
```

---

## What this does *not* claim

- Faster Synopsys place-and-route algorithms  
- AutoFDO / kernel tuning (see sibling `autofdo-fc-runtime/`)  
- That the mocks *are* FC or Vortex  

It **does** claim: these Airflow patterns give methodology a **shared, reviewable control plane** for FC→Vortex, with measurable demos you can run tonight.
