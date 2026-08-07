// Reads a GDSII, runs recursive-partitioned FEOL/BEOL metal fill, writes the
// filled GDSII and a text report.
#include <cstdlib>
#include <fstream>
#include <iostream>
#include <string>

#include "metalfill/engine.hpp"
#include "metalfill/gdsii.hpp"
#include "metalfill/layermap.hpp"

using namespace mf;

int main(int argc, char** argv) {
    std::string in, out = "filled.gds", report;
    EngineConfig cfg;
    for (int i = 1; i < argc; ++i) {
        std::string a = argv[i];
        if ((a == "-i" || a == "--in") && i + 1 < argc)
            in = argv[++i];
        else if ((a == "-o" || a == "--out") && i + 1 < argc)
            out = argv[++i];
        else if ((a == "-r" || a == "--report") && i + 1 < argc)
            report = argv[++i];
        else if (a == "--iters" && i + 1 < argc)
            cfg.max_iterations = std::atoi(argv[++i]);
        else if (a == "--gpu")
            cfg.prefer_gpu = true;
        else if (a == "-h" || a == "--help") {
            std::cout << "usage: run_fill -i in.gds [-o filled.gds] [-r report.txt] "
                         "[--iters N] [--gpu]\n";
            return 0;
        } else if (in.empty()) {
            in = a;
        }
    }
    if (in.empty()) {
        std::cerr << "error: no input GDS (use -i in.gds)\n";
        return 2;
    }

    Layout layout = read_gds(in);
    std::cout << "read " << in << ": " << layout.polygons.size() << " polygons\n";

    auto rules = default_layermap();
    FillSummary summary = run_fill(layout, rules, cfg);

    write_gds(out, layout);
    std::string rpt = format_report(summary);
    std::cout << rpt;
    std::cout << "wrote filled GDS: " << out << " (" << layout.polygons.size() << " polygons)\n";
    if (!report.empty()) {
        std::ofstream f(report);
        f << rpt;
        std::cout << "wrote report: " << report << "\n";
    }
    return summary.total_violations() == 0 ? 0 : 1;
}
