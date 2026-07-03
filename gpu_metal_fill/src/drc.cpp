#include "metalfill/drc.hpp"

#include <cmath>
#include <sstream>

namespace mf {

int DrcReport::count(ViolationType t) const {
    int c = 0;
    for (const auto& v : violations)
        if (v.type == t) ++c;
    return c;
}

DrcReport run_drc(const SummedAreaTable& total_sat, const Grid& blocked, const Grid& fill_occ,
                  int win_cells, int step_cells, const FillRule& rule, double dbu_per_um,
                  dbu cell) {
    DrcReport rep;
    DensityMap dm = compute_density(total_sat, win_cells, step_cells);

    // Density min / max per window.
    for (const auto& w : dm.tiles) {
        if (w.density < rule.min_density - 1e-9) {
            std::ostringstream os;
            os << rule.name << " window (" << w.ix << "," << w.iy << ") density "
               << w.density << " < min " << rule.min_density;
            rep.violations.push_back({ViolationType::MinDensity, w.ix, w.iy, w.density,
                                      rule.min_density, os.str()});
        }
        if (w.density > rule.max_density + 1e-9) {
            std::ostringstream os;
            os << rule.name << " window (" << w.ix << "," << w.iy << ") density "
               << w.density << " > max " << rule.max_density;
            rep.violations.push_back({ViolationType::MaxDensity, w.ix, w.iy, w.density,
                                      rule.max_density, os.str()});
        }
    }

    // Density gradient between adjacent windows.
    if (rule.max_gradient > 0) {
        for (int ty = 0; ty < dm.ntiles_y; ++ty) {
            for (int tx = 0; tx < dm.ntiles_x; ++tx) {
                double d = dm.at(tx, ty).density;
                if (tx + 1 < dm.ntiles_x) {
                    double g = std::fabs(d - dm.at(tx + 1, ty).density);
                    if (g > rule.max_gradient + 1e-9) {
                        std::ostringstream os;
                        os << rule.name << " gradient " << g << " > " << rule.max_gradient
                           << " between (" << tx << "," << ty << ") and (" << tx + 1 << "," << ty
                           << ")";
                        rep.violations.push_back(
                            {ViolationType::Gradient, tx, ty, g, rule.max_gradient, os.str()});
                    }
                }
                if (ty + 1 < dm.ntiles_y) {
                    double g = std::fabs(d - dm.at(tx, ty + 1).density);
                    if (g > rule.max_gradient + 1e-9) {
                        std::ostringstream os;
                        os << rule.name << " gradient " << g << " > " << rule.max_gradient
                           << " between (" << tx << "," << ty << ") and (" << tx << "," << ty + 1
                           << ")";
                        rep.violations.push_back(
                            {ViolationType::Gradient, tx, ty, g, rule.max_gradient, os.str()});
                    }
                }
            }
        }
    }

    // Fill-to-geometry spacing: fill must never land inside the keep-out halo.
    if (fill_occ.nx == blocked.nx && fill_occ.ny == blocked.ny) {
        int spacing_hits = 0;
        for (size_t i = 0; i < fill_occ.occ.size(); ++i)
            if (fill_occ.occ[i] && blocked.occ[i]) ++spacing_hits;
        if (spacing_hits > 0) {
            std::ostringstream os;
            os << rule.name << " fill overlaps keep-out halo in " << spacing_hits << " cells";
            rep.violations.push_back(
                {ViolationType::Spacing, -1, -1, double(spacing_hits), 0.0, os.str()});
        }
    }

    // Fill-shape minimum area (shape-level static check).
    double fill_area_um2 = rule.fill_w_um * rule.fill_h_um;
    if (fill_area_um2 < rule.min_area_um2 - 1e-9) {
        std::ostringstream os;
        os << rule.name << " fill area " << fill_area_um2 << " um^2 < min " << rule.min_area_um2;
        rep.violations.push_back(
            {ViolationType::MinArea, -1, -1, fill_area_um2, rule.min_area_um2, os.str()});
    }

    (void)dbu_per_um;
    (void)cell;
    return rep;
}

}  // namespace mf
