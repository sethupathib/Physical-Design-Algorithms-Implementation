#pragma once
#include <cstdint>
#include <vector>
#include "metalfill/geometry.hpp"

namespace mf {

// A uniform boolean occupancy grid over a rectangular area of the layout.
// cell is the edge length of one grid cell in database units. Element (ix, iy)
// covers [ox + ix*cell, ox + (ix+1)*cell) x [oy + iy*cell, oy + (iy+1)*cell).
struct Grid {
    int nx = 0;
    int ny = 0;
    dbu cell = 1;
    dbu ox = 0;
    dbu oy = 0;
    std::vector<uint8_t> occ;  // 0/1, row-major (iy*nx + ix)

    void resize(int nx_, int ny_, dbu cell_, dbu ox_, dbu oy_) {
        nx = nx_;
        ny = ny_;
        cell = cell_;
        ox = ox_;
        oy = oy_;
        occ.assign(static_cast<size_t>(nx) * ny, 0);
    }
    inline size_t idx(int ix, int iy) const { return static_cast<size_t>(iy) * nx + ix; }
    inline uint8_t at(int ix, int iy) const { return occ[idx(ix, iy)]; }
    inline void set(int ix, int iy, uint8_t v) { occ[idx(ix, iy)] = v; }
    size_t count() const {
        size_t c = 0;
        for (auto v : occ) c += v;
        return c;
    }
};

// Allocates a grid covering `area` at resolution `cell` (dbu). The area is
// snapped so the origin lands on a cell boundary.
Grid make_grid(const BBox& area, dbu cell);

// Rasterizes the given polygons (whose (layer,datatype) match) into `grid` by
// setting occupied cells to 1. Uses even-odd scanline fill; robust for
// arbitrary simple polygons, exact for axis-aligned rectangles.
void rasterize(Grid& grid, const std::vector<Polygon>& polys, int layer, int datatype);

// Stamps a single axis-aligned rectangle (in dbu) into the grid.
void stamp_rect(Grid& grid, dbu x0, dbu y0, dbu x1, dbu y1, uint8_t value = 1);

}  // namespace mf
