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

I ran the same BEFORE/AFTER experiment style as my tmpfs+rsync work — STREAM triad + pointer chase + graph walk:

- AFTER/BEFORE triad ≈ **1.27×**
- chase ≈ **1.66×** faster when local
- wall_proxy ≈ **2.2×** better

(On this 1-node cloud box BEFORE is a labeled remote-DRAM emulation — same idea as NFS RTT modeling. Re-run on a real 2S farm for hardware numbers.)

Repo: NUMA-EDA-Bench — compare harness, white paper, production wrapper, demo GIF.

Same silicon. Better memory policy.

#PhysicalDesign #EDA #FusionCompiler #NUMA #HPC #Semiconductor
