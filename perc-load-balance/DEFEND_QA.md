# DEFEND_QA

### Q1. Isn’t this just “use more cores”?
**A.** No. More cores without tokens/slots is how jobs pend forever. We plan under both ceilings.

### Q2. Why not always max `turbo`?
**A.** Guide band for mmDRC is often 4–8. Beyond that, efficiency drops (bacct) while license spend rises. Measure.

### Q3. Does `-R select[mem>64]` give me 64 GB?
**A.** On TSRI-class LSF: **no**. It filters hosts. Memory is not reserved. Size from prior `bacct`/rep and expect contention.

### Q4. Why is the master `-n 1`?
**A.** For remote Calibre, the master coordinates; children are separate LSF jobs. Burning 32 slots on the master wastes the user ceiling.

### Q5. Are your license ratios correct for Siemens?
**A.** Unknown until you calibrate. `farm.yaml` defaults are explicit **assumptions**. Day-1 sandbox task: run one small job and watch `lmstat`.

### Q6. Will this make PERC 2× faster?
**A.** Not claimed. It prevents impossible launches and targets efficient feasible parallelism. Walltime claims need on-farm A/B.

### Q7. DRC vs PERC?
**A.** Same slot/license planning physics; different ruledecks/features. Set `flow:` and `calibre_base.feature` accordingly.

### Q8. Hyperflex?
**A.** Guide: can multiply memory use; LSF may kill. Default off in examples.
