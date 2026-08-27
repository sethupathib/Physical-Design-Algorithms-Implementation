# DEFEND_QA — AutoFDO for FC / signoff runtime

## 0. One sentence

**AutoFDO’s published ~10% is mostly a *kernel latency* win for farm hosts under FC/signoff; you PGO the code you own, and you ask Synopsys for the rest — then you measure.**

---

## 1. Concepts

**Q: What is AutoFDO?**  
A: Feedback-directed optimization using **hardware samples** (`perf` + LBR) instead of heavy compiler instrumentation. Great for kernels and production processes.

**Q: Is that the same as `-fprofile-generate`?**  
A: Same family (FDO), different collection. Instrumentation PGO = compiler counters. AutoFDO = PMU samples → `llvm-profgen` / `create_llvm_prof`.

**Q: Why do slides say “up to 10%”?**  
A: Published **Linux kernel** AutoFDO results (Neper `tcp_rr` latency ~10.6%). Not a universal FC wall-time guarantee.

---

## 2. Failure mode (what people get wrong)

**Q: “We’ll AutoFDO Fusion Compiler this weekend.”**  
A: You don’t have FC sources. Closed binary → vendor conversation, not a Makefile.

**Q: “Kernel AutoFDO will cut every FC job 10%.”**  
A: Only the **kernel-bound** slice moves. A pure DRAM-bound place/route phase may show little. A/B the **same deck**.

**Q: “PGO always wins.”**  
A: This repo’s cloud host showed **~neutral** user-space PGO. FDO can regress. That’s why CLAIM_GATE exists.

---

## 3. Fix / levers

| Lever | Action |
|---|---|
| Kernel | Pilot AutoFDO kernel (`farm/KERNEL_AUTOFDO.md`) |
| Owned tools | `make pgo && ./examples/compare_all.sh` |
| Vendor | AE request: profile-optimized FC/PT builds |
| NUMA / I/O | Sibling projects — orthogonal wins |

---

## 4. How to measure

```bash
make baseline pgo && ./examples/compare_all.sh
cat results/SUMMARY.txt results/CLAIM_GATE.txt
```

Farm:

```text
Same deck → host A baseline kernel vs host B AutoFDO kernel
Record wall time, perf stat, NFS latency, license wait
```

---

## 5. GIF / figure honesty

Mechanism diagrams show **pipeline** (sample → convert → rebuild → A/B). They are **not** a benchmark of FC.

---

## 6. Challenge round

**Q: Your SUMMARY shows no user-space win. Is the project useless?**  
A: No — it proves the measurement discipline and points the 10% claim at the **kernel** lever where the literature lives.

**Q: Why GCC PGO not Clang AutoFDO on the laptop?**  
A: GCC instrumentation PGO is the most portable citeable path. Sample AutoFDO needs working LBR/`perf` mmap events; many VMs fail (`llvm-profgen: No relevant mmap event`).

**Q: Can methodology leads review this?**  
A: Yes — README dimension table + CLAIM_GATE + farm cookbook are the shared language.

---

## 7. 30-second pitch

“AutoFDO’s 10% is a kernel story. We PGO our own tools with a gated harness, we pilot AutoFDO kernels under FC with A/B decks, and we don’t claim we recompiled Synopsys.”

---

## 8. Checklist before posting numbers

- [ ] Binary named (`signoff_proxy` vs `fc_shell`)  
- [ ] CLAIM_GATE read  
- [ ] Literature 10% cited as kernel, not as this SUMMARY  
- [ ] Farm A/B deck hash recorded  
- [ ] No “FC got X%” unless farm gate says so  
