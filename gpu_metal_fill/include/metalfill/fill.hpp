#pragma once
#include <vector>
#include "metalfill/geometry.hpp"
#include "metalfill/raster.hpp"

namespace mf {

// Result of computing the keep-out (forbidden) mask for fill placement.
// A cell is blocked if any existing geometry lies within `keepout` of it.
Grid compute_keepout(const Grid& occ, int keepout_cells);

// A placed fill shape, expressed in grid-cell coordinates (footprint is
// [ix0, ix0+w) x [iy0, iy0+h)).
struct FillShape {
    int ix0 = 0, iy0 = 0;
    int w = 0, h = 0;
};

// Parameters controlling fill placement, all expressed in grid cells.
struct FillParams {
    int fill_w = 1;
    int fill_h = 1;
    int pitch_x = 2;
    int pitch_y = 2;
    int win_cells = 1;
    int step_cells = 1;
    double target_density = 0.30;  // fill until each window reaches this
    double max_density = 0.80;     // never exceed this in any window

    // Optional per-window target (gradient-aware fill). When set, a window's
    // target is looked up from this global map instead of `target_density`.
    // The map is indexed [gy*gnx + gx] where (gx,gy) is the *global* window
    // index; a local tile (tx,ty) maps to global (goff_x+tx, goff_y+ty).
    const std::vector<double>* target_map = nullptr;
    int gnx = 0;
    int gny = 0;
    int goff_x = 0;
    int goff_y = 0;
};

// Places dummy fill on a grid so that every window reaches `target_density`
// where physically possible, while never exceeding `max_density` and never
// overlapping the keep-out mask. Returns the placed shapes; `fill_occ` is
// populated with the fill footprints (1 where fill was placed).
std::vector<FillShape> place_fill(const Grid& occ, const Grid& blocked,
                                  const FillParams& params, Grid& fill_occ);

}  // namespace mf
