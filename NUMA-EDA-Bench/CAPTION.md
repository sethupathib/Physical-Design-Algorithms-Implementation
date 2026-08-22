# LinkedIn caption — paste / edit

---

Your Fusion Compiler job can look CPU-bound and still be dying on the interconnect.

On a dual-socket server, each socket owns its own DRAM.
If `fc_shell` runs on node 0 but the working set was first-touched on node 1, every load crosses UPI/Infinity Fabric.

`top` shows 100%.
Wall clock does not care.

The fix is a policy, not more cores:

```bash
numactl --cpunodebind=0 --membind=0 fc_shell -f run.tcl
```

Same silicon.
CPU + pages on the **same** NUMA node.
Interconnect goes quiet.

Caveat that matters in production: only do hard `membind` when peak RSS fits that node’s free RAM. Otherwise `--preferred=0` or size the machine.

Demo GIF: unbound remote fills → policy → local recovery.

#PhysicalDesign #EDA #FusionCompiler #NUMA #HPC #Semiconductor

---

**Alt shorter:**

FC at 100% CPU on a 2S box can still be NUMA-bound.
Pin cores + DRAM to one node:
`numactl --cpunodebind=0 --membind=0 …`
Free wall-time when the design fits the node.
