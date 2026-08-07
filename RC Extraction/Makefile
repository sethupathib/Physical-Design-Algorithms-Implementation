CXX      ?= g++
CXXFLAGS ?= -std=c++17 -O2 -Wall -Wextra -pedantic -Iinclude
LDFLAGS  ?=

SRCS = \
  src/techfile.cpp \
  src/layout.cpp \
  src/connectivity.cpp \
  src/resistance.cpp \
  src/capacitance.cpp \
  src/rc_network.cpp \
  src/spef_writer.cpp \
  src/elmore.cpp \
  src/extract.cpp

OBJS = $(SRCS:.cpp=.o)

.PHONY: all clean test demos

all: rcx_extract test_rc

rcx_extract: src/main.cpp $(OBJS)
	$(CXX) $(CXXFLAGS) -o $@ src/main.cpp $(OBJS) $(LDFLAGS)

test_rc: tests/test_rc.cpp $(OBJS)
	$(CXX) $(CXXFLAGS) -o $@ tests/test_rc.cpp $(OBJS) $(LDFLAGS)

src/%.o: src/%.cpp
	$(CXX) $(CXXFLAGS) -c -o $@ $<

test: test_rc
	./test_rc

demos: rcx_extract
	@echo "===== simple_net ====="
	./rcx_extract examples/simple_net.lay --spef /tmp/simple_net.spef --elmore clk U1:Z
	@echo ""
	@echo "===== coupled_nets ====="
	./rcx_extract examples/coupled_nets.lay --spef /tmp/coupled_nets.spef
	@echo ""
	@echo "===== via_stack ====="
	./rcx_extract examples/via_stack.lay --spef /tmp/via_stack.spef --elmore netx DRV:Z

clean:
	rm -f $(OBJS) rcx_extract test_rc
