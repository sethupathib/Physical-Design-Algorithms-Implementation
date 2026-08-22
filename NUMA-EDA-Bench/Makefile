#!/usr/bin/env bash
# Fallback if you don't want CMake — kept for parity with older notes
# Primary: make -j && ./examples/compare_numa.sh
CXX      ?= g++
CXXFLAGS ?= -O3 -std=c++17 -Wall -Wextra -march=native
LDFLAGS  ?= -pthread

BIN := build/numa_mem_bench
SRC := src/numa_mem_bench.cpp

.PHONY: all clean run-local compare report pdf

all: $(BIN)

build:
	mkdir -p build

$(BIN): $(SRC) | build
	$(CXX) $(CXXFLAGS) -o $@ $< $(LDFLAGS)

clean:
	rm -rf build

run-local: $(BIN)
	./$(BIN) --bytes 256M --threads 4 --stream-iters 5

compare: $(BIN)
	./examples/compare_numa.sh

report:
	./scripts/numa_report.sh

pdf:
	python3 docs/build_whitepaper_pdf.py
