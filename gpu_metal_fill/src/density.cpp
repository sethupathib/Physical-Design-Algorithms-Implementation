#include "metalfill/density.hpp"

#include <algorithm>
#include <limits>

namespace mf {

int64_t SummedAreaTable::area(int x0, int y0, int x1, int y1) const {
    x0 = std::max(x0, 0);
    y0 = std::max(y0, 0);
    x1 = std::min(x1, nx);
    y1 = std::min(y1, ny);
    if (x1 <= x0 || y1 <= y0) return 0;
    const int w = nx + 1;
    auto S = [&](int x, int y) -> int64_t { return sat[static_cast<size_t>(y) * w + x]; };
    return S(x1, y1) - S(x0, y1) - S(x1, y0) + S(x0, y0);
}

SummedAreaTable build_sat(const Grid& grid) {
    SummedAreaTable t;
    t.nx = grid.nx;
    t.ny = grid.ny;
    const int w = grid.nx + 1;
    const int h = grid.ny + 1;
    t.sat.assign(static_cast<size_t>(w) * h, 0);
    for (int y = 0; y < grid.ny; ++y) {
        int64_t row = 0;
        for (int x = 0; x < grid.nx; ++x) {
            row += grid.at(x, y);
            t.sat[static_cast<size_t>(y + 1) * w + (x + 1)] =
                t.sat[static_cast<size_t>(y) * w + (x + 1)] + row;
        }
    }
    return t;
}

double DensityMap::min_density() const {
    double m = std::numeric_limits<double>::max();
    for (const auto& t : tiles) m = std::min(m, t.density);
    return tiles.empty() ? 0.0 : m;
}
double DensityMap::max_density() const {
    double m = 0.0;
    for (const auto& t : tiles) m = std::max(m, t.density);
    return m;
}
double DensityMap::mean_density() const {
    if (tiles.empty()) return 0.0;
    double s = 0.0;
    for (const auto& t : tiles) s += t.density;
    return s / tiles.size();
}

DensityMap compute_density(const SummedAreaTable& sat, int win_cells, int step_cells) {
    DensityMap dm;
    win_cells = std::max(win_cells, 1);
    step_cells = std::max(step_cells, 1);
    // Number of tiles so that the whole grid is covered.
    auto ntiles = [](int n, int step) { return std::max(1, (n + step - 1) / step); };
    dm.ntiles_x = ntiles(sat.nx, step_cells);
    dm.ntiles_y = ntiles(sat.ny, step_cells);
    dm.tiles.resize(static_cast<size_t>(dm.ntiles_x) * dm.ntiles_y);

    for (int ty = 0; ty < dm.ntiles_y; ++ty) {
        for (int tx = 0; tx < dm.ntiles_x; ++tx) {
            Window win;
            win.ix = tx;
            win.iy = ty;
            win.x0 = tx * step_cells;
            win.y0 = ty * step_cells;
            win.x1 = std::min(win.x0 + win_cells, sat.nx);
            win.y1 = std::min(win.y0 + win_cells, sat.ny);
            int64_t occ = sat.area(win.x0, win.y0, win.x1, win.y1);
            int64_t cells = static_cast<int64_t>(win.x1 - win.x0) * (win.y1 - win.y0);
            win.density = cells > 0 ? static_cast<double>(occ) / static_cast<double>(cells) : 0.0;
            dm.tiles[static_cast<size_t>(ty) * dm.ntiles_x + tx] = win;
        }
    }
    return dm;
}

}  // namespace mf
