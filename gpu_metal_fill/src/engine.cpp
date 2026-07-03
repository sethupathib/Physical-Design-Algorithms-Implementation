#include "metalfill/engine.hpp"

#include <algorithm>
#include <chrono>
#include <cmath>
#include <iomanip>
#include <sstream>

#include "metalfill/partition.hpp"

#ifdef _OPENMP
#include <omp.h>
#endif

namespace mf {
namespace {

struct LayerGeom {
    dbu cell = 1;
    dbu fw = 1, fh = 1, px = 1, py = 1;
    dbu win = 1, step = 1, keep = 0;
    dbu align_x = 1, align_y = 1, margin = 1;
    int fw_c = 1, fh_c = 1, px_c = 1, py_c = 1;
    int win_c = 1, step_c = 1, keep_c = 0;
};

dbu to_dbu(double um, double dppu) { return static_cast<dbu>(std::llround(um * dppu)); }

LayerGeom compute_geom(const FillRule& r, double dppu) {
    LayerGeom g;
    g.fw = std::max<dbu>(to_dbu(r.fill_w_um, dppu), 1);
    g.fh = std::max<dbu>(to_dbu(r.fill_h_um, dppu), 1);
    g.px = std::max<dbu>(to_dbu(r.fill_pitch_x_um, dppu), g.fw);
    g.py = std::max<dbu>(to_dbu(r.fill_pitch_y_um, dppu), g.fh);
    g.win = std::max<dbu>(to_dbu(r.window_um, dppu), 1);
    g.step = std::max<dbu>(to_dbu(r.step_um, dppu), 1);
    g.keep = std::max<dbu>(to_dbu(r.keepout_um, dppu), 0);

    // Grid cell divides every relevant length so windows/pitch are exact.
    dbu c = gcd_dbu(g.fw, g.fh);
    c = gcd_dbu(c, g.px);
    c = gcd_dbu(c, g.py);
    c = gcd_dbu(c, g.win);
    c = gcd_dbu(c, g.step);
    g.cell = std::max<dbu>(c, 1);

    g.fw_c = static_cast<int>(g.fw / g.cell);
    g.fh_c = static_cast<int>(g.fh / g.cell);
    g.px_c = static_cast<int>(g.px / g.cell);
    g.py_c = static_cast<int>(g.py / g.cell);
    g.win_c = static_cast<int>(g.win / g.cell);
    g.step_c = static_cast<int>(g.step / g.cell);
    g.keep_c = static_cast<int>((g.keep + g.cell - 1) / g.cell);

    // Partition cuts must align to BOTH the window and the fill pitch so the
    // per-partition result is identical to a global fill.
    g.align_x = lcm_dbu(g.win, g.px);
    g.align_y = lcm_dbu(g.win, g.py);
    // Halo must cover keep-out + one fill footprint of context, rounded up to a
    // full align unit so the halo origin stays on the lattice.
    dbu need = g.keep + std::max(g.fw, g.fh);
    dbu m_x = ((need + g.align_x - 1) / g.align_x) * g.align_x;
    dbu m_y = ((need + g.align_y - 1) / g.align_y) * g.align_y;
    g.margin = std::max(m_x, m_y);
    return g;
}

dbu floor_to(dbu v, dbu a) { return (v >= 0 ? (v / a) : -(((-v) + a - 1) / a)) * a; }
dbu ceil_to(dbu v, dbu a) { return (v >= 0 ? ((v + a - 1) / a) : -((-v) / a)) * a; }

// Snaps a bbox outward to the align lattice in each axis. The result is an exact
// whole number of align-units, so density windows and the fill pitch stay
// coherent whether computed globally or per-partition.
BBox snap_area(const BBox& b, dbu align_x, dbu align_y) {
    BBox s;
    s.xmin = floor_to(b.xmin, align_x);
    s.ymin = floor_to(b.ymin, align_y);
    s.xmax = ceil_to(b.xmax, align_x);
    s.ymax = ceil_to(b.ymax, align_y);
    return s;
}

std::vector<Polygon> layer_polys(const Layout& layout, const FillRule& r) {
    std::vector<Polygon> v;
    for (const auto& p : layout.polygons)
        if (p.layer == r.layer && p.datatype == r.datatype) v.push_back(p);
    return v;
}

bool intersects(const BBox& a, const BBox& b) {
    return !(a.xmax <= b.xmin || b.xmax <= a.xmin || a.ymax <= b.ymin || b.ymax <= a.ymin);
}

// Runs partitioned fill for a per-window target map; returns emitted fill
// rectangles (global dbu) tagged on the fill datatype. Each leaf is processed
// independently (parallel), reading a halo of context and emitting only inside
// its core, so the concatenated result equals a global fill.
std::vector<Polygon> partitioned_fill(const std::vector<Polygon>& polys, const FillRule& rule,
                                      const LayerGeom& g, const std::vector<PartitionRect>& parts,
                                      FillBackend& backend, const std::vector<double>& target_map,
                                      int gnx, int gny, dbu area_xmin, dbu area_ymin, double maxd) {
    std::vector<std::vector<Polygon>> per(parts.size());

#ifdef _OPENMP
#pragma omp parallel for schedule(dynamic)
#endif
    for (int pi = 0; pi < static_cast<int>(parts.size()); ++pi) {
        const PartitionRect& part = parts[pi];
        Grid occ = make_grid(part.halo, g.cell);

        // Rasterize only geometry that touches this leaf's halo.
        std::vector<Polygon> local;
        for (const auto& p : polys)
            if (intersects(p.bbox(), part.halo)) local.push_back(p);
        rasterize(occ, local, rule.layer, rule.datatype);

        Grid blocked = backend.compute_keepout(occ, g.keep_c);

        FillParams fp;
        fp.fill_w = g.fw_c;
        fp.fill_h = g.fh_c;
        fp.pitch_x = g.px_c;
        fp.pitch_y = g.py_c;
        fp.win_cells = g.win_c;
        fp.step_cells = g.step_c;
        fp.max_density = maxd;
        fp.target_map = &target_map;
        fp.gnx = gnx;
        fp.gny = gny;
        fp.goff_x = static_cast<int>((occ.ox - area_xmin) / g.step);
        fp.goff_y = static_cast<int>((occ.oy - area_ymin) / g.step);

        Grid fill_occ;
        std::vector<FillShape> shapes = backend.place_fill(occ, blocked, fp, fill_occ);

        auto& out = per[pi];
        for (const auto& s : shapes) {
            dbu x0 = occ.ox + static_cast<dbu>(s.ix0) * g.cell;
            dbu y0 = occ.oy + static_cast<dbu>(s.iy0) * g.cell;
            dbu x1 = x0 + static_cast<dbu>(s.w) * g.cell;
            dbu y1 = y0 + static_cast<dbu>(s.h) * g.cell;
            // Emit only shapes fully inside this leaf's core (disjoint merge).
            if (x0 < part.core.xmin || y0 < part.core.ymin || x1 > part.core.xmax ||
                y1 > part.core.ymax)
                continue;
            out.push_back(make_rect(rule.layer, rule.fill_datatype, x0, y0, x1, y1));
        }
    }

    std::vector<Polygon> fills;
    for (auto& v : per) fills.insert(fills.end(), v.begin(), v.end());
    return fills;
}

// Builds occupancy over the whole die for the given polygons on (layer,dt).
Grid whole_layer_grid(const std::vector<Polygon>& polys, const BBox& area, const FillRule& r,
                      dbu cell) {
    Grid g = make_grid(area, cell);
    rasterize(g, polys, r.layer, r.datatype);
    return g;
}

}  // namespace

FillSummary run_fill(Layout& layout, const std::vector<FillRule>& rules, const EngineConfig& cfg) {
    FillSummary summary;
    auto backend = make_backend(cfg.prefer_gpu);
    summary.backend = backend->name();

    double dppu = layout.dbu_per_um();
    auto t_all0 = std::chrono::steady_clock::now();

    for (const auto& rule : rules) {
        auto t0 = std::chrono::steady_clock::now();
        LayerResult res;
        res.name = rule.name;
        res.layer = rule.layer;
        res.is_beol = rule.is_beol;

        std::vector<Polygon> polys = layer_polys(layout, rule);
        res.existing_polys = static_cast<int>(polys.size());

        LayerGeom g = compute_geom(rule, dppu);
        BBox die = layout.bbox();
        if (!die.valid()) {
            summary.layers.push_back(res);
            continue;
        }
        // Align-lattice-snapped working area (see snap_area). Both the global
        // grids and the partition anchor use area.xmin/ymin so every window and
        // fill position is identical globally and per-partition.
        BBox area = snap_area(die, g.align_x, g.align_y);

        // ---- density before -------------------------------------------------
        Grid occ_before = whole_layer_grid(polys, area, rule, g.cell);
        SummedAreaTable sat_before = backend->build_sat(occ_before);
        DensityMap dm_before = backend->compute_density(sat_before, g.win_c, g.step_c);
        res.density_before_min = dm_before.min_density();
        res.density_before_mean = dm_before.mean_density();
        res.density_before_max = dm_before.max_density();

        // ---- partitions -----------------------------------------------------
        PartitionConfig pc;
        pc.anchor_x = area.xmin;
        pc.anchor_y = area.ymin;
        pc.align_x = g.align_x;
        pc.align_y = g.align_y;
        pc.margin = g.margin;
        pc.max_leaf = std::max(cfg.max_leaf, 1);  // align-units per leaf side
        pc.clip = area;  // cores tile the align-snapped area exactly
        std::vector<PartitionRect> parts = partition_recursive(area, pc);
        res.partitions = static_cast<int>(parts.size());

        // ---- gradient-aware iterative fill (DRC-driven) ---------------------
        // Each window gets its own target. We fill, measure density, then raise
        // targets for windows that still violate min-density or that sit too far
        // below a denser neighbor (gradient), and refill. Targets increase
        // monotonically toward max_density, so the loop converges.
        double min_d = rule.min_density;
        double max_d = rule.max_density;
        double grad = rule.max_gradient;
        int gnx = dm_before.ntiles_x;
        int gny = dm_before.ntiles_y;
        double base_target = std::min(min_d + cfg.fill_headroom, max_d);
        std::vector<double> target_map(static_cast<size_t>(gnx) * gny, base_target);

        std::vector<Polygon> best_fills;
        DensityMap dm_after = dm_before;
        int iter = 0;
        for (; iter < std::max(cfg.max_iterations, 1); ++iter) {
            std::vector<Polygon> fills = partitioned_fill(
                polys, rule, g, parts, *backend, target_map, gnx, gny, area.xmin, area.ymin, max_d);

            Grid total = occ_before;  // copy existing occupancy
            for (const auto& f : fills) {
                BBox b = f.bbox();
                stamp_rect(total, b.xmin, b.ymin, b.xmax, b.ymax, 1);
            }
            SummedAreaTable sat_after = backend->build_sat(total);
            DensityMap dm = backend->compute_density(sat_after, g.win_c, g.step_c);

            best_fills = std::move(fills);
            dm_after = dm;

            // Update targets from the achieved density (DRC feedback).
            bool changed = false;
            const int dx[4] = {1, -1, 0, 0};
            const int dy[4] = {0, 0, 1, -1};
            for (int ty = 0; ty < gny; ++ty) {
                for (int tx = 0; tx < gnx; ++tx) {
                    size_t idx = static_cast<size_t>(ty) * gnx + tx;
                    double here = dm.at(tx, ty).density;
                    double need = target_map[idx];
                    if (here < min_d - 1e-9) need = std::max(need, base_target);
                    if (grad > 0) {
                        for (int k = 0; k < 4; ++k) {
                            int nx = tx + dx[k], ny = ty + dy[k];
                            if (nx < 0 || ny < 0 || nx >= gnx || ny >= gny) continue;
                            double nd = dm.at(nx, ny).density;
                            // Overshoot by grad_headroom so the achieved density
                            // (which lands just below target) still clears the
                            // gradient limit despite discrete fill quanta.
                            if (nd - here > grad + 1e-9)
                                need = std::max(need, nd - grad + cfg.grad_headroom);
                        }
                    }
                    need = std::min(need, max_d);
                    if (need > target_map[idx] + 1e-9) {
                        target_map[idx] = need;
                        changed = true;
                    }
                }
            }
            if (!changed) {
                ++iter;
                break;
            }
        }
        res.iterations = iter;

        // ---- append fills + final DRC --------------------------------------
        res.fill_shapes = static_cast<int>(best_fills.size());
        Grid fill_occ = make_grid(area, g.cell);
        for (const auto& f : best_fills) {
            BBox b = f.bbox();
            stamp_rect(fill_occ, b.xmin, b.ymin, b.xmax, b.ymax, 1);
        }
        Grid total = occ_before;
        for (const auto& f : best_fills) {
            BBox b = f.bbox();
            stamp_rect(total, b.xmin, b.ymin, b.xmax, b.ymax, 1);
        }
        SummedAreaTable sat_total = backend->build_sat(total);
        Grid blocked = backend->compute_keepout(occ_before, g.keep_c);
        res.drc = run_drc(sat_total, blocked, fill_occ, g.win_c, g.step_c, rule, dppu, g.cell);

        res.density_after_min = dm_after.min_density();
        res.density_after_mean = dm_after.mean_density();
        res.density_after_max = dm_after.max_density();

        layout.polygons.insert(layout.polygons.end(), best_fills.begin(), best_fills.end());

        auto t1 = std::chrono::steady_clock::now();
        res.seconds = std::chrono::duration<double>(t1 - t0).count();
        summary.layers.push_back(std::move(res));
    }

    auto t_all1 = std::chrono::steady_clock::now();
    summary.total_seconds = std::chrono::duration<double>(t_all1 - t_all0).count();
    return summary;
}

int FillSummary::total_violations() const {
    int c = 0;
    for (const auto& l : layers) c += static_cast<int>(l.drc.violations.size());
    return c;
}
int FillSummary::total_fill_shapes() const {
    int c = 0;
    for (const auto& l : layers) c += l.fill_shapes;
    return c;
}

std::string format_report(const FillSummary& summary) {
    std::ostringstream os;
    os << std::fixed << std::setprecision(3);
    os << "===== Metal Fill Report =====\n";
    os << "backend      : " << summary.backend << "\n";
    os << "total time   : " << summary.total_seconds << " s\n";
    os << "total fill   : " << summary.total_fill_shapes() << " shapes\n";
    os << "total DRC    : " << summary.total_violations() << " violations\n\n";

    os << std::left << std::setw(6) << "layer" << std::setw(6) << "type" << std::setw(6) << "part"
       << std::setw(8) << "exist" << std::setw(8) << "fill" << std::setw(6) << "it"
       << "  dens(before->after) min/mean/max      drc  time(s)\n";
    os << std::string(112, '-') << "\n";
    for (const auto& l : summary.layers) {
        os << std::left << std::setw(6) << l.name << std::setw(6) << (l.is_beol ? "BEOL" : "FEOL")
           << std::setw(6) << l.partitions << std::setw(8) << l.existing_polys << std::setw(8)
           << l.fill_shapes << std::setw(6) << l.iterations << "  ";
        os << std::setprecision(2) << l.density_before_min << "/" << l.density_before_mean << "/"
           << l.density_before_max << " -> " << l.density_after_min << "/" << l.density_after_mean
           << "/" << l.density_after_max;
        os << "   " << std::setw(4) << static_cast<int>(l.drc.violations.size()) << " "
           << std::setprecision(3) << l.seconds << "\n";
    }

    // Detail any violations.
    bool any = false;
    for (const auto& l : summary.layers)
        if (!l.drc.clean()) any = true;
    if (any) {
        os << "\n--- DRC details ---\n";
        for (const auto& l : summary.layers)
            for (const auto& v : l.drc.violations) os << "  " << v.message << "\n";
    }
    return os.str();
}

}  // namespace mf
