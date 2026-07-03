#pragma once
#include <string>
#include <vector>
#include "metalfill/backend.hpp"
#include "metalfill/drc.hpp"
#include "metalfill/gdsii.hpp"
#include "metalfill/rules.hpp"

namespace mf {

// Per-layer result of the fill run.
struct LayerResult {
    std::string name;
    int layer = 0;
    bool is_beol = false;
    int existing_polys = 0;
    int fill_shapes = 0;
    int partitions = 0;
    double density_before_min = 0, density_before_mean = 0, density_before_max = 0;
    double density_after_min = 0, density_after_mean = 0, density_after_max = 0;
    int iterations = 0;
    DrcReport drc;
    double seconds = 0.0;
};

struct EngineConfig {
    // Raster resolution in database units. Smaller = more accurate + more memory.
    dbu grid_cell_dbu = 0;   // 0 => auto (derived from smallest fill pitch)
    int max_iterations = 3;  // iterative fill/DRC passes per layer
    int max_leaf = 2;        // partition leaf size (align-units per side)
    bool prefer_gpu = false; // offload BEOL to CUDA backend if available
    double fill_headroom = 0.02;  // aim slightly above min_density
    double grad_headroom = 0.02;  // overshoot gradient target to beat discretization
};

struct FillSummary {
    std::string backend;
    std::vector<LayerResult> layers;
    double total_seconds = 0.0;
    int total_violations() const;
    int total_fill_shapes() const;
};

// Runs FEOL + BEOL fill over `layout` using `rules`. Fill polygons are appended
// to `layout` (tagged with each rule's fill_datatype). BEOL layers are processed
// through the (optionally GPU) backend.
FillSummary run_fill(Layout& layout, const std::vector<FillRule>& rules,
                     const EngineConfig& cfg);

// Renders a human-readable text report.
std::string format_report(const FillSummary& summary);

}  // namespace mf
