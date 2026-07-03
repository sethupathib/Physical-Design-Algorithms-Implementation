#pragma once
#include <string>
#include <vector>

namespace mf {

// Fill rules for a single mask layer. Distances are given in microns and are
// converted to database units at runtime using the layout UNITS.
//
// A layer is identified by its GDS (layer, datatype). Fill geometry is emitted
// on the same GDS layer number but tagged with `fill_datatype` so that dummy
// fill can be distinguished (and stripped) later.
struct FillRule {
    std::string name;        // human readable, e.g. "M1", "OD"
    int layer = 0;           // GDS layer of the existing (drawn) geometry
    int datatype = 0;        // GDS datatype of the existing geometry
    int fill_datatype = 10;  // GDS datatype used to tag emitted fill shapes

    // Density window (CMP planarity is evaluated over a sliding window).
    double window_um = 20.0;  // square window edge length
    double step_um = 20.0;    // window step (== window_um => non-overlapping tiles)

    // Density targets. CMP needs the metal density to stay inside [min, max]
    // and the window-to-window gradient to stay bounded.
    double min_density = 0.30;
    double max_density = 0.80;
    double max_gradient = 0.20;  // max |density(tile) - density(neighbor)|; <=0 disables

    // Fill shape geometry.
    double fill_w_um = 0.4;
    double fill_h_um = 0.4;
    double fill_pitch_x_um = 0.8;
    double fill_pitch_y_um = 0.8;

    // Design-rule spacing between fill and any existing geometry (keep-out halo).
    double keepout_um = 0.15;

    // Minimum legal fill-shape area (sanity DRC on the fill shape itself).
    double min_area_um2 = 0.04;

    // BEOL (metal) layers are flagged for the GPU-offloaded processing path.
    bool is_beol = false;
};

}  // namespace mf
