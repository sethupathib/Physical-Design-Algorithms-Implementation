#include "metalfill/layermap.hpp"

namespace mf {

std::vector<FillRule> default_layermap() {
    std::vector<FillRule> rules;

    // ---- FEOL / base layers ------------------------------------------------
    {
        FillRule od;
        od.name = "OD";
        od.layer = kOdLayer;
        od.fill_datatype = kFillDatatype;
        od.window_um = 20.0;
        od.step_um = 20.0;
        od.min_density = 0.25;
        od.max_density = 0.75;
        od.max_gradient = 0.20;
        od.fill_w_um = 0.5;
        od.fill_h_um = 0.5;
        od.fill_pitch_x_um = 0.625;  // 1.25x fill -> ~64% max coverage
        od.fill_pitch_y_um = 0.625;
        od.keepout_um = 0.20;
        od.min_area_um2 = 0.25;
        od.is_beol = false;
        rules.push_back(od);

        FillRule po;
        po.name = "PO";
        po.layer = kPoLayer;
        po.fill_datatype = kFillDatatype;
        po.window_um = 20.0;
        po.step_um = 20.0;
        po.min_density = 0.20;
        po.max_density = 0.70;
        po.max_gradient = 0.20;
        po.fill_w_um = 0.4;
        po.fill_h_um = 0.4;
        po.fill_pitch_x_um = 0.5;  // 1.25x fill
        po.fill_pitch_y_um = 0.5;
        po.keepout_um = 0.15;
        po.min_area_um2 = 0.16;
        po.is_beol = false;
        rules.push_back(po);
    }

    // ---- BEOL / metal layers M1..M14 --------------------------------------
    for (int n = 1; n <= kNumMetals; ++n) {
        FillRule m;
        m.name = "M" + std::to_string(n);
        m.layer = metal_layer(n);
        m.fill_datatype = kFillDatatype;
        m.window_um = 20.0;
        m.step_um = 20.0;
        m.min_density = 0.30;
        m.max_density = 0.80;
        m.max_gradient = 0.15;
        m.keepout_um = (n <= 6) ? 0.10 : 0.30;
        m.is_beol = true;

        // Pitch is kept at 1.25x the fill size (and a divisor of the 20um
        // window) so fill can reach ~64% coverage -- comfortably above the min
        // density target -- while windows/pitch stay lattice-coherent.
        if (n <= 6) {
            // Lower/thin metals: small dense fill.
            m.fill_w_um = 0.20;
            m.fill_h_um = 0.20;
            m.fill_pitch_x_um = 0.25;
            m.fill_pitch_y_um = 0.25;
            m.min_area_um2 = 0.04;
        } else if (n <= 10) {
            m.fill_w_um = 0.40;
            m.fill_h_um = 0.40;
            m.fill_pitch_x_um = 0.50;
            m.fill_pitch_y_um = 0.50;
            m.min_area_um2 = 0.16;
        } else {
            // Upper/thick metals: large fill on a coarse pitch.
            m.fill_w_um = 0.80;
            m.fill_h_um = 0.80;
            m.fill_pitch_x_um = 1.00;
            m.fill_pitch_y_um = 1.00;
            m.min_area_um2 = 0.64;
        }
        rules.push_back(m);
    }

    return rules;
}

}  // namespace mf
