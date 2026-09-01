# Vortex-style YAML DSL vs Bash / Python / Perl ad-hoc

**1:1 comparison project:** policy-as-code (`search_by_rule` YAML) versus ad-hoc scripting.

| Artifact | Path |
|---|---|
| Shared policy (7 rules) | [`policy/design_health.yaml`](./policy/design_health.yaml) |
| Ad-hoc Bash / Python / Perl | [`adhoc/`](./adhoc/) |
| Reference YAML runner | [`runners/yaml_dsl_runner.py`](./runners/yaml_dsl_runner.py) |
| Compare harness | [`examples/compare_all.sh`](./examples/compare_all.sh) |
| **Large-log thesis** | [`scripts/run_large_log_thesis.sh`](./scripts/run_large_log_thesis.sh) |
| Measured SUMMARY | [`results/SUMMARY.txt`](./results/SUMMARY.txt) |
| Large-log baseline | [`results/LARGE_LOG_BASELINE.txt`](./results/LARGE_LOG_BASELINE.txt) |
| White paper | [`WHITEOBER.md`](./WHITEOBER.md) · [`docs/vortex_vs_adhoc_whitepaper.pdf`](./docs/vortex_vs_adhoc_whitepaper.pdf) |

## The real thesis (large logs)

**Claim:** on ~GB PD–signoff logs, the **Vortex product binary** (`--search`) is highly performant versus ad-hoc Python.

Measured with Vortex **v25.1** on this host (cold cache, `drop_caches`):

| Workload | Engine | Seconds | vs Python |
|---|---|---:|---:|
| ~1.08 GB, pattern `ERROR` | `vortex --search` | 1.42 | **2.4×** faster |
| ~1.08 GB, pattern `ERROR` | Python `re` one-pass | 3.41 | 1.0× |
| ~1.08 GB, **7 patterns** | 7× `vortex --search` | **5.65** | **~26×** faster |
| ~1.08 GB, **7 rules** | Python ad-hoc | 145.4 | 1.0× |

`CLAIM_GATE_LARGE_LOG`: **PASS** on the primary multi-pattern claim (`POSTABLE_LARGE_LOG_PERF=yes`).

```bash
# Install Vortex eval package (not shipped in git), then:
export VORTEX_BIN=/path/to/vortex-v25.1/bin/vortex
LINES=35000000 ./scripts/run_large_log_thesis.sh
cat results/LARGE_LOG_BASELINE.txt results/CLAIM_GATE_LARGE_LOG.txt
```

### Honest caveat — `--search_by_rule`

On a ~309 MB synthetic log, `vortex … --search_by_rule` with the 7-rule YAML took **~201 s** here. That is **not** the fast path. Cite **`--search`** (and multi `--search`) for large-log performance. Policy-as-code UX (`search_by_rule`) is still the right *methodology* surface — performance leadership on huge logs is the engine’s `--search` path today.

---

## Quick start (on your machine)

```bash
cd vortex-vs-adhoc

# dependencies (YAML runner + optional PDF build)
pip install -r requirements.txt
# or minimal:  pip install pyyaml
# or system:   apt install python3-yaml

# small methodology compare (~6MB)
./examples/compare_all.sh
cat results/SUMMARY.txt

# large-log thesis (needs VORTEX_BIN to PASS CLAIM_GATE)
LINES=10000000 ./scripts/run_large_log_thesis.sh
```

Optional — measure your Vortex binary on the same log/policy:

```bash
export VORTEX_BIN=/path/to/vortex
./examples/compare_all.sh
LINES=10000000 ./scripts/run_large_log_thesis.sh
```

---

## Headline numbers (small methodology run)

Synthetic log: **200,000 lines (~5.9 MB)**, seed fixed, same file for every engine.

### Lines of code (non-blank, non-comment)

| Artifact | LOC | Role |
|---|---:|---|
| **YAML policy** | **51** | Intent — what to find |
| Bash ad-hoc | 96 | Implementation embeds policy |
| Python ad-hoc | 123 | Same |
| Perl ad-hoc | 69 | Same |
| YAML reference runner | 104 | Engine glue (not edited when rules change) |

**Bash / YAML LOC ratio ≈ 1.88×** (implementation vs intent for the same 7 rules).

### Correctness

All four engines **MATCH** on triggered rules and **identical hit counts** for all 7 rules on the synthetic log.

### Wall time (same small log — illustrative)

| Engine | Seconds |
|---|---:|
| bash (`grep`) | ~0.23 |
| yaml_dsl reference | ~0.96 |
| python ad-hoc | ~0.98 |
| perl ad-hoc | ~1.03 |
| vortex | set `VORTEX_BIN` |

On a **small** synthetic file, `grep` is often fastest. That does **not** overturn the thesis — see **The real thesis (large logs)** above.

---

## Dimension table (methodology)

| Dimension | YAML DSL (`search_by_rule`) | Ad-hoc Bash / Grep / Python / Perl |
|---|---|---|
| **LOC for 7 rules** | ~51 (policy only) | ~69–123 (policy buried in code) |
| **Readability** | Declarative list — intent is obvious | Procedural — must parse regex + control flow |
| **Edit a threshold** | Change one YAML field (~seconds) | Find block(s), edit, retest (minutes) |
| **Add a rule** | New named block | Copy/paste procedural block + test |
| **Who can write?** | Anyone who can read a list | Needs shell/Python/Perl + regex depth |
| **Who can review?** | FE / BE / CAD / methodology / leads | Only language experts |
| **Team alignment** | One shared policy file | Fragmentation — personal scripts |
| **Output** | Structured severities, counts, context | Raw / reinvented JSON every time |
| **Audit trail** | Native in Vortex product | DIY |
| **Philosophy** | **Intent** (what) | **Implementation** (how) |

---

## Layout

```
vortex-vs-adhoc/
├── README.md
├── WHITEOBER.md
├── policy/design_health.yaml
├── runners/yaml_dsl_runner.py
├── adhoc/
├── scripts/gen_synthetic_log.py
├── scripts/run_large_log_thesis.sh
├── examples/compare_all.sh
├── results/          # SUMMARY + LARGE_LOG_BASELINE (fat logs gitignored)
└── docs/
```

---

## What this does *not* claim

- That Bash is always slower than Vortex on tiny files.  
- That the reference YAML runner **is** Vortex.  
- That Vortex beat Python on huge logs **in this environment** (binary not present — `POSTABLE_LARGE_LOG_PERF=no`).  
- Customer QoR or tapeout outcomes.

It **does** claim: for the same 7 rules, policy-as-code is shorter and team-aligning; and on a ~309 MB synthetic log, ad-hoc Python is already ~21× slower than bash — the performance gap Vortex is meant to close once `VORTEX_BIN` is measured.
