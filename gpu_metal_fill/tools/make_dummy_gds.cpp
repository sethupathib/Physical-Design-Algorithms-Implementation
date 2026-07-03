// Generates a dummy GDSII with FEOL base layers (OD, PO) and BEOL metals
// (M1..M14). Each 20um window is given a deterministic, spatially varying
// existing density so the fill engine has real work to do (some windows below
// the min-density target, some already dense, with gradients across the die).
#include <cmath>
#include <cstdlib>
#include <iostream>
#include <string>

#include "metalfill/gdsii.hpp"
#include "metalfill/layermap.hpp"

using namespace mf;

int main(int argc, char** argv) {
    std::string out = "dummy.gds";
    int windows = 5;  // 5x5 windows -> 100um die
    for (int i = 1; i < argc; ++i) {
        std::string a = argv[i];
        if (a == "-o" && i + 1 < argc)
            out = argv[++i];
        else if (a == "-n" && i + 1 < argc)
            windows = std::atoi(argv[++i]);
        else if (a == "-h" || a == "--help") {
            std::cout << "usage: make_dummy_gds [-o out.gds] [-n windows_per_side]\n";
            return 0;
        }
    }

    Layout L;
    L.lib_name = "METALFILL";
    L.cell_name = "TOP";
    const double dppu = L.dbu_per_um();       // 1000 dbu / um
    const dbu win = static_cast<dbu>(20.0 * dppu);  // 20um window

    auto rules = default_layermap();
    int layer_index = 0;
    for (const auto& r : rules) {
        for (int j = 0; j < windows; ++j) {
            for (int i = 0; i < windows; ++i) {
                // Spatially varying density, offset per layer so stacks differ.
                int phase = (i + j + layer_index) % 9;
                double f = 0.04 + 0.06 * phase;  // 0.04 .. 0.52
                if (f < 0.0) f = 0.0;
                if (f > 0.85) f = 0.85;
                double s = std::sqrt(f) * win;  // side of a centered square
                dbu wx0 = static_cast<dbu>(i) * win;
                dbu wy0 = static_cast<dbu>(j) * win;
                dbu off = static_cast<dbu>((win - s) / 2.0);
                dbu x0 = wx0 + off;
                dbu y0 = wy0 + off;
                dbu x1 = x0 + static_cast<dbu>(s);
                dbu y1 = y0 + static_cast<dbu>(s);
                if (x1 > x0 && y1 > y0)
                    L.polygons.push_back(make_rect(r.layer, r.datatype, x0, y0, x1, y1));
            }
        }
        ++layer_index;
    }

    write_gds(out, L);
    BBox b = L.bbox();
    std::cout << "wrote " << out << ": " << L.polygons.size() << " polygons, die "
              << (b.width() / dppu) << " x " << (b.height() / dppu) << " um, " << rules.size()
              << " layers\n";
    return 0;
}
