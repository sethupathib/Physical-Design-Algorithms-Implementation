#include "metalfill/raster.hpp"

#include <algorithm>
#include <cmath>

namespace mf {

Grid make_grid(const BBox& area, dbu cell) {
    Grid g;
    if (cell <= 0) cell = 1;
    dbu ox = area.valid() ? area.xmin : 0;
    dbu oy = area.valid() ? area.ymin : 0;
    dbu w = area.valid() ? area.width() : 0;
    dbu h = area.valid() ? area.height() : 0;
    // Enough cells to fully cover the area (ceil).
    int nx = static_cast<int>((w + cell - 1) / cell);
    int ny = static_cast<int>((h + cell - 1) / cell);
    g.resize(std::max(nx, 1), std::max(ny, 1), cell, ox, oy);
    return g;
}

void stamp_rect(Grid& grid, dbu x0, dbu y0, dbu x1, dbu y1, uint8_t value) {
    if (x1 < x0) std::swap(x0, x1);
    if (y1 < y0) std::swap(y1, y0);
    // Cells whose center lies within [x0,x1) x [y0,y1).
    int ix0 = static_cast<int>(std::floor((static_cast<double>(x0 - grid.ox)) / grid.cell));
    int iy0 = static_cast<int>(std::floor((static_cast<double>(y0 - grid.oy)) / grid.cell));
    int ix1 = static_cast<int>(std::ceil((static_cast<double>(x1 - grid.ox)) / grid.cell));
    int iy1 = static_cast<int>(std::ceil((static_cast<double>(y1 - grid.oy)) / grid.cell));
    ix0 = std::max(ix0, 0);
    iy0 = std::max(iy0, 0);
    ix1 = std::min(ix1, grid.nx);
    iy1 = std::min(iy1, grid.ny);
    for (int iy = iy0; iy < iy1; ++iy)
        for (int ix = ix0; ix < ix1; ++ix) grid.set(ix, iy, value);
}

void rasterize(Grid& grid, const std::vector<Polygon>& polys, int layer, int datatype) {
    for (const auto& poly : polys) {
        if (poly.layer != layer || poly.datatype != datatype) continue;
        if (poly.pts.size() < 3) continue;

        BBox b = poly.bbox();
        int row0 = static_cast<int>(std::floor((static_cast<double>(b.ymin - grid.oy)) / grid.cell));
        int row1 = static_cast<int>(std::ceil((static_cast<double>(b.ymax - grid.oy)) / grid.cell));
        row0 = std::max(row0, 0);
        row1 = std::min(row1, grid.ny);

        const size_t n = poly.pts.size();
        std::vector<double> xs;
        for (int iy = row0; iy < row1; ++iy) {
            // Scanline at the vertical center of the cell row.
            double yc = grid.oy + (iy + 0.5) * grid.cell;
            xs.clear();
            for (size_t i = 0; i < n; ++i) {
                const Point& a = poly.pts[i];
                const Point& c = poly.pts[(i + 1) % n];
                double ay = a.y, cy = c.y;
                if ((ay <= yc && cy > yc) || (cy <= yc && ay > yc)) {
                    double t = (yc - ay) / (cy - ay);
                    xs.push_back(a.x + t * (c.x - a.x));
                }
            }
            std::sort(xs.begin(), xs.end());
            for (size_t k = 0; k + 1 < xs.size(); k += 2) {
                double xl = xs[k], xr = xs[k + 1];
                // Cells whose center is inside [xl, xr).
                int cx0 = static_cast<int>(
                    std::ceil((xl - grid.ox) / grid.cell - 0.5));
                int cx1 = static_cast<int>(
                    std::floor((xr - grid.ox) / grid.cell - 0.5));
                cx0 = std::max(cx0, 0);
                cx1 = std::min(cx1, grid.nx - 1);
                for (int ix = cx0; ix <= cx1; ++ix) grid.set(ix, iy, 1);
            }
        }
    }
}

}  // namespace mf
