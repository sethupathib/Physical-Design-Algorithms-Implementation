# Kernel AutoFDO on the farm host (not rebuilt in this repo)
#
# Published result (Linux kernel + Clang AutoFDO, LPC / LLVM discourse):
#   Neper tcp_rr latency ≈ 10.6% improvement (AutoFDO vs default kernel)
#   Warehouse-scale services ≈ up to ~5%
#
# Why it matters for Fusion Compiler / signoff:
#   FC and PT jobs spend wall time in user code AND in the kernel
#   (page faults, scheduling, NFS/license syscalls, interrupt handling).
#   An AutoFDO-tuned kernel reduces *kernel latency*. It does not
#   recompile Synopsys binaries.
#
# This file is a cookbook for methodology / CAD / IT — not a one-click script.

## Prerequisites
# - Clang/LLVM ≥ 17 with AutoFDO support
# - Farm hosts with Intel LBR (or Arm SPE/ETM)
# - Ability to install a custom kernel (or work with IT on a pilot rack)
# - Representative FC/signoff load for profiling (production sample preferred)

## High-level flow
# 1. Build kernel with CONFIG_AUTOFDO_CLANG=y (and debug info for sampling)
# 2. Boot that kernel on a pilot host
# 3. Run representative FC / signoff / NFS-heavy load
# 4. perf record -e BR_INST_RETIRED.NEAR_TAKEN:k -b ... (see kernel docs)
# 5. Convert with llvm_profgen / create_llvm_prof
# 6. Rebuild kernel with -fprofile-sample-use=<profile>
# 7. A/B measure: same FC job deck on baseline vs AutoFDO kernel
#    Metrics: wall time, CPU%, voluntary/involuntary context switches,
#    perf stat frontend stalls, NFS latency

## Official docs
# https://www.kernel.org/doc/html/latest/dev-tools/autofdo.html
# LPC 2024: AutoFDO & Propeller for kernel
# LLVM discourse: Optimizing the Linux kernel with AutoFDO (+ThinLTO +Propeller)

## What NOT to claim
# - "We AutoFDO'd Fusion Compiler" — false without vendor cooperation
# - "Every FC job gets 10%" — 10% is *kernel latency* on Neper tcp_rr, not FC QoR
# - Cite farm A/B numbers only when CLAIM_GATE / controlled deck says so

## Sibling: user-space path (this repo)
# make pgo && make compare
# Optimizes *your* signoff_proxy / in-house tools — measurable on a laptop.
