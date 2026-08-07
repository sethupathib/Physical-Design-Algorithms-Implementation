#include "engine.hpp"

#include "checks.hpp"

#include <algorithm>
#include <chrono>
#include <future>
#include <thread>
#include <unordered_set>

namespace perc {
namespace {

using Clock = std::chrono::steady_clock;

double seconds_since(Clock::time_point t0) {
  return std::chrono::duration<double>(Clock::now() - t0).count();
}

void append(std::vector<Violation>& dst, std::vector<Violation>&& src) {
  dst.insert(dst.end(), std::make_move_iterator(src.begin()), std::make_move_iterator(src.end()));
}

RunReport finish(const std::string& mode, std::vector<Violation> viols, double elapsed,
                 std::unordered_map<std::string, double> metrics = {}) {
  RunReport r;
  r.mode = mode;
  r.elapsed_s = elapsed;
  r.violation_counts = summarize(viols);
  r.violations = std::move(viols);
  r.metrics = std::move(metrics);
  return r;
}

std::vector<std::pair<std::string, std::string>> all_pad_pairs(const Design& design) {
  std::vector<std::pair<std::string, std::string>> pairs;
  pairs.reserve(design.pad_nets.size() * 2);
  for (const auto& p : design.pad_nets) {
    pairs.emplace_back(p, "VSS");
    pairs.emplace_back(p, "VDD");
  }
  return pairs;
}

}  // namespace

RunReport run_baseline(const Design& design) {
  const auto t0 = Clock::now();
  std::vector<Violation> viols;
  append(viols, check_esd_clamps(design));
  append(viols, check_floating_gates(design));
  append(viols, check_p2p_resistance(design));
  append(viols, check_current_density_paths(design));
  return finish("baseline", std::move(viols), seconds_since(t0),
                {{"devices", static_cast<double>(design.devices.size())},
                 {"nets", static_cast<double>(design.nets.size())},
                 {"r_edges", static_cast<double>(design.rgraph.edge_count())}});
}

RunReport run_roi(const Design& design) {
  const auto t0 = Clock::now();
  const auto roi = esd_roi_nets(design);

  // Floating-gate only on devices that touch ROI nets (still catches FLOAT_* near rails/pads),
  // plus a cheap scan limited to devices whose gate is FLOAT_* for the educational demo.
  std::unordered_set<std::string> scope;
  for (const auto& kv : design.devices) {
    if (kv.second.kind != DeviceKind::Mosfet) continue;
    auto git = kv.second.terminals.find("g");
    if (git != kv.second.terminals.end() && git->second.rfind("FLOAT_", 0) == 0) {
      scope.insert(kv.first);
      continue;
    }
    for (const auto& t : kv.second.terminals) {
      if (roi.count(t.second)) {
        scope.insert(kv.first);
        break;
      }
    }
  }

  std::vector<Violation> viols;
  append(viols, check_esd_clamps(design));  // already pad-scoped
  append(viols, check_floating_gates(design, &scope));
  append(viols, check_p2p_resistance(design));
  append(viols, check_current_density_paths(design));
  return finish("roi", std::move(viols), seconds_since(t0),
                {{"roi_nets", static_cast<double>(roi.size())},
                 {"fg_scope_devices", static_cast<double>(scope.size())}});
}

RunReport run_hierarchical(const Design& design) {
  const auto t0 = Clock::now();
  std::vector<Violation> viols;

  // Chip-level ESD / P2P / CD
  append(viols, check_esd_clamps(design));
  append(viols, check_p2p_resistance(design));
  append(viols, check_current_density_paths(design));

  // Per-block floating gates with a shared writer index (build once).
  const FloatingGateIndex fg = build_floating_gate_index(design);
  for (const auto& bkv : design.blocks) {
    append(viols, check_floating_gates_indexed(design, fg, &bkv.second.devices));
  }

  return finish("hierarchical", std::move(viols), seconds_since(t0),
                {{"blocks", static_cast<double>(design.blocks.size())}});
}

RunReport run_incremental(const Design& design, MetadataStore& store, bool warm) {
  const auto t0 = Clock::now();
  std::vector<Violation> viols;
  double cache_hits = 0;
  double cache_miss = 0;

  std::unordered_set<std::string> touched(design.touched_blocks.begin(),
                                          design.touched_blocks.end());
  const bool eco_mode = !touched.empty();

  auto run_scope = [&](const std::string& scope, bool known_untouched, auto&& fp_fn,
                       auto&& compute) {
    if (known_untouched) {
      if (const CheckResult* hit = store.latest(scope)) {
        append(viols, std::vector<Violation>(hit->violations));
        cache_hits += 1;
        return;
      }
    }
    const std::string fp = fp_fn();
    if (const CheckResult* hit = store.get(scope, fp)) {
      append(viols, std::vector<Violation>(hit->violations));
      cache_hits += 1;
      return;
    }
    CheckResult cr;
    cr.scope = scope;
    cr.fingerprint = fp;
    cr.violations = compute();
    append(viols, std::vector<Violation>(cr.violations));
    store.put(std::move(cr));
    cache_miss += 1;
  };

  // Chip-level ESD/P2P/CD — fingerprint ignores core logic ECOs.
  run_scope(
      "chip_esd", eco_mode || warm,
      [&] { return design.esd_fingerprint(); },
      [&] {
        std::vector<Violation> v;
        append(v, check_esd_clamps(design));
        append(v, check_p2p_resistance(design));
        append(v, check_current_density_paths(design));
        return v;
      });

  for (const auto& bkv : design.blocks) {
    const bool untouched = eco_mode && !touched.count(bkv.first);
    run_scope(
        bkv.first, untouched || (warm && !eco_mode),
        [&] { return design.fingerprint(&bkv.second.nets); },
        [&] { return check_floating_gates(design, &bkv.second.devices); });
  }

  return finish("incremental", std::move(viols), seconds_since(t0),
                {{"cache_hits", cache_hits},
                 {"cache_misses", cache_miss},
                 {"cache_size", static_cast<double>(store.size())}});
}

RunReport run_parallel(const Design& design, unsigned workers) {
  const auto t0 = Clock::now();
  if (workers == 0) {
    workers = std::max(1u, std::thread::hardware_concurrency());
  }

  std::vector<Violation> viols;
  append(viols, check_esd_clamps(design));
  append(viols, check_floating_gates(design));

  auto pairs = all_pad_pairs(design);
  const unsigned n = static_cast<unsigned>(pairs.size());
  const unsigned chunk = std::max(1u, (n + workers - 1) / workers);

  std::vector<std::future<std::vector<Violation>>> futs;
  futs.reserve(workers);
  for (unsigned w = 0; w < workers; ++w) {
    const unsigned begin = w * chunk;
    if (begin >= n) break;
    const unsigned end = std::min(n, begin + chunk);
    futs.push_back(std::async(std::launch::async, [&design, pairs, begin, end] {
      std::vector<std::pair<std::string, std::string>> slice(pairs.begin() + begin,
                                                             pairs.begin() + end);
      std::vector<Violation> local;
      append(local, check_p2p_resistance(design, &slice));
      // CD only for pads represented in this slice (unique first endpoints)
      std::vector<std::string> pads;
      for (const auto& pr : slice) {
        if (pr.second == "VSS") pads.push_back(pr.first);
      }
      append(local, check_current_density_paths(design, &pads));
      return local;
    }));
  }

  for (auto& f : futs) append(viols, f.get());

  return finish("parallel", std::move(viols), seconds_since(t0),
                {{"workers", static_cast<double>(workers)},
                 {"pad_pairs", static_cast<double>(pairs.size())}});
}

RunReport run_optimized(const Design& design, MetadataStore& store, unsigned workers, bool warm) {
  const auto t0 = Clock::now();
  if (workers == 0) {
    workers = std::max(1u, std::thread::hardware_concurrency());
  }

  std::vector<Violation> viols;
  double cache_hits = 0;
  double cache_miss = 0;

  std::unordered_set<std::string> touched(design.touched_blocks.begin(),
                                          design.touched_blocks.end());
  const bool eco_mode = !touched.empty();

  auto run_scope = [&](const std::string& scope, bool known_untouched, auto&& fp_fn,
                       auto&& compute) {
    if (known_untouched || (warm && !eco_mode)) {
      if (const CheckResult* hit = store.latest(scope)) {
        append(viols, std::vector<Violation>(hit->violations));
        cache_hits += 1;
        return;
      }
    }
    const std::string fp = fp_fn();
    if (const CheckResult* hit = store.get(scope, fp)) {
      append(viols, std::vector<Violation>(hit->violations));
      cache_hits += 1;
      return;
    }
    CheckResult cr;
    cr.scope = scope;
    cr.fingerprint = fp;
    cr.violations = compute();
    append(viols, std::vector<Violation>(cr.violations));
    store.put(std::move(cr));
    cache_miss += 1;
  };

  run_scope(
      "chip_esd_opt", eco_mode || warm,
      [&] { return design.esd_fingerprint(); },
      [&] {
        std::vector<Violation> v;
        append(v, check_esd_clamps(design));

        auto pairs = all_pad_pairs(design);
        const unsigned n = static_cast<unsigned>(pairs.size());
        const unsigned chunk = std::max(1u, (n + workers - 1) / workers);
        std::vector<std::future<std::vector<Violation>>> futs;
        for (unsigned w = 0; w < workers; ++w) {
          const unsigned begin = w * chunk;
          if (begin >= n) break;
          const unsigned end = std::min(n, begin + chunk);
          futs.push_back(std::async(std::launch::async, [&design, pairs, begin, end] {
            std::vector<std::pair<std::string, std::string>> slice(pairs.begin() + begin,
                                                                   pairs.begin() + end);
            std::vector<Violation> local;
            append(local, check_p2p_resistance(design, &slice));
            std::vector<std::string> pads;
            for (const auto& pr : slice) {
              if (pr.second == "VSS") pads.push_back(pr.first);
            }
            append(local, check_current_density_paths(design, &pads));
            return local;
          }));
        }
        for (auto& f : futs) append(v, f.get());
        return v;
      });

  for (const auto& bkv : design.blocks) {
    const bool untouched = eco_mode && !touched.count(bkv.first);
    run_scope(
        bkv.first + "_fg", untouched || (warm && !eco_mode),
        [&] { return design.fingerprint(&bkv.second.nets); },
        [&] { return check_floating_gates(design, &bkv.second.devices); });
  }

  return finish("optimized", std::move(viols), seconds_since(t0),
                {{"cache_hits", cache_hits},
                 {"cache_misses", cache_miss},
                 {"workers", static_cast<double>(workers)}});
}

}  // namespace perc
