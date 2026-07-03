# Metal Fill (FEOL/BEOL) — recursive-partitioned dummy fill.
#
# Build is CPU (OpenMP-parallel across partitions). The compute-heavy stages are
# isolated behind FillBackend (see include/metalfill/backend.hpp) so a CUDA
# backend can be dropped in later (GPU offload is future work).

CXX      ?= g++
OPT      ?= -O2
CXXFLAGS ?= -std=c++17 $(OPT) -Wall -Wextra -Iinclude
LDFLAGS  ?=

# OpenMP (parallel partitions / fill). Disable with `make OPENMP=0`.
OPENMP ?= 1
ifeq ($(OPENMP),1)
  CXXFLAGS += -fopenmp
  LDFLAGS  += -fopenmp
endif

BUILD := build
LIB_SRC := $(wildcard src/*.cpp)
LIB_OBJ := $(patsubst src/%.cpp,$(BUILD)/%.o,$(LIB_SRC))

TOOLS := $(BUILD)/make_dummy_gds $(BUILD)/run_fill $(BUILD)/render_layer
TESTS := $(BUILD)/test_main

.PHONY: all tools test demo clean
all: tools
tools: $(TOOLS)

$(BUILD):
	mkdir -p $(BUILD)

$(BUILD)/%.o: src/%.cpp | $(BUILD)
	$(CXX) $(CXXFLAGS) -c $< -o $@

$(BUILD)/make_dummy_gds: tools/make_dummy_gds.cpp $(LIB_OBJ) | $(BUILD)
	$(CXX) $(CXXFLAGS) $< $(LIB_OBJ) -o $@ $(LDFLAGS)

$(BUILD)/run_fill: tools/run_fill.cpp $(LIB_OBJ) | $(BUILD)
	$(CXX) $(CXXFLAGS) $< $(LIB_OBJ) -o $@ $(LDFLAGS)

$(BUILD)/render_layer: tools/render_layer.cpp $(LIB_OBJ) | $(BUILD)
	$(CXX) $(CXXFLAGS) $< $(LIB_OBJ) -o $@ $(LDFLAGS)

$(BUILD)/test_main: tests/test_main.cpp $(LIB_OBJ) | $(BUILD)
	$(CXX) $(CXXFLAGS) $< $(LIB_OBJ) -o $@ $(LDFLAGS)

test: $(TESTS)
	$(BUILD)/test_main

demo: tools
	$(BUILD)/make_dummy_gds -o $(BUILD)/dummy.gds
	$(BUILD)/run_fill -i $(BUILD)/dummy.gds -o $(BUILD)/filled.gds -r $(BUILD)/report.txt

clean:
	rm -rf $(BUILD)
