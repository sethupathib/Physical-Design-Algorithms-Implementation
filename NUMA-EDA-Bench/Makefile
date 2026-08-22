# Fallback if you don't want CMake
CXX      ?= g++
CXXFLAGS ?= -O3 -std=c++17 -Wall -Wextra -march=native
LDFLAGS  ?= -pthread

BIN := build/numa_mem_bench
SRC := src/numa_mem_bench.cpp

.PHONY: all clean run-local compare

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
	./scripts/compare_local_remote.sh
