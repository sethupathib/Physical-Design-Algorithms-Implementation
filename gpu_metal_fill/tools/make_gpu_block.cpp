// Generates a synthetic but realistic "GPU block" GDSII to exercise the fill
// engine. It is NOT a real design -- it just reproduces the *floorplan-level
// density structure* a GPU block would have so that fill has varied work:
//
//   * A grid of SM (streaming-multiprocessor) tiles. Each tile has two SRAM
//     macros (register file + shared memory) and a standard-cell logic region.
//   * SRAM macros: very dense on OD/PO/M1..M3 (bitcell arrays), open above.
//   * Logic regions: medium-density cell rows (OD/PO) + local routing (M1..M3),
//     with per-tile variation.
//   * Routing channels between tiles: bus routing on mid metals (M4..M8).
//   * Global clock/spine routes on M9/M10.
//   * A regular power grid (wide straps) on the top metals (M11..M14), which is
//     sparse (~15-20%) and therefore needs fill up to the min-density target.
//
// GDS layers follow metalfill/layermap.hpp: OD=1, PO=2, M1..M14=10..23, dt 0.
#include <cmath>
#include <cstdint>
#include <cstdlib>
#include <iostream>
#include <string>

#include "metalfill/gdsii.hpp"
#include "metalfill/layermap.hpp"

using namespace mf;

namespace {

struct Gen {
    Layout L;
    double dppu;
    uint64_t s = 0x9e3779b97f4a7c15ULL;

    dbu um(double v) { return static_cast<dbu>(std::llround(v * dppu)); }
    uint32_t rnd() {
        s = s * 6364136223846793005ULL + 1442695040888963407ULL;
        return static_cast<uint32_t>(s >> 33);
    }
    double frand() { return (rnd() % 100000) / 100000.0; }

    void rect(int layer, dbu x0, dbu y0, dbu x1, dbu y1) {
        if (x1 > x0 && y1 > y0) L.polygons.push_back(make_rect(layer, 0, x0, y0, x1, y1));
    }
    // Parallel stripes filling a rectangle. density ~= width/pitch.
    void stripes(int layer, dbu x0, dbu y0, dbu x1, dbu y1, dbu pitch, dbu width, bool vertical) {
        if (pitch <= 0) return;
        if (vertical) {
            for (dbu x = x0; x + width <= x1; x += pitch) rect(layer, x, y0, x + width, y1);
        } else {
            for (dbu y = y0; y + width <= y1; y += pitch) rect(layer, x0, y, x1, y + width);
        }
    }
    // A dense macro: bitcell-like stripes on OD/PO/M1..M3. A guard ring of a
    // couple of microns is left inside so density tapers toward the edge (as in
    // a real macro placement), which keeps the density gradient fillable.
    void macro(dbu x0, dbu y0, dbu x1, dbu y1) {
        stripes(kOdLayer, x0, y0, x1, y1, um(0.5), um(0.28), false);   // ~56%
        stripes(kPoLayer, x0, y0, x1, y1, um(0.5), um(0.24), true);    // ~48%
        stripes(metal_layer(1), x0, y0, x1, y1, um(0.4), um(0.20), true);   // ~50%
        stripes(metal_layer(2), x0, y0, x1, y1, um(0.4), um(0.18), false);  // ~45%
        stripes(metal_layer(3), x0, y0, x1, y1, um(0.6), um(0.24), true);   // ~40%
    }
    // Standard-cell logic region: rows of active + poly gates, local routing.
    void logic(dbu x0, dbu y0, dbu x1, dbu y1, double lo) {
        // Cell rows: OD islands per row, poly gates crossing them.
        dbu row = um(1.2);
        for (dbu y = y0; y + um(0.7) <= y1; y += row) {
            for (dbu x = x0; x + um(1.0) <= x1; x += um(1.4)) {
                if (frand() < lo + 0.35) rect(kOdLayer, x, y, x + um(0.9), y + um(0.6));
            }
        }
        stripes(kPoLayer, x0, y0, x1, y1, um(0.9), um(0.18), true);  // poly gates
        // Local routing, density varies per region.
        stripes(metal_layer(1), x0, y0, x1, y1, um(0.6), um(0.2 + 0.15 * lo), true);
        stripes(metal_layer(2), x0, y0, x1, y1, um(0.8), um(0.24 + 0.2 * lo), false);
        stripes(metal_layer(3), x0, y0, x1, y1, um(1.0), um(0.24 + 0.2 * lo), true);
    }
};

}  // namespace

int main(int argc, char** argv) {
    std::string out = "gpu_block.gds";
    int sm = 3;  // SM grid is sm x sm
    for (int i = 1; i < argc; ++i) {
        std::string a = argv[i];
        if (a == "-o" && i + 1 < argc) out = argv[++i];
        else if (a == "-n" && i + 1 < argc) sm = std::atoi(argv[++i]);
        else if (a == "-h" || a == "--help") {
            std::cout << "usage: make_gpu_block [-o out.gds] [-n sm_grid]\n";
            return 0;
        }
    }

    Gen g;
    g.dppu = g.L.dbu_per_um();
    g.L.lib_name = "GPU_BLOCK";
    g.L.cell_name = "GPU_TOP";

    const dbu margin = g.um(8);
    const dbu tile = g.um(56);
    const dbu chan = g.um(6);
    const dbu step = tile + chan;
    const dbu die = margin * 2 + sm * tile + (sm - 1) * chan;

    // ---- SM tiles: macros + logic ----------------------------------------
    for (int ty = 0; ty < sm; ++ty) {
        for (int tx = 0; tx < sm; ++tx) {
            dbu ox = margin + tx * step;
            dbu oy = margin + ty * step;
            // Two SRAM macros in the top half (register file + shared memory).
            dbu mac_h = g.um(24);
            dbu half = tile / 2;
            g.macro(ox + g.um(1), oy + tile - mac_h - g.um(1), ox + half - g.um(1), oy + tile - g.um(1));
            g.macro(ox + half + g.um(1), oy + tile - mac_h - g.um(1), ox + tile - g.um(1),
                    oy + tile - g.um(1));
            // Logic occupies the bottom part; density varies per tile.
            double lo = 0.30 + 0.4 * g.frand();
            g.logic(ox + g.um(1), oy + g.um(1), ox + tile - g.um(1), oy + tile - mac_h - g.um(2), lo);
        }
    }

    // ---- Routing channels: bus routing on mid metals ---------------------
    for (int t = 1; t < sm; ++t) {
        dbu cx = margin + t * step - chan;
        dbu cy = margin + t * step - chan;
        for (int m = 4; m <= 8; ++m) {
            bool vert = (m % 2 == 0);
            // vertical channel (routes run vertically) and horizontal channel
            g.stripes(metal_layer(m), cx, margin, cx + chan, die - margin, g.um(0.8), g.um(0.4),
                      vert);
            g.stripes(metal_layer(m), margin, cy, die - margin, cy + chan, g.um(0.8), g.um(0.4),
                      !vert);
        }
    }

    // ---- Global clock / spine on M9, M10 ---------------------------------
    for (int k = 0; k < sm; ++k) {
        dbu c = margin + k * step + tile / 2;
        g.rect(metal_layer(9), c - g.um(1), margin, c + g.um(1), die - margin);
        g.rect(metal_layer(10), margin, c - g.um(1), die - margin, c + g.um(1));
    }

    // ---- Power grid on top metals (wide, sparse straps) ------------------
    // Vertical on M12/M14, horizontal on M11/M13; ~4um straps on a 24um pitch.
    for (dbu x = margin; x + g.um(4) <= die - margin; x += g.um(24)) {
        g.rect(metal_layer(12), x, margin, x + g.um(4), die - margin);
        g.rect(metal_layer(14), x, margin, x + g.um(4), die - margin);
    }
    for (dbu y = margin; y + g.um(4) <= die - margin; y += g.um(24)) {
        g.rect(metal_layer(11), margin, y, die - margin, y + g.um(4));
        g.rect(metal_layer(13), margin, y, die - margin, y + g.um(4));
    }

    write_gds(out, g.L);
    BBox b = g.L.bbox();
    std::cout << "wrote " << out << ": " << g.L.polygons.size() << " polygons, GPU block "
              << (b.width() / g.dppu) << " x " << (b.height() / g.dppu) << " um, " << (sm * sm)
              << " SM tiles\n";
    return 0;
}
