CXX      ?= g++
CXXFLAGS ?= -std=c++17 -O2 -Wall -Wextra -pthread -Iinclude
LDFLAGS  ?= -pthread

SRC := src/design.cpp src/generator.cpp src/checks.cpp src/metadata.cpp src/engine.cpp
OBJ := $(SRC:.cpp=.o)

.PHONY: all clean test bench run

all: perc_optimizer test_perc

perc_optimizer: $(OBJ) src/main.o
	$(CXX) $(CXXFLAGS) -o $@ $^ $(LDFLAGS)

test_perc: $(OBJ) tests/test_perc.o
	$(CXX) $(CXXFLAGS) -o $@ $^ $(LDFLAGS)

src/%.o: src/%.cpp
	$(CXX) $(CXXFLAGS) -c -o $@ $<

tests/%.o: tests/%.cpp
	$(CXX) $(CXXFLAGS) -c -o $@ $<

run: perc_optimizer
	./perc_optimizer --pads 24 --blocks 6 --devices 200

bench: perc_optimizer
	./perc_optimizer --bench --eco --workers $$(nproc 2>/dev/null || echo 4)

test: test_perc
	./test_perc

clean:
	rm -f $(OBJ) src/main.o tests/test_perc.o perc_optimizer test_perc
