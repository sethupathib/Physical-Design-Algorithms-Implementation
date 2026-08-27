// dispatch_hot — mechanism microbench: skewed switch dispatch (classic PGO win).
// Not a Fusion Compiler model. Used to show FDO can move the needle when the
// bottleneck is branchy control flow / I-cache layout.
#include <chrono>
#include <cstdint>
#include <cstdio>
#include <cstdlib>

__attribute__((noinline)) static uint64_t h0(uint64_t x) { return x + 1; }
__attribute__((noinline)) static uint64_t h1(uint64_t x) { return x + 3; }
__attribute__((noinline)) static uint64_t h2(uint64_t x) { return x + 5; }
__attribute__((noinline)) static uint64_t h3(uint64_t x) { return x + 7; }
__attribute__((noinline)) static uint64_t h4(uint64_t x) { return x + 11; }
__attribute__((noinline)) static uint64_t h5(uint64_t x) { return x + 13; }
__attribute__((noinline)) static uint64_t h6(uint64_t x) { return x + 17; }
__attribute__((noinline)) static uint64_t h7(uint64_t x) { return x + 19; }
__attribute__((noinline)) static uint64_t h8(uint64_t x) { return x + 23; }
__attribute__((noinline)) static uint64_t h9(uint64_t x) { return x + 29; }

int main(int argc, char** argv) {
  long n = argc > 1 ? std::atol(argv[1]) : 25000000L;
  uint64_t s = 1, acc = 0;
  auto t0 = std::chrono::steady_clock::now();
  for (long i = 0; i < n; ++i) {
    s ^= s << 13;
    s ^= s >> 7;
    s ^= s << 17;
    int op;
    if ((s & 1) == 0)
      op = 0;
    else if ((s & 3) == 1)
      op = 1;
    else if ((s & 7) == 3)
      op = 2;
    else if ((s & 15) == 7)
      op = 3;
    else
      op = 4 + (int)(s % 6);
    switch (op) {
      case 0: acc = h0(acc); break;
      case 1: acc = h1(acc); break;
      case 2: acc = h2(acc); break;
      case 3: acc = h3(acc); break;
      case 4: acc = h4(acc); break;
      case 5: acc = h5(acc); break;
      case 6: acc = h6(acc); break;
      case 7: acc = h7(acc); break;
      case 8: acc = h8(acc); break;
      default: acc = h9(acc); break;
    }
  }
  auto t1 = std::chrono::steady_clock::now();
  double ms = std::chrono::duration<double, std::milli>(t1 - t0).count();
  std::printf("{\"wall_ms\":%.3f,\"acc\":%llu,\"iters\":%ld}\n", ms,
              (unsigned long long)acc, n);
  return 0;
}
