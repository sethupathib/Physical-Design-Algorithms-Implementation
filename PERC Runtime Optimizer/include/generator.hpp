#pragma once

#include "design.hpp"

#include <cstddef>

namespace perc {

struct GenConfig {
  int n_pads = 32;
  int n_blocks = 8;
  int devices_per_block = 400;
  double missing_clamp_rate = 0.05;
  unsigned seed = 42;
  double r_mesh_density = 0.35;
};

Design generate_design(const GenConfig& cfg);
// Touch MOSFET drains inside a limited number of blocks (for incremental demos).
Design mutate_eco(const Design& design, double touch_fraction = 0.05, unsigned seed = 7,
                  int max_blocks_to_touch = 1);

}  // namespace perc
