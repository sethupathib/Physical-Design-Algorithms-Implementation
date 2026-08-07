#include "metalfill/fill.hpp"

#include <algorithm>
#include <cmath>

#include "metalfill/density.hpp"

#ifdef _OPENMP
#include <omp.h>
#endif

namespace mf {

Grid compute_keepout(const Grid& occ, int keepout_cells) {
    Grid blocked;
    blocked.resize(occ.nx, occ.ny, occ.cell, occ.ox, occ.oy);
    int r = std::max(keepout_cells, 0);
    SummedAreaTable sat = build_sat(occ);
    for (int iy = 0; iy < occ.ny; ++iy) {
        for (int ix = 0; ix < occ.nx; ++ix) {
            int x0 = ix - r, y0 = iy - r;
            int x1 = ix + r + 1, y1 = iy + r + 1;
            blocked.set(ix, iy, sat.area(x0, y0, x1, y1) > 0 ? 1 : 0);
        }
    }
    return blocked;
}

std::vector<FillShape> place_fill(const Grid& occ, const Grid& blocked,
                                  const FillParams& params, Grid& fill_occ) {
    fill_occ.resize(occ.nx, occ.ny, occ.cell, occ.ox, occ.oy);

    const int fw = std::max(params.fill_w, 1);
    const int fh = std::max(params.fill_h, 1);
    const int px = std::max(params.pitch_x, fw);
    const int py = std::max(params.pitch_y, fh);
    const int win = std::max(params.win_cells, 1);
    const int step = std::max(params.step_cells, 1);
    const double fill_area = static_cast<double>(fw) * fh;

    SummedAreaTable occ_sat = build_sat(occ);

    auto ntiles = [](int n, int s) { return std::max(1, (n + s - 1) / s); };
    const int ntx = ntiles(occ.nx, step);
    const int nty = ntiles(occ.ny, step);
    const int ntiles_total = ntx * nty;

    std::vector<std::vector<FillShape>> per_tile(ntiles_total);

    // Each tile writes only footprints whose origin is inside the tile and whose
    // extent stays inside the tile, so the writes to fill_occ are disjoint and
    // the loop is safe to run in parallel across tiles (and, later, on the GPU).
#ifdef _OPENMP
#pragma omp parallel for schedule(dynamic)
#endif
    for (int t = 0; t < ntiles_total; ++t) {
        int tx = t % ntx;
        int ty = t / ntx;
        int wx0 = tx * step;
        int wy0 = ty * step;
        int wx1 = std::min(wx0 + win, occ.nx);
        int wy1 = std::min(wy0 + win, occ.ny);
        double win_area = static_cast<double>(wx1 - wx0) * (wy1 - wy0);
        if (win_area <= 0) continue;

        double occ_cells = static_cast<double>(occ_sat.area(wx0, wy0, wx1, wy1));
        double placed_cells = 0.0;

        // Per-window target (gradient-aware) if a target map is supplied.
        double tgt = params.target_density;
        if (params.target_map) {
            int gx = params.goff_x + tx;
            int gy = params.goff_y + ty;
            if (gx >= 0 && gy >= 0 && gx < params.gnx && gy < params.gny)
                tgt = (*params.target_map)[static_cast<size_t>(gy) * params.gnx + gx];
        }
        double target_cells = tgt * win_area;
        double max_cells = params.max_density * win_area;

        auto& out = per_tile[t];

        // First candidate origin on the global pitch lattice inside the tile.
        int cx_start = ((wx0 + px - 1) / px) * px;
        int cy_start = ((wy0 + py - 1) / py) * py;

        for (int cy = cy_start; cy + fh <= wy1; cy += py) {
            if (occ_cells + placed_cells + fill_area > target_cells) break;
            for (int cx = cx_start; cx + fw <= wx1; cx += px) {
                if (occ_cells + placed_cells + fill_area > target_cells) break;
                if (occ_cells + placed_cells + fill_area > max_cells) break;

                bool free = true;
                for (int yy = cy; yy < cy + fh && free; ++yy)
                    for (int xx = cx; xx < cx + fw; ++xx)
                        if (blocked.at(xx, yy) || fill_occ.at(xx, yy)) {
                            free = false;
                            break;
                        }
                if (!free) continue;

                for (int yy = cy; yy < cy + fh; ++yy)
                    for (int xx = cx; xx < cx + fw; ++xx) fill_occ.set(xx, yy, 1);
                out.push_back(FillShape{cx, cy, fw, fh});
                placed_cells += fill_area;
            }
        }
    }

    std::vector<FillShape> shapes;
    for (auto& v : per_tile)
        shapes.insert(shapes.end(), v.begin(), v.end());
    return shapes;
}

}  // namespace mf
