#include <atomic>
#include <chrono>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <iostream>
#include <string>
#include <thread>
#include <vector>

#if defined(__linux__)
#include <sched.h>
#include <unistd.h>
#endif

// STREAM triad + pointer-chase microbench for NUMA local vs remote.
// No synthetic "wall_proxy". No emulated remote tax.
// On a 1-node host, local and remote policies are the same DRAM — do not
// interpret that as a NUMA win/loss.

namespace {

struct Args {
  std::size_t bytes = 512ull << 20;
  int threads = 0;
  int chase_iters = 8'000'000;
  int stream_iters = 5;
  bool json = false;
  bool help = false;
};

void usage(const char* argv0) {
  std::cerr
      << "Usage: " << argv0 << " [options]\n"
      << "  --bytes N|Nm|Ng   working set (default 512M)\n"
      << "  --threads T       default = nproc\n"
      << "  --stream-iters K\n"
      << "  --chase-iters K\n"
      << "  --json\n"
      << "\nHardware compare (need ≥2 NUMA nodes):\n"
      << "  numactl --cpunodebind=0 --membind=0 " << argv0 << " --json\n"
      << "  numactl --cpunodebind=0 --membind=1 " << argv0 << " --json\n";
}

std::size_t parse_size(const std::string& s) {
  char* end = nullptr;
  double v = std::strtod(s.c_str(), &end);
  if (end == s.c_str()) throw std::runtime_error("bad --bytes value");
  while (*end == ' ') ++end;
  double mul = 1.0;
  if (*end == 'k' || *end == 'K') mul = 1024.0;
  else if (*end == 'm' || *end == 'M') mul = 1024.0 * 1024.0;
  else if (*end == 'g' || *end == 'G') mul = 1024.0 * 1024.0 * 1024.0;
  else if (*end != '\0') throw std::runtime_error("bad --bytes suffix");
  return static_cast<std::size_t>(v * mul);
}

Args parse(int argc, char** argv) {
  Args a;
  for (int i = 1; i < argc; ++i) {
    std::string arg = argv[i];
    auto need = [&](const char* name) -> std::string {
      if (i + 1 >= argc) throw std::runtime_error(std::string("missing value for ") + name);
      return argv[++i];
    };
    if (arg == "-h" || arg == "--help") a.help = true;
    else if (arg == "--bytes") a.bytes = parse_size(need("--bytes"));
    else if (arg == "--threads") a.threads = std::stoi(need("--threads"));
    else if (arg == "--stream-iters") a.stream_iters = std::stoi(need("--stream-iters"));
    else if (arg == "--chase-iters") a.chase_iters = std::stoi(need("--chase-iters"));
    else if (arg == "--json") a.json = true;
    else throw std::runtime_error("unknown arg: " + arg);
  }
  if (a.threads <= 0) {
#if defined(__linux__)
    a.threads = static_cast<int>(sysconf(_SC_NPROCESSORS_ONLN));
#else
    a.threads = 1;
#endif
  }
  if (a.threads < 1) a.threads = 1;
  if (a.bytes < 64 * 1024) a.bytes = 64 * 1024;
  return a;
}

std::string cpu_affinity_string() {
#if defined(__linux__)
  cpu_set_t set;
  CPU_ZERO(&set);
  if (sched_getaffinity(0, sizeof(set), &set) != 0) return "unknown";
  std::string out;
  for (int c = 0; c < CPU_SETSIZE; ++c) {
    if (CPU_ISSET(c, &set)) {
      if (!out.empty()) out += ',';
      out += std::to_string(c);
    }
  }
  return out.empty() ? "none" : out;
#else
  return "n/a";
#endif
}

int numa_node_count() {
  int n = 0;
  for (int i = 0; i < 64; ++i) {
    char path[64];
    std::snprintf(path, sizeof(path), "/sys/devices/system/node/node%d", i);
    if (access(path, F_OK) == 0) ++n;
    else break;
  }
  return n > 0 ? n : 1;
}

double seconds_since(std::chrono::steady_clock::time_point t0) {
  using namespace std::chrono;
  return duration<double>(steady_clock::now() - t0).count();
}

double run_stream(std::size_t n, int threads, int iters) {
  std::vector<double> a(n), b(n), c(n);
  const double scalar = 3.0;
  for (std::size_t i = 0; i < n; ++i) {
    b[i] = 1.0;
    c[i] = 2.0;
  }

  auto worker = [&](int tid) {
    const std::size_t chunk = (n + threads - 1) / threads;
    const std::size_t lo = static_cast<std::size_t>(tid) * chunk;
    const std::size_t hi = std::min(n, lo + chunk);
    for (int it = 0; it < iters; ++it) {
      for (std::size_t i = lo; i < hi; ++i) a[i] = b[i] + scalar * c[i];
    }
    volatile double sink = a[lo];
    (void)sink;
  };

  auto t0 = std::chrono::steady_clock::now();
  std::vector<std::thread> pool;
  for (int t = 0; t < threads; ++t) pool.emplace_back(worker, t);
  for (auto& th : pool) th.join();
  const double sec = seconds_since(t0);
  const double bytes = static_cast<double>(iters) * static_cast<double>(n) * sizeof(double) * 3.0;
  return (bytes / sec) / (1024.0 * 1024.0 * 1024.0);
}

double run_chase(std::size_t nodes, int iters) {
  std::vector<std::uint32_t> next(nodes);
  for (std::size_t i = 0; i < nodes; ++i) next[i] = static_cast<std::uint32_t>(i);
  std::uint64_t state = 0x9e3779b97f4a7c15ULL;
  for (std::size_t i = nodes - 1; i > 0; --i) {
    state = state * 6364136223846793005ULL + 1;
    std::swap(next[i], next[state % (i + 1)]);
  }

  std::uint32_t idx = 0;
  auto t0 = std::chrono::steady_clock::now();
  for (int i = 0; i < iters; ++i) idx = next[idx];
  const double sec = seconds_since(t0);
  volatile std::uint32_t sink = idx;
  (void)sink;
  return (sec * 1e9) / static_cast<double>(iters);
}

}  // namespace

int main(int argc, char** argv) {
  try {
    Args args = parse(argc, argv);
    if (args.help) {
      usage(argv[0]);
      return 0;
    }

    std::size_t elems = args.bytes / (3 * sizeof(double));
    if (elems < 1024) elems = 1024;
    std::size_t chase_nodes = args.bytes / sizeof(std::uint32_t);
    if (chase_nodes < 4096) chase_nodes = 4096;

    const double gib_s = run_stream(elems, args.threads, args.stream_iters);
    const double chase_ns = run_chase(chase_nodes, args.chase_iters);

    if (args.json) {
      std::printf(
          "{\"threads\":%d,\"bytes\":%zu,\"numa_nodes\":%d,"
          "\"triad_gib_s\":%.6f,\"chase_ns\":%.6f,\"affinity\":\"%s\"}\n",
          args.threads, args.bytes, numa_node_count(), gib_s, chase_ns,
          cpu_affinity_string().c_str());
      return 0;
    }

    std::cout << "numa_mem_bench\n"
              << "  threads=" << args.threads << " bytes≈" << (elems * 3 * sizeof(double))
              << " chase_nodes=" << chase_nodes << "\n"
              << "  affinity=" << cpu_affinity_string() << " numa_nodes=" << numa_node_count()
              << "\n"
              << "  STREAM triad: " << gib_s << " GiB/s   (higher better)\n"
              << "  pointer chase: " << chase_ns << " ns/hop  (lower better)\n";
    return 0;
  } catch (const std::exception& e) {
    std::cerr << "error: " << e.what() << "\n";
    usage(argv[0]);
    return 1;
  }
}
