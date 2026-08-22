# Fallback build
CXX      ?= g++
CXXFLAGS ?= -O3 -std=c++17 -Wall -Wextra -march=native
LDFLAGS  ?= -pthread

BIN := build/numa_mem_bench
SRC := src/numa_mem_bench.cpp

.PHONY: all clean report compare pdf

all: $(BIN)

build:
	mkdir -p build

$(BIN): $(SRC) | build
	$(CXX) $(CXXFLAGS) -o $@ $< $(LDFLAGS)

clean:
	rm -rf build

report:
	./scripts/numa_report.sh

compare: $(BIN)
	./examples/compare_numa.sh

pdf:
	python3 docs/build_whitepaper_pdf.py
