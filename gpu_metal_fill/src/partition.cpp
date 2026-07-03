#include "metalfill/partition.hpp"

#include <algorithm>

namespace mf {

dbu gcd_dbu(dbu a, dbu b) {
    a = a < 0 ? -a : a;
    b = b < 0 ? -b : b;
    while (b) {
        dbu t = a % b;
        a = b;
        b = t;
    }
    return a == 0 ? 1 : a;
}

dbu lcm_dbu(dbu a, dbu b) {
    if (a == 0 || b == 0) return std::max<dbu>(a, b);
    return (a / gcd_dbu(a, b)) * b;
}

namespace {

// Recurse in integer align-lattice coordinates: region [ix0,ix1) x [iy0,iy1).
void recurse(int ix0, int iy0, int ix1, int iy1, int depth, const PartitionConfig& cfg,
             std::vector<PartitionRect>& out) {
    int nx = ix1 - ix0;
    int ny = iy1 - iy0;
    if (nx <= 0 || ny <= 0) return;

    bool leaf = (nx <= cfg.max_leaf && ny <= cfg.max_leaf) || depth >= cfg.max_depth;
    if (leaf) {
        PartitionRect pr;
        pr.depth = depth;
        pr.core.xmin = cfg.anchor_x + static_cast<dbu>(ix0) * cfg.align_x;
        pr.core.xmax = cfg.anchor_x + static_cast<dbu>(ix1) * cfg.align_x;
        pr.core.ymin = cfg.anchor_y + static_cast<dbu>(iy0) * cfg.align_y;
        pr.core.ymax = cfg.anchor_y + static_cast<dbu>(iy1) * cfg.align_y;
        // Clamp emission core to the die bounds.
        if (cfg.clip.valid()) {
            pr.core.xmin = std::max(pr.core.xmin, cfg.clip.xmin);
            pr.core.ymin = std::max(pr.core.ymin, cfg.clip.ymin);
            pr.core.xmax = std::min(pr.core.xmax, cfg.clip.xmax);
            pr.core.ymax = std::min(pr.core.ymax, cfg.clip.ymax);
        }
        pr.halo.xmin = pr.core.xmin - cfg.margin;
        pr.halo.ymin = pr.core.ymin - cfg.margin;
        pr.halo.xmax = pr.core.xmax + cfg.margin;
        pr.halo.ymax = pr.core.ymax + cfg.margin;
        if (pr.core.xmax > pr.core.xmin && pr.core.ymax > pr.core.ymin) out.push_back(pr);
        return;
    }

    bool split_x = nx > 1;
    bool split_y = ny > 1;
    int mx = ix0 + (nx + 1) / 2;
    int my = iy0 + (ny + 1) / 2;

    if (split_x && split_y) {
        // Quadtree split into four children.
        recurse(ix0, iy0, mx, my, depth + 1, cfg, out);
        recurse(mx, iy0, ix1, my, depth + 1, cfg, out);
        recurse(ix0, my, mx, iy1, depth + 1, cfg, out);
        recurse(mx, my, ix1, iy1, depth + 1, cfg, out);
    } else if (split_x) {
        recurse(ix0, iy0, mx, iy1, depth + 1, cfg, out);
        recurse(mx, iy0, ix1, iy1, depth + 1, cfg, out);
    } else {
        recurse(ix0, iy0, ix1, my, depth + 1, cfg, out);
        recurse(ix0, my, ix1, iy1, depth + 1, cfg, out);
    }
}

}  // namespace

std::vector<PartitionRect> partition_recursive(const BBox& area, const PartitionConfig& cfg) {
    std::vector<PartitionRect> out;
    if (!area.valid() || cfg.align_x <= 0 || cfg.align_y <= 0) return out;

    dbu w = area.xmax - cfg.anchor_x;
    dbu h = area.ymax - cfg.anchor_y;
    int nX = static_cast<int>((w + cfg.align_x - 1) / cfg.align_x);
    int nY = static_cast<int>((h + cfg.align_y - 1) / cfg.align_y);
    nX = std::max(nX, 1);
    nY = std::max(nY, 1);
    recurse(0, 0, nX, nY, 0, cfg, out);
    return out;
}

}  // namespace mf
