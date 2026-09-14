# epyc-eda-tuned Makefile
CC ?= gcc
CFLAGS ?= -O2 -Wall -Wextra -pthread
ROOT := $(dir $(abspath $(lastword $(MAKEFILE_LIST))))
BIN := $(ROOT)src/fanout_bench

.PHONY: all bin test dry-inventory claim-gate clean

all: bin

bin: $(BIN)

$(BIN): $(ROOT)src/fanout_bench.c
	$(CC) $(CFLAGS) -o $@ $<

test: bin
	$(BIN) --mode spread --outer 3 --work-units 500 --burn-iters 2000
	$(BIN) --mode queue --outer 3 --work-units 4 --jobs 128 --burn-iters 2000

dry-inventory:
	$(ROOT)scripts/detect_env.sh
	$(ROOT)scripts/dump_sched_knobs.sh
	$(ROOT)scripts/compare_profiles.sh --dry-run

claim-gate:
	$(ROOT)scripts/claim_gate.sh

clean:
	rm -f $(BIN)
