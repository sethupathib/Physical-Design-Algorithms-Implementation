// Prints a per-(layer,datatype) polygon-count summary for one or more GDSII
// files. Fill emitted by this project uses datatype 10, so it is flagged as
// "FILL" to make it easy to confirm that fill happened.
#include <cstdio>
#include <map>
#include <string>
#include <utility>

#include "metalfill/gdsii.hpp"
#include "metalfill/layermap.hpp"

using namespace mf;

namespace {

// Best-effort human-readable name for the known layer numbers.
std::string layer_name(int layer) {
    if (layer == kOdLayer) return "OD";
    if (layer == kPoLayer) return "PO";
    if (layer > kMetalBaseLayer && layer <= kMetalBaseLayer + kNumMetals)
        return "M" + std::to_string(layer - kMetalBaseLayer);
    return "?";
}

void dump(const char* path) {
    Layout L = read_gds(path);
    std::map<std::pair<int, int>, long> counts;
    for (const auto& p : L.polygons) counts[{p.layer, p.datatype}]++;

    BBox b = L.bbox();
    double dppu = L.dbu_per_um();
    std::printf("=== %s ===\n", path);
    std::printf("  cell '%s', %zu polygons, bbox %.2f x %.2f um\n", L.cell_name.c_str(),
                L.polygons.size(), b.width() / dppu, b.height() / dppu);
    std::printf("  %-6s %-6s %10s   %s\n", "layer", "L/DT", "polygons", "kind");
    std::printf("  ------------------------------------------------\n");

    long design = 0, fill = 0;
    for (const auto& kv : counts) {
        int layer = kv.first.first, dt = kv.first.second;
        bool is_fill = (dt == kFillDatatype);
        if (is_fill) fill += kv.second;
        else design += kv.second;
        char ld[32];
        std::snprintf(ld, sizeof(ld), "%d/%d", layer, dt);
        std::printf("  %-6s %-6s %10ld   %s\n", layer_name(layer).c_str(), ld, kv.second,
                    is_fill ? "FILL" : "design");
    }
    std::printf("  ------------------------------------------------\n");
    std::printf("  design=%ld  fill=%ld  total=%ld\n\n", design, fill, design + fill);
}

}  // namespace

int main(int argc, char** argv) {
    if (argc < 2) {
        std::printf("usage: gdsinfo file1.gds [file2.gds ...]\n");
        return 2;
    }
    for (int i = 1; i < argc; ++i) dump(argv[i]);
    return 0;
}
