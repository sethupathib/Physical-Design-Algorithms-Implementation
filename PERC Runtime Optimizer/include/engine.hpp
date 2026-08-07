#pragma once

#include "design.hpp"
#include "metadata.hpp"

#include <string>
#include <unordered_map>
#include <vector>

namespace perc {

struct RunReport {
  std::string mode;
  std::vector<Violation> violations;
  double elapsed_s = 0.0;
  std::unordered_map<std::string, int> violation_counts;
  std::unordered_map<std::string, double> metrics;  // e.g. cache_hits, scopes_ran
};

// Naïve full-chip: every rule on entire design, every time.
RunReport run_baseline(const Design& design);

// ROI pruning: only ESD-relevant nets/devices + pad P2P/CD.
RunReport run_roi(const Design& design);

// Hierarchical: per-block floating-gate + chip-level ESD/P2P/CD.
RunReport run_hierarchical(const Design& design);

// Incremental: reuse cached block/chip results when fingerprints match.
RunReport run_incremental(const Design& design, MetadataStore& store, bool warm = false);

// Parallel pad-pair P2P + CD using std::async worker pool.
RunReport run_parallel(const Design& design, unsigned workers = 0);

// Full optimized stack: hierarchical ROI + incremental + parallel P2P.
RunReport run_optimized(const Design& design, MetadataStore& store, unsigned workers = 0,
                        bool warm = false);

}  // namespace perc
