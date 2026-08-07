#pragma once

#include "layout.hpp"

#include <map>
#include <set>
#include <string>
#include <vector>

namespace rcx {

struct Net {
  std::string name;
  std::set<std::size_t> shape_indices;
};

// Geometric connectivity: abutting same-layer metals + via stitches → nets.
// Stamps Shape::net on every shape. Returns map netName → Net.
std::map<std::string, Net> extractConnectivity(Layout& layout);

std::string summarizeConnectivity(const Layout& layout,
                                  const std::map<std::string, Net>& nets);

}  // namespace rcx
