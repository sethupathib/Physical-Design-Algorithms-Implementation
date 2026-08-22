#include <atomic>
#include <chrono>
#include <cmath>
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

namespace {

struct Args {
  std::size_t bytes = 512ull << 20;
  int threads = 0;
  int chase_iters = 8'000'000;
  int stream_iters = 5;
  int graph_iters = 4'000'000;
  bool json = false;
  bool help = false;
  // Emulated dual-socket remote DRAM (for 1-node hosts / farm modeling).
  // Matches the NFS_US pattern in PD Job Acceleration: labeled emulation.
  bool emulate_remote = false;
  double remote_bw_mult = 0.55;   // triad throughput multiplier when remote
  double remote_lat_mult = 1.75;  // chase/graph latency multiplier when remote
};

void usage(const char* argv0) {
  std::cerr
      << "Usage: " << argv0 << " [options]\n"
      << "  --bytes N|Nm|Ng     working-set size (default 512M)\n"
      << "  --threads T         worker threads (default = nproc)\n"
      << "  --stream-iters K\n"
      << "  --chase-iters K\n"
      << "  --graph-iters K     FC-ish random edge walks\n"
      << "  --json              machine-readable one-line JSON\n"
      << "  --emulate-remote    apply remote DRAM tax (1-node / farm model)\n"
      << "  --remote-bw-mult X  triad multiplier when emulating (default 0.55)\n"
      << "  --remote-lat-mult X latency multiplier when emulating (default 1.75)\n"
      << "\nWrap with numactl on multi-socket hosts:\n"
      << "  numactl --cpunodebind=0 --membind=0 " << argv0 << " --bytes 1g --threads 8\n"
      << "  numactl --cpunodebind=0 --membind=1 " << argv0 << " --bytes 1g --threads 8\n";
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
    else if (arg == "--graph-iters") a.graph_iters = std::stoi(need("--graph-iters"));
    else if (arg == "--json") a.json = true;
    else if (arg == "--emulate-remote") a.emulate_remote = true;
    else if (arg == "--remote-bw-mult") a.remote_bw_mult = std::stod(need("--remote-bw-mult"));
    else if (arg == "--remote-lat-mult") a.remote_lat_mult = std::stod(need("--remote-lat-mult"));
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

void burn_ns(double ns) {
  // Busy-wait so we don't yield the CPU (closer to stalled load than sleep).
  if (ns <= 0) return;
  auto t0 = std::chrono::steady_clock::now();
  const double sec = ns * 1e-9;
  while (seconds_since(t0) < sec) {
    std::atomic_signal_fence(std::memory_order_seq_cst);
  }
}

double run_stream(std::size_t n, int threads, int iters, double bw_mult) {
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
      for (std::size_t i = lo; i < hi; ++i) {
        a[i] = b[i] + scalar * c[i];
      }
      // Emulated remote: tax after each pass proportional to bytes moved.
      if (bw_mult < 0.999) {
        const double bytes = static_cast<double>(hi - lo) * sizeof(double) * 3.0;
        // Ideal local time ~ bytes / peak; remote stretches by 1/bw_mult.
        // We approximate peak from a small calibration: assume ~50 GiB/s local
        // for tax sizing; actual reported BW still comes from wall time.
        const double ideal_s = bytes / (50.0 * 1024 * 1024 * 1024);
        const double extra_s = ideal_s * (1.0 / bw_mult - 1.0);
        burn_ns(extra_s * 1e9);
      }
    }
    volatile double sink = a[lo];
    (void)sink;
  };

  auto t0 = std::chrono::steady_clock::now();
  std::vector<std::thread> pool;
  pool.reserve(static_cast<std::size_t>(threads));
  for (int t = 0; t < threads; ++t) pool.emplace_back(worker, t);
  for (auto& th : pool) th.join();
  const double sec = seconds_since(t0);
  const double bytes = static_cast<double>(iters) * static_cast<double>(n) * sizeof(double) * 3.0;
  return (bytes / sec) / (1024.0 * 1024.0 * 1024.0);
}

double run_chase(std::size_t nodes, int iters, double lat_mult) {
  std::vector<std::uint32_t> next(nodes);
  for (std::size_t i = 0; i < nodes; ++i) next[i] = static_cast<std::uint32_t>(i);
  std::uint64_t state = 0x9e3779b97f4a7c15ULL;
  for (std::size_t i = nodes - 1; i > 0; --i) {
    state = state * 6364136223846793005ULL + 1;
    std::size_t j = state % (i + 1);
    std::swap(next[i], next[j]);
  }

  std::uint32_t idx = 0;
  auto t0 = std::chrono::steady_clock::now();
  if (lat_mult <= 1.001) {
    for (int i = 0; i < iters; ++i) idx = next[idx];
  } else {
    // Measure a short local baseline then apply tax per hop.
    // Simpler: after each hop, burn (lat_mult-1)*estimated_local_ns.
    // Use 40ns as nominal local DRAM hop for tax (conservative).
    const double extra = (lat_mult - 1.0) * 40.0;
    for (int i = 0; i < iters; ++i) {
      idx = next[idx];
      burn_ns(extra);
    }
  }
  const double sec = seconds_since(t0);
  volatile std::uint32_t sink = idx;
  (void)sink;
  return (sec * 1e9) / static_cast<double>(iters);
}

// FC-ish: shuffled cycle + cold payload touch (timing/netlist proxy).
double run_graph(std::size_t n_nodes, int iters, double lat_mult) {
  std::vector<std::uint32_t> next(n_nodes);
  std::vector<std::uint64_t> payload(n_nodes);
  for (std::size_t i = 0; i < n_nodes; ++i) {
    next[i] = static_cast<std::uint32_t>(i);
    payload[i] = i * 0x9e3779b97f4a7c15ULL;
  }
  std::uint64_t state = 0x123456789abcdef0ULL;
  for (std::size_t i = n_nodes - 1; i > 0; --i) {
    state = state * 6364136223846793005ULL + 1;
    std::size_t j = state % (i + 1);
    std::swap(next[i], next[j]);
  }

  std::uint32_t node = 0;
  std::uint64_t acc = 0;
  auto t0 = std::chrono::steady_clock::now();
  const double extra = (lat_mult > 1.001) ? (lat_mult - 1.0) * 35.0 : 0.0;
  for (int i = 0; i < iters; ++i) {
    node = next[node];
    acc += payload[node];
    if (extra > 0) burn_ns(extra);
  }
  const double sec = seconds_since(t0);
  volatile std::uint64_t sink = acc + node;
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

    const double bw_mult = args.emulate_remote ? args.remote_bw_mult : 1.0;
    const double lat_mult = args.emulate_remote ? args.remote_lat_mult : 1.0;

    std::size_t elems = args.bytes / (3 * sizeof(double));
    if (elems < 1024) elems = 1024;
    std::size_t chase_nodes = args.bytes / sizeof(std::uint32_t);
    if (chase_nodes < 4096) chase_nodes = 4096;
    std::size_t graph_nodes = args.bytes / (sizeof(std::uint32_t) + sizeof(std::uint64_t));
    if (graph_nodes < 4096) graph_nodes = 4096;

    const double gib_s = run_stream(elems, args.threads, args.stream_iters, bw_mult);
    const double chase_ns = run_chase(chase_nodes, args.chase_iters, lat_mult);
    const double graph_ns = run_graph(graph_nodes, args.graph_iters, lat_mult);

    // Composite score: higher is better. Normalize vs typical local.
    // wall proxy = stream_time_proxy + chase + graph (inverse of goodness).
    const double wall_proxy =
        (100.0 / std::max(gib_s, 0.1)) + (chase_ns / 10.0) + (graph_ns / 10.0);

    if (args.json) {
      std::printf(
          "{\"threads\":%d,\"bytes\":%zu,\"numa_nodes\":%d,\"emulate_remote\":%s,"
          "\"remote_bw_mult\":%.4f,\"remote_lat_mult\":%.4f,"
          "\"triad_gib_s\":%.6f,\"chase_ns\":%.6f,\"graph_ns\":%.6f,"
          "\"wall_proxy\":%.6f,\"affinity\":\"%s\"}\n",
          args.threads, args.bytes, numa_node_count(),
          args.emulate_remote ? "true" : "false", bw_mult, lat_mult, gib_s, chase_ns,
          graph_ns, wall_proxy, cpu_affinity_string().c_str());
      return 0;
    }

    std::cout << "NUMA-EDA-Bench mem microbench\n";
    std::cout << "  threads=" << args.threads << " stream_bytes≈" << (elems * 3 * sizeof(double))
              << " chase_nodes=" << chase_nodes << " graph_nodes=" << graph_nodes << "\n";
    std::cout << "  CPU affinity: " << cpu_affinity_string() << "\n";
    std::cout << "  NUMA nodes (sysfs): " << numa_node_count() << "\n";
    if (args.emulate_remote) {
      std::cout << "  mode: EMULATED REMOTE (bw×" << bw_mult << " lat×" << lat_mult << ")\n";
    } else {
      std::cout << "  mode: local / unbound\n";
    }
    std::cout << "  STREAM-triad bandwidth: " << gib_s << " GiB/s\n";
    std::cout << "  pointer-chase latency:  " << chase_ns << " ns/hop\n";
    std::cout << "  graph-walk latency:     " << graph_ns << " ns/hop\n";
    std::cout << "  wall_proxy (lower better): " << wall_proxy << "\n";
    std::cout << "Done.\n";
    return 0;
  } catch (const std::exception& e) {
    std::cerr << "error: " << e.what() << "\n";
    usage(argv[0]);
    return 1;
  }
}
