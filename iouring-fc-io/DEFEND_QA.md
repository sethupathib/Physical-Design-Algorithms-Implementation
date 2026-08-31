# DEFEND_QA — io_uring × Fusion Compiler

## 0. One sentence

**io_uring can speed the I/O *around* FC (stage-in, hydrate, log ingest); it cannot recompile Synopsys — measure stage-in and FC wall separately, and believe CLAIM_GATE.**

---

## 1. Concepts

**Q: What is io_uring?**  
A: Linux submission/completion-queue I/O. Batch ops, fewer syscalls, deeper outstanding queues via liburing.

**Q: Why talk about it for FC?**  
A: FC jobs still storm small libs and suck large DEF/logs. That tax is often NFS. Wrappers can change that path.

---

## 2. Failure modes

**Q: “We io_uring’d Fusion Compiler.”**  
A: False unless Synopsys says so. You io_uring’d *your* hydrate/copier.

**Q: Bench shows posix faster on small files — so io_uring is useless?**  
A: On warm local cache, yes often. On cold NFS, queue depth matters. Re-measure on the farm.

**Q: FC wall didn’t move after uring hydrate.**  
A: Job was probably CPU-bound after stage-in. That’s a successful measurement, not a failed project.

---

## 3. How to defend the numbers

1. Show `results/SUMMARY.txt` + `CLAIM_GATE.txt`.  
2. State storage class (overlay vs NFS→NVMe).  
3. Separate **stage-in seconds** from **fc_shell seconds**.  
4. Refuse to cite cloud warm-cache small-file ratios as farm truth.

---

## 4. 30-second pitch

“FC is closed. We built a liburing bench for the I/O we *do* own — liberty storms and big DEF/log reads — with an honesty gate. Large objects saw a small uring win here; tiny warm files did not. Next step is NFS→NVMe stage-in A/B on a pilot rack.”
