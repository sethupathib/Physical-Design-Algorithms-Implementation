#include "engine.hpp"
#include "generator.hpp"

#include <cstdlib>
#include <iomanip>
#include <iostream>
#include <string>

namespace {

void print_report(const perc::RunReport& r) {
  std::cout << std::left << std::setw(14) << r.mode
            << "  time_s=" << std::fixed << std::setprecision(4) << r.elapsed_s
            << "  violations=" << r.violations.size();
  if (!r.violation_counts.empty()) {
    std::cout << "  [";
    bool first = true;
    for (const auto& kv : r.violation_counts) {
      if (!first) std::cout << ", ";
      first = false;
      std::cout << kv.first << '=' << kv.second;
    }
    std::cout << "]";
  }
  if (!r.metrics.empty()) {
    std::cout << "  metrics{";
    bool first = true;
    for (const auto& kv : r.metrics) {
      if (!first) std::cout << ", ";
      first = false;
      std::cout << kv.first << '=' << kv.second;
    }
    std::cout << "}";
  }
  std::cout << '\n';
}

void usage(const char* argv0) {
  std::cerr
      << "PERC Runtime Optimizer (C++)\n"
      << "Usage: " << argv0
      << " [--pads N] [--blocks N] [--devices N] [--workers N] [--eco] [--bench]\n";
}

}  // namespace

int main(int argc, char** argv) {
  perc::GenConfig cfg;
  unsigned workers = 0;
  bool do_eco = false;
  bool do_bench = false;

  for (int i = 1; i < argc; ++i) {
    const std::string a = argv[i];
    auto need = [&](const char* flag) -> int {
      if (i + 1 >= argc) {
        std::cerr << "Missing value for " << flag << '\n';
        std::exit(2);
      }
      return std::atoi(argv[++i]);
    };
    if (a == "--pads") cfg.n_pads = need("--pads");
    else if (a == "--blocks") cfg.n_blocks = need("--blocks");
    else if (a == "--devices") cfg.devices_per_block = need("--devices");
    else if (a == "--workers") workers = static_cast<unsigned>(need("--workers"));
    else if (a == "--eco") do_eco = true;
    else if (a == "--bench") do_bench = true;
    else if (a == "--help" || a == "-h") {
      usage(argv[0]);
      return 0;
    } else {
      std::cerr << "Unknown arg: " << a << '\n';
      usage(argv[0]);
      return 2;
    }
  }

  if (do_bench) {
    // Larger default for timing comparisons (P2P/CD heavy)
    if (cfg.devices_per_block == 400 && cfg.n_pads == 32) {
      cfg.n_pads = 256;
      cfg.n_blocks = 16;
      cfg.devices_per_block = 500;
    }
  }

  std::cout << "Generating design pads=" << cfg.n_pads << " blocks=" << cfg.n_blocks
            << " devices/block=" << cfg.devices_per_block << " ...\n";
  perc::Design design = perc::generate_design(cfg);
  std::cout << "Design " << design.name << " devices=" << design.devices.size()
            << " nets=" << design.nets.size() << " r_edges=" << design.rgraph.edge_count()
            << '\n';

  print_report(perc::run_baseline(design));
  print_report(perc::run_roi(design));
  print_report(perc::run_hierarchical(design));
  print_report(perc::run_parallel(design, workers));

  perc::MetadataStore store;
  // Cold incremental (populate cache)
  print_report(perc::run_incremental(design, store, false));
  // Warm incremental (should hit cache)
  print_report(perc::run_incremental(design, store, true));

  perc::MetadataStore opt_store;
  print_report(perc::run_optimized(design, opt_store, workers, false));
  print_report(perc::run_optimized(design, opt_store, workers, true));

  if (do_eco) {
    std::cout << "\n--- After ECO (5% MOSFET drains touched) ---\n";
    perc::Design eco = perc::mutate_eco(design, 0.05, 7, /*max_blocks_to_touch=*/1);
    std::cout << "Touched blocks:";
    for (const auto& b : eco.touched_blocks) std::cout << ' ' << b;
    std::cout << '\n';
    print_report(perc::run_baseline(eco));
    // Reuse prior store: unchanged block fingerprints should hit.
    print_report(perc::run_incremental(eco, store, true));
    print_report(perc::run_optimized(eco, opt_store, workers, true));
  }

  return 0;
}
