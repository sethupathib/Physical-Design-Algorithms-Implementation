#pragma once
#include <string>
#include <vector>
#include "metalfill/density.hpp"
#include "metalfill/raster.hpp"
#include "metalfill/rules.hpp"

namespace mf {

enum class ViolationType {
    MinDensity,
    MaxDensity,
    Gradient,
    Spacing,
    MinArea,
};

struct Violation {
    ViolationType type;
    int ix = 0, iy = 0;      // offending tile (or -1 for shape-level checks)
    double value = 0.0;      // measured value
    double limit = 0.0;      // rule limit
    std::string message;
};

struct DrcReport {
    std::vector<Violation> violations;
    bool clean() const { return violations.empty(); }
    int count(ViolationType t) const;
};

// Runs density (min/max), gradient, keep-out spacing and min-area checks over
// the combined (existing + fill) layout for one layer.
//   total_occ : existing geometry OR fill footprints (post-fill occupancy)
//   blocked   : keep-out mask (existing geometry dilated by keepout)
//   fill_occ  : fill footprints only (for spacing check)
DrcReport run_drc(const SummedAreaTable& total_sat, const Grid& blocked,
                  const Grid& fill_occ, int win_cells, int step_cells,
                  const FillRule& rule, double dbu_per_um, dbu cell);

}  // namespace mf
