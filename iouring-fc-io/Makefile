CC ?= gcc
CFLAGS ?= -O2 -Wall -Wextra -std=c11
LDFLAGS ?= -luring

ROOT := $(abspath .)
BIN := $(ROOT)/build

.PHONY: all clean bench dataset compare figures pdf gif all-docs

all: $(BIN)/fc_io_bench

$(BIN)/fc_io_bench: src/fc_io_bench.c
	mkdir -p $(BIN)
	$(CC) $(CFLAGS) -o $@ $< $(LDFLAGS)

dataset:
	bash scripts/gen_dataset.sh

bench: all
	$(BIN)/fc_io_bench --root data --mode all --backend all --repeat 3

compare: all
	bash examples/compare_all.sh

figures:
	python3 docs/gen_figures.py

gif:
	python3 demo/gen_gif.py

pdf:
	python3 docs/build_whitepaper_pdf.py

all-docs: figures gif pdf

clean:
	rm -rf $(BIN)
