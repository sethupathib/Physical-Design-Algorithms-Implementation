# DEFEND_QA — Airflow hacks for FC + Vortex

## 0. One sentence

**Airflow is the assembly line: it starts FC, always runs Vortex, branches on severity, and refuses to overbook licenses — and you can demo that on a laptop without installing Airflow.**

---

## 1. Concepts

**Q: Do I need Airflow to learn this?**  
A: No. `python3 scripts/local_runner.py` runs the same hacks.

**Q: Is this replacing Vortex?**  
A: No. Vortex (or the mock) is the **forensics engine**. Airflow is the **orchestrator**.

**Q: Is this replacing FC?**  
A: No. FC (or the mock) is the **implementation tool**. Airflow triggers it.

---

## 2. Failure modes these hacks fix

| Failure | Hack |
|---|---|
| Forgot to run Vortex | #1 chain / #6 dataset |
| Grep false positive on clean log | #2 branch on `overall` |
| License storm | #3 pool |
| Corner copy-paste debt | #4 / #8 |
| Vortex after FC FATAL | #5 short-circuit |
| License checkout blip kills night run | #7 retries |

---

## 3. Challenge round

**Q: Your DAG is longer than the Bash script — so Bash wins?**  
A: Bash wins **LOC for one happy path**. Airflow wins **reviewability, pools, retries, UI trigger, run history**. Adding the 5th corner is a JSON edit, not a script fork.

**Q: Why did naive grep fail the demo?**  
A: Rule *names* always appear in Vortex JSON. Grep thinks every log is a setup violation. Branch on `overall` / `triggered`.

**Q: How is this simpler than AutoFDO?**  
A: No kernel rebuild, no `perf`, no PMU. One `pip install pyyaml` and you’re demoing.

---

## 4. 30-second pitch

“We don’t hope someone greps the log. Airflow finishes FC, runs Vortex policy, pages on fatal, opens Jira on timing, and never launches more FC than we have seats.”

---

## 5. Checklist

- [ ] Ran `./examples/compare_all.sh`  
- [ ] Read `CLAIM_GATE.txt`  
- [ ] Pool `fc_licenses` sized to seats  
- [ ] Policy YAML shared with Vortex  
- [ ] Not claiming FC algorithm speedups  
