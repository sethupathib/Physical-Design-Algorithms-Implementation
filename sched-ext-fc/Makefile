CC ?= gcc
CFLAGS ?= -O2 -Wall -Wextra -pthread
BIN := build/fc_sched_bench

.PHONY: all clean

all: $(BIN)

build:
	mkdir -p build

$(BIN): src/fc_sched_bench.c | build
	$(CC) $(CFLAGS) -o $@ $< -lm

clean:
	rm -f $(BIN)
