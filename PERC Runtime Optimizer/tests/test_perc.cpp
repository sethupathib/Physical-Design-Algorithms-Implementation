#include "checks.hpp"
#include "engine.hpp"
#include "generator.hpp"

#include <cassert>
#include <cmath>
#include <iostream>

static int g_failed = 0;

#define EXPECT(cond)                                                       \
  do {                                                                     \
    if (!(cond)) {                                                         \
      std::cerr << "FAIL " << __FILE__ << ":" << __LINE__ << " " << #cond  \
                << '\n';                                                   \
      ++g_failed;                                                          \
    }                                                                      \
  } while (0)

int main() {
  perc::GenConfig cfg;
  cfg.n_pads = 16;
  cfg.n_blocks = 4;
  cfg.devices_per_block = 50;
  cfg.missing_clamp_rate = 0.1;
  cfg.seed = 1;

  perc::Design d = perc::generate_design(cfg);
  EXPECT(!d.devices.empty());
  EXPECT(!d.pad_nets.empty());
  EXPECT(d.rgraph.edge_count() > 0);

  auto clamps = perc::check_esd_clamps(d);
  EXPECT(!clamps.empty());  // missing_clamp_rate > 0

  auto p2p = perc::check_p2p_resistance(d);
  // Missing clamps produce high R → P2P violations expected
  EXPECT(!p2p.empty());

  auto base = perc::run_baseline(d);
  auto roi = perc::run_roi(d);
  auto hier = perc::run_hierarchical(d);
  EXPECT(base.violations.size() == hier.violations.size());
  // ROI floating-gate scope may differ slightly; ESD/P2P counts should match baseline rule set presence
  EXPECT(base.violation_counts.count("ESD_CLAMP_MISSING"));
  EXPECT(roi.violation_counts.count("ESD_CLAMP_MISSING"));

  perc::MetadataStore store;
  auto cold = perc::run_incremental(d, store, false);
  auto warm = perc::run_incremental(d, store, true);
  EXPECT(warm.metrics.at("cache_hits") > 0);
  EXPECT(warm.elapsed_s <= cold.elapsed_s * 1.5 + 0.05);

  perc::Design eco = perc::mutate_eco(d, 0.2, 3, /*max_blocks_to_touch=*/1);
  EXPECT(!eco.touched_blocks.empty());
  auto eco_inc = perc::run_incremental(eco, store, true);
  EXPECT(eco_inc.metrics.at("cache_hits") > 0);

  auto par = perc::run_parallel(d, 2);
  EXPECT(par.violations.size() == base.violations.size());

  if (g_failed) {
    std::cerr << g_failed << " assertion(s) failed\n";
    return 1;
  }
  std::cout << "All tests passed\n";
  return 0;
}
