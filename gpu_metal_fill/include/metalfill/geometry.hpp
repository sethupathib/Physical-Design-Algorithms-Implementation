#pragma once
#include <cstdint>
#include <vector>
#include <limits>
#include <algorithm>

namespace mf {

// All layout coordinates are stored in integer database units (dbu).
using dbu = int64_t;

struct Point {
    dbu x = 0;
    dbu y = 0;
};

struct BBox {
    dbu xmin = std::numeric_limits<dbu>::max();
    dbu ymin = std::numeric_limits<dbu>::max();
    dbu xmax = std::numeric_limits<dbu>::min();
    dbu ymax = std::numeric_limits<dbu>::min();

    bool valid() const { return xmax >= xmin && ymax >= ymin; }
    dbu width() const { return valid() ? xmax - xmin : 0; }
    dbu height() const { return valid() ? ymax - ymin : 0; }

    void expand(const Point& p) {
        xmin = std::min(xmin, p.x);
        ymin = std::min(ymin, p.y);
        xmax = std::max(xmax, p.x);
        ymax = std::max(ymax, p.y);
    }
    void expand(const BBox& b) {
        if (!b.valid()) return;
        xmin = std::min(xmin, b.xmin);
        ymin = std::min(ymin, b.ymin);
        xmax = std::max(xmax, b.xmax);
        ymax = std::max(ymax, b.ymax);
    }
};

// A simple polygon tagged with GDSII (layer, datatype).
struct Polygon {
    int layer = 0;
    int datatype = 0;
    std::vector<Point> pts;

    BBox bbox() const {
        BBox b;
        for (const auto& p : pts) b.expand(p);
        return b;
    }
};

inline Polygon make_rect(int layer, int datatype, dbu x0, dbu y0, dbu x1, dbu y1) {
    Polygon p;
    p.layer = layer;
    p.datatype = datatype;
    p.pts = {{x0, y0}, {x1, y0}, {x1, y1}, {x0, y1}};
    return p;
}

}  // namespace mf
