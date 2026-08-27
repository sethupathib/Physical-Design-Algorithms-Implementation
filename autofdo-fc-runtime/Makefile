# autofdo-fc-runtime — PGO / AutoFDO demo for PD/signoff-shaped workloads
#
# Citeable laptop path: GCC instrumentation PGO on signoff_proxy.
# Clang IRPGO + sample AutoFDO are optional / best-effort on this host.
# Kernel AutoFDO for farm hosts is documented (not rebuilt in this repo).

# Prefer g++ for citeable PGO (reliable .gcda path on Ubuntu).
CXX_GCC  ?= g++
CXX_CLANG ?= $(shell command -v clang++-18 || command -v clang++ || echo clang++)
CXXFLAGS ?= -O2 -g -std=c++17 -Wall -Wextra -fno-omit-frame-pointer
LLVM_BIN ?= /usr/lib/llvm-18/bin
PROFDATA ?= $(LLVM_BIN)/llvm-profdata
PROFGEN  ?= $(LLVM_BIN)/llvm-profgen
PERF     ?= $(shell ls /usr/lib/linux-tools/*/perf 2>/dev/null | head -1)
ifeq ($(PERF),)
  PERF := perf
endif

ROOT := $(abspath .)
BIN  := $(ROOT)/build
RES  := $(ROOT)/results

.PHONY: all clean dirs baseline pgo pgo-clang sample-autofdo smoke compare compare-mech report \
        figures pdf gif all-docs help mechanism

help:
	@echo "Targets: baseline pgo mechanism compare compare-mech sample-autofdo figures pdf gif"
	@echo "Citeable laptop path: make baseline pgo compare   (GCC PGO on signoff_proxy)"
	@echo "Mechanism demo:       make mechanism compare-mech (skewed switch — clearer PGO win)"

all: baseline pgo

dirs:
	mkdir -p $(BIN) $(RES) docs/figures demo

baseline: dirs
	$(CXX_GCC) $(CXXFLAGS) -o $(BIN)/signoff_proxy_baseline src/signoff_proxy.cpp

# --- GCC instrumentation PGO (citeable laptop path) ---
# Compile to a stable object name so .gcda/.gcno match between generate and use.
pgo: dirs
	rm -rf $(BIN)/gcc_pgo && mkdir -p $(BIN)/gcc_pgo
	cd $(BIN)/gcc_pgo && $(CXX_GCC) $(CXXFLAGS) -fprofile-generate \
	  -c -o signoff_proxy.o $(ROOT)/src/signoff_proxy.cpp
	cd $(BIN)/gcc_pgo && $(CXX_GCC) $(CXXFLAGS) -fprofile-generate \
	  -o gen signoff_proxy.o
	@echo "== GCC PGO train =="
	$(BIN)/gcc_pgo/gen --nodes 10000 --rounds 40 --ops 1500000 --seed 7 >/dev/null
	$(BIN)/gcc_pgo/gen --nodes 14000 --rounds 55 --ops 2200000 --seed 11 >/dev/null
	$(BIN)/gcc_pgo/gen --nodes 12000 --rounds 50 --ops 2000000 --seed 42 >/dev/null
	@test -f $(BIN)/gcc_pgo/signoff_proxy.gcda
	cd $(BIN)/gcc_pgo && $(CXX_GCC) $(CXXFLAGS) -fprofile-use -fprofile-correction \
	  -c -o signoff_proxy.o $(ROOT)/src/signoff_proxy.cpp
	cd $(BIN)/gcc_pgo && $(CXX_GCC) $(CXXFLAGS) -fprofile-use \
	  -o $(BIN)/signoff_proxy_pgo signoff_proxy.o
	@echo "wrote $(BIN)/signoff_proxy_pgo"


# --- Clang IRPGO (optional; may regress on some cloud CPUs — measure before citing) ---
pgo-clang: dirs
	rm -rf $(BIN)/clang_pgo $(BIN)/clang.profdata
	mkdir -p $(BIN)/clang_pgo
	$(CXX_CLANG) $(CXXFLAGS) -fprofile-generate=$(BIN)/clang_pgo \
	  -o $(BIN)/signoff_proxy_clang_gen src/signoff_proxy.cpp
	LLVM_PROFILE_FILE=$(BIN)/clang_pgo/train_%p.profraw \
	  $(BIN)/signoff_proxy_clang_gen --nodes 12000 --rounds 50 --ops 2000000 --seed 42 >/dev/null
	$(PROFDATA) merge -o $(BIN)/clang.profdata $(BIN)/clang_pgo/*.profraw
	$(CXX_CLANG) $(CXXFLAGS) -fprofile-use=$(BIN)/clang.profdata \
	  -o $(BIN)/signoff_proxy_clang_pgo src/signoff_proxy.cpp
	@echo "wrote $(BIN)/signoff_proxy_clang_pgo (optional — compare separately)"

# --- Sample-based AutoFDO (best-effort) ---
sample-autofdo: baseline dirs
	@echo "== sample AutoFDO via perf + llvm-profgen =="
	@if [ ! -x "$(PERF)" ] && ! command -v $(PERF) >/dev/null 2>&1; then \
	  echo "SKIP: perf not found"; exit 0; fi
	$(CXX_CLANG) $(CXXFLAGS) -fdebug-info-for-profiling \
	  -o $(BIN)/signoff_proxy_baseline_afdo src/signoff_proxy.cpp || \
	  $(CXX_GCC) $(CXXFLAGS) -o $(BIN)/signoff_proxy_baseline_afdo src/signoff_proxy.cpp
	$(PERF) record -o $(BIN)/perf.data -e cycles:u -c 10007 -- \
	  $(BIN)/signoff_proxy_baseline_afdo --nodes 12000 --rounds 50 --ops 2000000 --seed 42 >/dev/null
	@if [ -x "$(PROFGEN)" ]; then \
	  $(PROFGEN) --binary=$(BIN)/signoff_proxy_baseline_afdo --perfdata=$(BIN)/perf.data \
	    --output=$(BIN)/sample.prof 2>$(BIN)/profgen.err || true; \
	fi
	@if [ -s $(BIN)/sample.prof ]; then \
	  $(CXX_CLANG) $(CXXFLAGS) -fprofile-sample-use=$(BIN)/sample.prof \
	    -o $(BIN)/signoff_proxy_autofdo src/signoff_proxy.cpp && \
	  echo "wrote $(BIN)/signoff_proxy_autofdo"; \
	else \
	  echo "SKIP: sample profile not produced (see $(BIN)/profgen.err)"; \
	  echo "  GCC PGO (make pgo) remains the citeable laptop path."; \
	fi

smoke: baseline
	$(BIN)/signoff_proxy_baseline --nodes 2000 --rounds 5 --ops 50000 --json

compare: baseline pgo
	bash examples/compare_all.sh

# --- Mechanism demo: skewed switch (usually clearer PGO delta) ---
mechanism: dirs
	rm -rf $(BIN)/mech_pgo && mkdir -p $(BIN)/mech_pgo
	$(CXX_GCC) $(CXXFLAGS) -o $(BIN)/dispatch_hot_baseline src/dispatch_hot.cpp
	cd $(BIN)/mech_pgo && $(CXX_GCC) $(CXXFLAGS) -fprofile-generate \
	  -c -o dispatch_hot.o $(ROOT)/src/dispatch_hot.cpp
	cd $(BIN)/mech_pgo && $(CXX_GCC) $(CXXFLAGS) -fprofile-generate -o gen dispatch_hot.o
	$(BIN)/mech_pgo/gen 20000000 >/dev/null
	$(BIN)/mech_pgo/gen 25000000 >/dev/null
	cd $(BIN)/mech_pgo && $(CXX_GCC) $(CXXFLAGS) -fprofile-use -fprofile-correction \
	  -c -o dispatch_hot.o $(ROOT)/src/dispatch_hot.cpp
	cd $(BIN)/mech_pgo && $(CXX_GCC) $(CXXFLAGS) -fprofile-use \
	  -o $(BIN)/dispatch_hot_pgo dispatch_hot.o
	@echo "wrote $(BIN)/dispatch_hot_pgo"

compare-mech: mechanism
	bash examples/compare_mechanism.sh

report: compare

figures:
	python3 docs/gen_figures.py

pdf:
	python3 docs/build_whitepaper_pdf.py

gif:
	python3 demo/gen_gif.py

all-docs: figures gif pdf

clean:
	rm -rf $(BIN)
	rm -f results/*.json results/*.jsonl results/*.txt results/*.time 2>/dev/null || true
