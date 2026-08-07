// Renders one layer of a GDSII to a PPM image: existing geometry, dummy fill,
// and the recursive-partition (quadtree) core boundaries. Useful for eyeballing
// what the fill engine produced.
#include <algorithm>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <fstream>
#include <string>
#include <vector>

#include "metalfill/engine.hpp"
#include "metalfill/gdsii.hpp"
#include "metalfill/layermap.hpp"
#include "metalfill/partition.hpp"
#include "metalfill/raster.hpp"

using namespace mf;

struct Img {
    int w, h;
    std::vector<uint8_t> px;  // RGB
    Img(int w_, int h_) : w(w_), h(h_), px(size_t(w_) * h_ * 3, 255) {}
    void set(int x, int y, uint8_t r, uint8_t g, uint8_t b) {
        if (x < 0 || y < 0 || x >= w || y >= h) return;
        size_t i = (size_t(y) * w + x) * 3;
        px[i] = r;
        px[i + 1] = g;
        px[i + 2] = b;
    }
    void hline(int x0, int x1, int y, uint8_t r, uint8_t g, uint8_t b) {
        for (int x = x0; x <= x1; ++x) set(x, y, r, g, b);
    }
    void vline(int x, int y0, int y1, uint8_t r, uint8_t g, uint8_t b) {
        for (int y = y0; y <= y1; ++y) set(x, y, r, g, b);
    }
    void write_ppm(const std::string& path) {
        std::ofstream os(path, std::ios::binary);
        os << "P6\n" << w << " " << h << "\n255\n";
        os.write(reinterpret_cast<char*>(px.data()), px.size());
    }
};

int main(int argc, char** argv) {
    std::string in, out = "layer.ppm";
    int target_layer = metal_layer(3);  // M3 by default
    int px_target = 900;
    for (int i = 1; i < argc; ++i) {
        std::string a = argv[i];
        if (a == "-i" && i + 1 < argc) in = argv[++i];
        else if (a == "-o" && i + 1 < argc) out = argv[++i];
        else if (a == "-l" && i + 1 < argc) target_layer = std::atoi(argv[++i]);
        else if (a == "-p" && i + 1 < argc) px_target = std::atoi(argv[++i]);
    }
    if (in.empty()) { std::fprintf(stderr, "usage: render_layer -i in.gds -o out.ppm [-l layer]\n"); return 2; }

    Layout L = read_gds(in);
    BBox area = L.bbox();
    if (!area.valid()) { std::fprintf(stderr, "empty layout\n"); return 1; }

    dbu cell = std::max<dbu>(area.width() / px_target, 1);
    Grid ge = make_grid(area, cell), gf = make_grid(area, cell);
    rasterize(ge, L.polygons, target_layer, 0);
    rasterize(gf, L.polygons, target_layer, kFillDatatype);

    int W = ge.nx, H = ge.ny;
    Img img(W, H);

    auto to_px = [&](dbu x, dbu y, int& ix, int& iy) {
        ix = int((x - area.xmin) / cell);
        iy = H - 1 - int((y - area.ymin) / cell);
    };

    // Light window grid every 20um.
    dbu win = static_cast<dbu>(20.0 * L.dbu_per_um());
    for (dbu x = area.xmin; x <= area.xmax; x += win) {
        int ix, iy;
        to_px(x, area.ymin, ix, iy);
        img.vline(ix, 0, H - 1, 235, 235, 235);
    }
    for (dbu y = area.ymin; y <= area.ymax; y += win) {
        int ix, iy;
        to_px(area.xmin, y, ix, iy);
        img.hline(0, W - 1, iy, 235, 235, 235);
    }

    // Existing geometry (navy) and fill (orange).
    for (int y = 0; y < H; ++y)
        for (int x = 0; x < W; ++x) {
            int row = H - 1 - y;
            if (ge.at(x, y)) img.set(x, row, 30, 60, 150);
            else if (gf.at(x, y)) img.set(x, row, 250, 160, 60);
        }

    // Recursive-partition (quadtree) core boundaries in red.
    dbu align = lcm_dbu(win, win);
    PartitionConfig pc;
    pc.anchor_x = area.xmin; pc.anchor_y = area.ymin;
    pc.align_x = align; pc.align_y = align;
    pc.margin = align; pc.max_leaf = 2; pc.clip = area;
    for (const auto& part : partition_recursive(area, pc)) {
        int x0, y0, x1, y1;
        to_px(part.core.xmin, part.core.ymin, x0, y0);
        to_px(part.core.xmax, part.core.ymax, x1, y1);
        if (x1 < x0) std::swap(x0, x1);
        if (y1 < y0) std::swap(y0, y1);
        img.hline(x0, x1, y0, 220, 30, 30);
        img.hline(x0, x1, y1, 220, 30, 30);
        img.vline(x0, y0, y1, 220, 30, 30);
        img.vline(x1, y0, y1, 220, 30, 30);
    }

    img.write_ppm(out);
    std::printf("wrote %s (%dx%d) layer=%d\n", out.c_str(), W, H, target_layer);
    return 0;
}
