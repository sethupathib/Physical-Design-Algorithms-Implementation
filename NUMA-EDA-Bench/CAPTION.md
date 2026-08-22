# LinkedIn caption — paste / edit

**Claims policy:** Do not post speedup numbers from a 1-node / emulated run.
Only cite hardware `membind=remote` vs `membind=local` (or real FC wall time) from a multi-socket farm box.

---

Your Fusion Compiler job can look CPU-bound and still be dying on the interconnect.

On a dual-socket server, each socket owns its own DRAM.
If `fc_shell` runs on node 0 but the working set was first-touched on node 1, every load crosses UPI / Infinity Fabric.

`top` shows 100%.
Wall clock does not care.

The policy (when the working set fits one node’s free RAM):

```bash
numactl --cpunodebind=0 --membind=0 fc_shell -f run.tcl
```

I built a before/after harness for this (same ops rigor as the tmpfs+rsync work): STREAM triad + pointer-chase + graph walk, plus a production `numactl` wrapper.

What I will **not** do: quote “X× faster” from a single-socket cloud VM. That host cannot show remote DRAM. Emulated taxes are for harness smoke only.

What I **will** post when I have it: hardware remote vs local on a real 2S/4S node (or FC stage wall time + `numastat`), with the SUMMARY attached.

Repo: NUMA-EDA-Bench — measure on farm silicon, then claim.

#PhysicalDesign #EDA #FusionCompiler #NUMA #Semiconductor
