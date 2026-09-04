CC ?= gcc
CFLAGS ?= -O2 -Wall -Wextra -pthread
BIN := build/fc_noise_bench

.PHONY: all clean

all: $(BIN)

build:
	mkdir -p build

$(BIN): src/fc_noise_bench.c | build
	$(CC) $(CFLAGS) -o $@ $<

clean:
	rm -f $(BIN)
