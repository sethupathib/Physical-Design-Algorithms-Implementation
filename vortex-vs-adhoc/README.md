# Vortex-style YAML DSL vs Bash / Python / Perl ad-hoc

**1:1 comparison project:** policy-as-code (`search_by_rule` YAML) versus ad-hoc scripting.

| Artifact | Path |
|---|---|
| Shared policy (7 rules) | [`policy/design_health.yaml`](./policy/design_health.yaml) |
| Ad-hoc Bash / Python / Perl | [`adhoc/`](./adhoc/) |
| Reference YAML runner | [`runners/yaml_dsl_runner.py`](./runners/yaml_dsl_runner.py) |
| Compare harness | [`examples/compare_all.sh`](./examples/compare_all.sh) |
| Measured SUMMARY | [`results/SUMMARY.txt`](./results/SUMMARY.txt) |
| White paper | [`WHITEPAPER.md`](./WHITEPAPER.md) · [`docs/vortex_vs_adhoc_whitepaper.pdf`](./docs/vortex_vs_adhoc_whitepaper.pdf) |

**Honest framing:** This repo proves the **methodology and maintainability** gap with numbers.  
The **Vortex product** is the industrial engine (GB-scale perf, audit trail, binary distribution). Plug it in with `VORTEX_BIN` when you have it — the proprietary binary is **not** shipped here.

---

## Quick start (on your machine)

```bash
cd vortex-vs-adhoc

# dependencies (YAML runner + optional PDF build)
pip install -r requirements.txt
# or minimal:  pip install pyyaml
# or system:   apt install python3-yaml

# run the full comparison (generates ~6MB synthetic log, times all engines)
./examples/compare_all.sh

# read the numbers
cat results/SUMMARY.txt

# optional — rebuild the white-paper PDF
python3 docs/build_whitepaper_pdf.py
```

Optional — measure your Vortex binary on the same log/policy:

```bash
export VORTEX_BIN=/path/to/vortex
./examples/compare_all.sh
```

Larger log:

```bash
LINES=1000000 REGEN_LOG=1 ./examples/compare_all.sh
```

---

## Headline numbers (this CI run)

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

Raw line counts (including comments/blanks): YAML 67 · Bash 133 · Python 138 · Perl 77.

### Correctness

All four engines **MATCH** on triggered rules and **identical hit counts** for all 7 rules on the synthetic log.

### Wall time (same log — illustrative)

| Engine | Seconds |
|---|---:|
| bash (`grep`) | ~0.23 |
| yaml_dsl reference | ~0.96 |
| python ad-hoc | ~0.98 |
| perl ad-hoc | ~1.03 |
| vortex | set `VORTEX_BIN` |

On a **small** synthetic file, `grep` is often fastest. That does **not** overturn the thesis:

1. Maintainability / team alignment live in the **YAML**, not in who won a 6 MB microbench.  
2. On **multi‑GB farm logs**, the Vortex binary’s mmap/search path is the performance product (see your private GB measurements) — re-run with `VORTEX_BIN` + a real chamber log for that claim.

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
├── WHITEPAPER.md
├── policy/design_health.yaml      # shared 7-rule policy
├── runners/yaml_dsl_runner.py     # reference interpreter
├── adhoc/
│   ├── bash_search_by_rule.sh
│   ├── python_search_by_rule.py
│   └── perl_search_by_rule.pl
├── scripts/gen_synthetic_log.py
├── examples/compare_all.sh
├── results/                       # SUMMARY + timings (log may be gitignored)
└── docs/
```

---

## What this does *not* claim

- That Bash is always slower than Vortex on tiny files.  
- That the reference YAML runner **is** Vortex.  
- Customer QoR or tapeout outcomes.

It **does** claim: for the same 7 rules, policy-as-code is shorter, clearer, and team-aligning — and every engine can be verified to agree on a public synthetic log on your laptop.
