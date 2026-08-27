// signoff_proxy — PD/signoff-shaped CPU microbench (NOT Fusion Compiler).
// Designed so feedback-directed optimization has something to win:
//   - large switch dispatch (report/rule opcodes) with skewed hot cases
//   - many cold helper functions (I-cache / layout opportunity)
//   - timing-graph relax + hash lookups + heap legalize
//
// Build flavors: baseline | pgo-gen | pgo-use | sample-autofdo
#include <chrono>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <queue>
#include <string>
#include <unordered_map>
#include <vector>

struct Edge {
  int to;
  float delay;
};

struct Node {
  float arrival;
  float required;
  int fanout;
};

static uint64_t rng_state = 0xC0FFEEULL;
static inline uint64_t rng() {
  rng_state ^= rng_state << 13;
  rng_state ^= rng_state >> 7;
  rng_state ^= rng_state << 17;
  return rng_state;
}

static inline float frand() { return float(rng() & 0xffff) / 65535.0f; }

// --- Cold helpers (intentionally many; PGO/AutoFDO can keep them out of I-cache) ---
#define COLD_FN(N)                                                             \
  __attribute__((noinline, cold)) static uint64_t cold_helper_##N(uint64_t x) { \
    uint64_t y = x ^ (0x9E3779B97F4A7C15ULL * (N + 1));                        \
    for (int i = 0; i < 8; ++i) y = (y * 6364136223846793005ULL) + (N + i);    \
    return y;                                                                  \
  }

COLD_FN(0) COLD_FN(1) COLD_FN(2) COLD_FN(3) COLD_FN(4) COLD_FN(5) COLD_FN(6) COLD_FN(7)
COLD_FN(8) COLD_FN(9) COLD_FN(10) COLD_FN(11) COLD_FN(12) COLD_FN(13) COLD_FN(14) COLD_FN(15)
COLD_FN(16) COLD_FN(17) COLD_FN(18) COLD_FN(19) COLD_FN(20) COLD_FN(21) COLD_FN(22) COLD_FN(23)
COLD_FN(24) COLD_FN(25) COLD_FN(26) COLD_FN(27) COLD_FN(28) COLD_FN(29) COLD_FN(30) COLD_FN(31)

using ColdFn = uint64_t (*)(uint64_t);
static ColdFn cold_table[32] = {
    cold_helper_0,  cold_helper_1,  cold_helper_2,  cold_helper_3,  cold_helper_4,
    cold_helper_5,  cold_helper_6,  cold_helper_7,  cold_helper_8,  cold_helper_9,
    cold_helper_10, cold_helper_11, cold_helper_12, cold_helper_13, cold_helper_14,
    cold_helper_15, cold_helper_16, cold_helper_17, cold_helper_18, cold_helper_19,
    cold_helper_20, cold_helper_21, cold_helper_22, cold_helper_23, cold_helper_24,
    cold_helper_25, cold_helper_26, cold_helper_27, cold_helper_28, cold_helper_29,
    cold_helper_30, cold_helper_31};

// Hot opcode handlers — skewed: 0..3 dominate (~92%), rest are rare.
__attribute__((noinline)) static uint64_t op_setup_check(uint64_t a, float slack) {
  return slack < 0 ? (a + 1) : a;
}
__attribute__((noinline)) static uint64_t op_hold_check(uint64_t a, float slack) {
  return slack < 0.02f ? (a + 3) : a;
}
__attribute__((noinline)) static uint64_t op_maxtran(uint64_t a, int fanout) {
  return fanout > 16 ? (a + 5) : a;
}
__attribute__((noinline)) static uint64_t op_drc(uint64_t a, int fanout) {
  return (fanout & 7) == 0 ? (a + 7) : a;
}
__attribute__((noinline)) static uint64_t op_antenna(uint64_t a) { return a + 11; }
__attribute__((noinline)) static uint64_t op_cong(uint64_t a) { return a ^ 0x55; }
__attribute__((noinline)) static uint64_t op_fatal(uint64_t a) { return a | 0x1000; }
__attribute__((noinline)) static uint64_t op_lvs(uint64_t a) { return a + 13; }
__attribute__((noinline)) static uint64_t op_antenna2(uint64_t a) { return a + 17; }
__attribute__((noinline)) static uint64_t op_erc(uint64_t a) { return a + 19; }
__attribute__((noinline)) static uint64_t op_noise(uint64_t a) { return a + 23; }
__attribute__((noinline)) static uint64_t op_em(uint64_t a) { return a + 29; }
__attribute__((noinline)) static uint64_t op_ir(uint64_t a) { return a + 31; }
__attribute__((noinline)) static uint64_t op_misc(uint64_t a) { return a + 37; }

// Skewed dispatch — without PGO the compiler cannot know 0..3 are hot.
__attribute__((noinline)) static uint64_t rule_dispatch(const std::vector<Node>& nodes,
                                                        int nops) {
  uint64_t acc = 0;
  const int n = (int)nodes.size();
  for (int i = 0; i < nops; ++i) {
    int idx = int(rng() % n);
    const Node& nd = nodes[idx];
    float slack = nd.required - nd.arrival;
    // Zipf-ish opcode: 0=50%, 1=25%, 2=12.5%, 3=6.25%, else rare
    uint64_t r = rng();
    int op;
    if ((r & 1) == 0)
      op = 0;
    else if ((r & 3) == 1)
      op = 1;
    else if ((r & 7) == 3)
      op = 2;
    else if ((r & 15) == 7)
      op = 3;
    else
      op = 4 + int(r % 10);

    switch (op) {
      case 0: acc = op_setup_check(acc, slack); break;
      case 1: acc = op_hold_check(acc, slack); break;
      case 2: acc = op_maxtran(acc, nd.fanout); break;
      case 3: acc = op_drc(acc, nd.fanout); break;
      case 4: acc = op_antenna(acc); break;
      case 5: acc = op_cong(acc); break;
      case 6: acc = op_fatal(acc); break;
      case 7: acc = op_lvs(acc); break;
      case 8: acc = op_antenna2(acc); break;
      case 9: acc = op_erc(acc); break;
      case 10: acc = op_noise(acc); break;
      case 11: acc = op_em(acc); break;
      case 12: acc = op_ir(acc); break;
      default: acc = op_misc(acc); break;
    }
    // Rare cold call (~3%)
    if ((r % 100) < 3) acc ^= cold_table[r & 31](acc);
  }
  return acc;
}

__attribute__((noinline)) static double timing_relax(
    std::vector<Node>& nodes, const std::vector<std::vector<Edge>>& adj, int rounds) {
  const int n = (int)nodes.size();
  double checksum = 0.0;
  for (int r = 0; r < rounds; ++r) {
    for (int u = 0; u < n; ++u) {
      float a = nodes[u].arrival;
      for (const Edge& e : adj[u]) {
        float cand = a + e.delay;
        if (cand > nodes[e.to].arrival) nodes[e.to].arrival = cand;
      }
    }
    for (int u = n - 1; u >= 0; --u) {
      float req = nodes[u].required;
      for (const Edge& e : adj[u]) {
        float cand = req - e.delay;
        if (cand < nodes[e.to].required) nodes[e.to].required = cand;
      }
    }
    if ((r & 7) == 0) {
      for (int u = 0; u < n; u += 17) checksum += nodes[u].arrival - nodes[u].required;
    }
  }
  return checksum;
}

__attribute__((noinline)) static uint64_t netlist_lookup_pass(
    const std::unordered_map<std::string, int>& name_to_id,
    const std::vector<std::string>& queries) {
  uint64_t hits = 0;
  for (const auto& q : queries) {
    auto it = name_to_id.find(q);
    if (it != name_to_id.end())
      hits += (uint64_t)it->second;
    else if (!q.empty() && (q[0] == 'X' || q[0] == 'Z'))
      hits ^= q.size();
    else
      hits += 1;
  }
  return hits;
}

__attribute__((noinline)) static double heap_legalize(std::vector<Node>& nodes, int iters) {
  using P = std::pair<float, int>;
  std::priority_queue<P, std::vector<P>, std::greater<P>> pq;
  for (int i = 0; i < (int)nodes.size(); ++i) pq.push({nodes[i].arrival, i});
  double acc = 0.0;
  for (int it = 0; it < iters && !pq.empty(); ++it) {
    auto [a, i] = pq.top();
    pq.pop();
    float bump = 0.001f * float((i * 17) & 255);
    nodes[i].arrival = a + bump;
    acc += nodes[i].arrival;
    if ((it & 3) == 0) pq.push({nodes[i].arrival, i});
  }
  return acc;
}

struct Config {
  int nodes = 12000;
  int edges_per = 6;
  int relax_rounds = 50;
  int lookup_queries = 250000;
  int heap_iters = 80000;
  int dispatch_ops = 2000000;
  uint64_t seed = 42;
};

static void usage(const char* argv0) {
  std::fprintf(stderr,
               "Usage: %s [--nodes N] [--rounds R] [--queries Q] [--ops O] [--seed S] [--json]\n"
               "  PD/signoff-shaped proxy for PGO / AutoFDO. NOT Fusion Compiler.\n",
               argv0);
}

int main(int argc, char** argv) {
  Config cfg;
  bool json = false;
  for (int i = 1; i < argc; ++i) {
    if (!std::strcmp(argv[i], "--nodes") && i + 1 < argc)
      cfg.nodes = std::atoi(argv[++i]);
    else if (!std::strcmp(argv[i], "--rounds") && i + 1 < argc)
      cfg.relax_rounds = std::atoi(argv[++i]);
    else if (!std::strcmp(argv[i], "--queries") && i + 1 < argc)
      cfg.lookup_queries = std::atoi(argv[++i]);
    else if (!std::strcmp(argv[i], "--ops") && i + 1 < argc)
      cfg.dispatch_ops = std::atoi(argv[++i]);
    else if (!std::strcmp(argv[i], "--seed") && i + 1 < argc)
      cfg.seed = (uint64_t)std::strtoull(argv[++i], nullptr, 10);
    else if (!std::strcmp(argv[i], "--json"))
      json = true;
    else if (!std::strcmp(argv[i], "--help") || !std::strcmp(argv[i], "-h")) {
      usage(argv[0]);
      return 0;
    } else {
      usage(argv[0]);
      return 2;
    }
  }
  rng_state = cfg.seed ? cfg.seed : 1;

  std::vector<Node> nodes(cfg.nodes);
  std::vector<std::vector<Edge>> adj(cfg.nodes);
  for (int i = 0; i < cfg.nodes; ++i) {
    nodes[i].arrival = frand();
    nodes[i].required = 10.0f + frand() * 5.0f;
    nodes[i].fanout = int(rng() % 32);
    int deg = cfg.edges_per + int(rng() % 3);
    adj[i].reserve(deg);
    for (int k = 0; k < deg; ++k) {
      int to = int(rng() % cfg.nodes);
      adj[i].push_back({to, 0.01f + frand() * 0.2f});
    }
  }

  std::unordered_map<std::string, int> name_to_id;
  name_to_id.reserve(cfg.nodes * 2);
  std::vector<std::string> names;
  names.reserve(cfg.nodes);
  for (int i = 0; i < cfg.nodes; ++i) {
    char buf[64];
    std::snprintf(buf, sizeof(buf), "u%d/inst_%d", i % 64, i);
    names.emplace_back(buf);
    name_to_id.emplace(names.back(), i);
  }
  std::vector<std::string> queries;
  queries.reserve(cfg.lookup_queries);
  for (int i = 0; i < cfg.lookup_queries; ++i) {
    if ((rng() % 100) < 92)
      queries.push_back(names[rng() % names.size()]);
    else {
      char buf[64];
      std::snprintf(buf, sizeof(buf), "Xmiss_%llu", (unsigned long long)rng());
      queries.emplace_back(buf);
    }
  }

  auto t0 = std::chrono::steady_clock::now();
  double c1 = timing_relax(nodes, adj, cfg.relax_rounds);
  uint64_t c2 = netlist_lookup_pass(name_to_id, queries);
  uint64_t c4 = rule_dispatch(nodes, cfg.dispatch_ops);
  double c3 = heap_legalize(nodes, cfg.heap_iters);
  auto t1 = std::chrono::steady_clock::now();
  double ms = std::chrono::duration<double, std::milli>(t1 - t0).count();

  volatile double sink = c1 + c3 + double(c2) + double(c4);
  (void)sink;

  if (json) {
    std::printf(
        "{\"wall_ms\":%.3f,\"nodes\":%d,\"rounds\":%d,\"queries\":%d,\"ops\":%d,"
        "\"checksum\":%.6g,\"dispatch\":%llu,\"seed\":%llu}\n",
        ms, cfg.nodes, cfg.relax_rounds, cfg.lookup_queries, cfg.dispatch_ops, c1 + c3,
        (unsigned long long)c4, (unsigned long long)cfg.seed);
  } else {
    std::printf("signoff_proxy wall_ms=%.3f nodes=%d rounds=%d ops=%d\n", ms, cfg.nodes,
                cfg.relax_rounds, cfg.dispatch_ops);
  }
  return 0;
}
