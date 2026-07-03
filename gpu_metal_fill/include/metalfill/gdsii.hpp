#pragma once
#include <string>
#include <vector>
#include "metalfill/geometry.hpp"

namespace mf {

// A minimal in-memory representation of a single-cell GDSII layout.
struct Layout {
    std::string lib_name = "METALFILL";
    std::string cell_name = "TOP";
    // meters per database unit (UNITS second value). 1e-9 => 1 dbu = 1 nm.
    double meters_per_dbu = 1e-9;
    // user units per database unit (UNITS first value). 1e-3 => 1 user unit = 1 um.
    double user_units_per_dbu = 1e-3;

    std::vector<Polygon> polygons;

    // Database units per micron, derived from UNITS.
    double dbu_per_um() const { return 1e-6 / meters_per_dbu; }

    BBox bbox() const {
        BBox b;
        for (const auto& p : polygons) b.expand(p.bbox());
        return b;
    }
};

// Reads a GDSII file. Only BOUNDARY and BOX records are imported (as polygons);
// references (SREF/AREF) and paths are ignored. Throws std::runtime_error on
// malformed input.
Layout read_gds(const std::string& path);

// Writes a single-cell GDSII file containing all polygons.
void write_gds(const std::string& path, const Layout& layout);

}  // namespace mf
