CXX      ?= g++
CXXFLAGS ?= -O3 -std=c++17 -Wall -Wextra -march=native
LDFLAGS  ?= -pthread
BIN := build/numa_mem_bench
SRC := src/numa_mem_bench.cpp

.PHONY: all clean report compare gif pdf smoke

all: $(BIN)

build:
	mkdir -p build

$(BIN): $(SRC) | build
	$(CXX) $(CXXFLAGS) -o $@ $< $(LDFLAGS)

clean:
	rm -rf build demo/frames

report:
	./scripts/numa_report.sh

compare: $(BIN)
	./examples/compare_numa.sh

smoke: $(BIN)
	./$(BIN) --bytes 128M --threads $$(nproc)

gif:
	python3 demo/gen_gif.py

pdf:
	python3 docs/build_whitepaper_pdf.py
