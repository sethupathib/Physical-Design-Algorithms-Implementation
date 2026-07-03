// Lightweight, dependency-free test harness for the metal-fill library.
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <string>
#include <vector>

#include "metalfill/density.hpp"
#include "metalfill/drc.hpp"
#include "metalfill/engine.hpp"
#include "metalfill/fill.hpp"
#include "metalfill/gdsii.hpp"
#include "metalfill/layermap.hpp"
#include "metalfill/partition.hpp"
#include "metalfill/raster.hpp"

using namespace mf;

static int g_fails = 0;
static int g_checks = 0;
#define CHECK(cond, msg)                                                       \
    do {                                                                       \
        ++g_checks;                                                            \
        if (!(cond)) {                                                         \
            ++g_fails;                                                         \
            std::printf("  FAIL: %s (%s:%d)\n", msg, __FILE__, __LINE__);      \
        }                                                                      \
    } while (0)

static void test_gds_roundtrip() {
    std::printf("[gds roundtrip]\n");
    Layout L;
    L.cell_name = "TOP";
    L.polygons.push_back(make_rect(10, 0, 0, 0, 5000, 3000));
    L.polygons.push_back(make_rect(23, 5, -2000, -1000, 4000, 7000));
    const std::string path = "build/_test_rt.gds";
    write_gds(path, L);
    Layout R = read_gds(path);
    CHECK(R.polygons.size() == 2, "polygon count preserved");
    CHECK(R.cell_name == "TOP", "cell name preserved");
    CHECK(std::llround(R.dbu_per_um()) == 1000, "units preserved (1000 dbu/um)");
    bool found = false;
    for (const auto& p : R.polygons)
        if (p.layer == 23 && p.datatype == 5) {
            BBox b = p.bbox();
            found = (b.xmin == -2000 && b.ymin == -1000 && b.xmax == 4000 && b.ymax == 7000);
        }
    CHECK(found, "layer/datatype/coords preserved");
}

static void test_sat_density() {
    std::printf("[sat + density]\n");
    Grid g;
    g.resize(4, 4, 100, 0, 0);
    // Fill a 2x2 block in the corner.
    for (int y = 0; y < 2; ++y)
        for (int x = 0; x < 2; ++x) g.set(x, y, 1);
    SummedAreaTable sat = build_sat(g);
    CHECK(sat.area(0, 0, 4, 4) == 4, "total occupied = 4");
    CHECK(sat.area(0, 0, 2, 2) == 4, "block area = 4");
    CHECK(sat.area(2, 2, 4, 4) == 0, "empty quadrant = 0");
    DensityMap dm = compute_density(sat, 2, 2);  // four 2x2 windows
    CHECK(dm.ntiles_x == 2 && dm.ntiles_y == 2, "2x2 tiling");
    CHECK(std::fabs(dm.at(0, 0).density - 1.0) < 1e-9, "corner window density 1.0");
    CHECK(std::fabs(dm.at(1, 1).density - 0.0) < 1e-9, "far window density 0.0");
    CHECK(std::fabs(dm.mean_density() - 0.25) < 1e-9, "mean density 0.25");
}

static void test_rasterize_rect() {
    std::printf("[rasterize]\n");
    Grid g = make_grid(BBox{0, 0, 1000, 1000}, 100);  // 10x10 cells (11x11 with +1)
    std::vector<Polygon> polys = {make_rect(1, 0, 200, 200, 700, 700)};
    rasterize(g, polys, 1, 0);
    // 500x500 dbu rect at 100 dbu/cell -> ~5x5 = 25 cells.
    CHECK(g.count() == 25, "rasterized rect area = 25 cells");
}

static void test_keepout() {
    std::printf("[keepout dilation]\n");
    Grid g;
    g.resize(7, 7, 100, 0, 0);
    g.set(3, 3, 1);  // single occupied cell in the middle
    Grid b = compute_keepout(g, 1);
    CHECK(b.at(3, 3) == 1, "center blocked");
    CHECK(b.at(2, 2) == 1 && b.at(4, 4) == 1, "diagonal neighbors blocked (r=1)");
    CHECK(b.at(1, 1) == 0, "distance-2 cell not blocked");
    Grid b0 = compute_keepout(g, 0);
    CHECK(b0.count() == 1, "r=0 keepout equals occupancy");
}

static void test_place_fill() {
    std::printf("[place fill]\n");
    Grid occ;
    occ.resize(40, 40, 100, 0, 0);  // empty layer
    Grid blocked = compute_keepout(occ, 0);
    FillParams fp;
    fp.fill_w = 1;
    fp.fill_h = 1;
    fp.pitch_x = 2;
    fp.pitch_y = 2;
    fp.win_cells = 40;
    fp.step_cells = 40;
    fp.target_density = 0.20;
    fp.max_density = 0.80;
    Grid fill_occ;
    auto shapes = place_fill(occ, blocked, fp, fill_occ);
    double dens = double(fill_occ.count()) / (40.0 * 40.0);
    CHECK(!shapes.empty(), "fill placed");
    CHECK(dens >= 0.20 - 1e-6, "reached target density");
    CHECK(dens <= 0.80 + 1e-6, "did not exceed max density");

    // With keepout covering everything, no fill can be placed.
    Grid occ2;
    occ2.resize(10, 10, 100, 0, 0);
    for (auto& v : occ2.occ) v = 1;
    Grid blocked2 = compute_keepout(occ2, 0);
    Grid fo2;
    auto s2 = place_fill(occ2, blocked2, fp, fo2);
    CHECK(s2.empty(), "no fill where fully blocked");
}

static void test_partition_cover() {
    std::printf("[partition cover]\n");
    BBox area{0, 0, 100000, 100000};  // 100um die
    PartitionConfig pc;
    pc.anchor_x = 0;
    pc.anchor_y = 0;
    pc.align_x = 20000;  // 20um
    pc.align_y = 20000;
    pc.margin = 20000;
    pc.max_leaf = 2;
    pc.clip = area;
    auto parts = partition_recursive(area, pc);
    CHECK(parts.size() >= 4, "die split into multiple leaves");

    // Cores must be disjoint and exactly cover the die area (by summed area).
    long long covered = 0;
    bool aligned = true;
    for (const auto& p : parts) {
        covered += (long long)p.core.width() * p.core.height();
        if ((p.core.xmin % pc.align_x) != 0 || (p.core.ymin % pc.align_y) != 0) aligned = false;
        CHECK(p.halo.xmin <= p.core.xmin && p.halo.xmax >= p.core.xmax, "halo contains core");
    }
    CHECK(aligned, "core edges aligned to lattice");
    CHECK(covered == (long long)area.width() * area.height(), "cores tile the die exactly");
}

// The whole point of partitioning: the merged result must match a single-shot
// (global) fill. We run the engine with a tiny leaf size and with a huge leaf
// size (one partition) and require identical post-fill density.
static void test_partition_equals_global() {
    std::printf("[partition == global]\n");
    Layout base;
    base.cell_name = "TOP";
    const dbu win = 20000;
    for (int j = 0; j < 5; ++j)
        for (int i = 0; i < 5; ++i) {
            double f = 0.05 + 0.05 * ((i + j) % 7);
            double s = std::sqrt(f) * win;
            dbu x0 = i * win + dbu((win - s) / 2);
            dbu y0 = j * win + dbu((win - s) / 2);
            base.polygons.push_back(make_rect(metal_layer(3), 0, x0, y0, x0 + dbu(s), y0 + dbu(s)));
        }

    std::vector<FillRule> rules;
    for (const auto& r : default_layermap())
        if (r.name == "M3") rules.push_back(r);

    Layout a = base, b = base;
    EngineConfig ca;
    ca.max_leaf = 1;      // finely partitioned
    ca.max_iterations = 3;
    EngineConfig cb;
    cb.max_leaf = 100000; // effectively one partition (global)
    cb.max_iterations = 3;

    FillSummary sa = run_fill(a, rules, ca);
    FillSummary sb = run_fill(b, rules, cb);

    CHECK(sa.layers[0].partitions > 1, "fine config actually partitioned");
    CHECK(sb.layers[0].partitions == 1, "global config is a single partition");
    CHECK(sa.layers[0].fill_shapes == sb.layers[0].fill_shapes,
          "same number of fill shapes partitioned vs global");
    CHECK(std::fabs(sa.layers[0].density_after_mean - sb.layers[0].density_after_mean) < 1e-6,
          "same post-fill mean density");
    CHECK(std::fabs(sa.layers[0].density_after_min - sb.layers[0].density_after_min) < 1e-6,
          "same post-fill min density");
}

static void test_engine_endtoend() {
    std::printf("[engine end-to-end]\n");
    Layout L;
    L.cell_name = "TOP";
    const dbu win = 20000;
    auto rules = default_layermap();
    int li = 0;
    for (const auto& r : rules) {
        for (int j = 0; j < 5; ++j)
            for (int i = 0; i < 5; ++i) {
                double f = 0.04 + 0.06 * ((i + j + li) % 9);
                double s = std::sqrt(f) * win;
                dbu x0 = i * win + dbu((win - s) / 2);
                dbu y0 = j * win + dbu((win - s) / 2);
                L.polygons.push_back(make_rect(r.layer, r.datatype, x0, y0, x0 + dbu(s), y0 + dbu(s)));
            }
        ++li;
    }
    size_t before = L.polygons.size();
    EngineConfig cfg;
    cfg.max_iterations = 3;
    FillSummary sum = run_fill(L, rules, cfg);

    CHECK(L.polygons.size() > before, "fill polygons appended");
    CHECK(sum.total_fill_shapes() > 0, "fill produced");
    // No spacing or max-density violations may ever be produced by the tool.
    int spacing = 0, maxd = 0;
    for (const auto& l : sum.layers) {
        spacing += l.drc.count(ViolationType::Spacing);
        maxd += l.drc.count(ViolationType::MaxDensity);
    }
    CHECK(spacing == 0, "no fill-in-keepout spacing violations");
    CHECK(maxd == 0, "no max-density violations");
    for (const auto& l : sum.layers) {
        CHECK(l.density_after_min >= l.density_before_min - 1e-9, "min density did not decrease");
        CHECK(l.density_after_mean >= l.density_before_mean - 1e-9, "mean density did not decrease");
    }
}

int main() {
    std::printf("== metalfill tests ==\n");
    test_gds_roundtrip();
    test_sat_density();
    test_rasterize_rect();
    test_keepout();
    test_place_fill();
    test_partition_cover();
    test_partition_equals_global();
    test_engine_endtoend();
    std::printf("\n%d checks, %d failures\n", g_checks, g_fails);
    return g_fails == 0 ? 0 : 1;
}
