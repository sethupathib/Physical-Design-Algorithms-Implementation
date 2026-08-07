#pragma once

#include "geometry.hpp"
#include "techfile.hpp"

#include <string>
#include <vector>

namespace rcx {

struct Layout {
  std::string name;
  std::vector<Shape> shapes;
  std::vector<Pin> pins;
  TechFile tech;

  Layout() : tech(defaultTech()) {}

  std::vector<std::size_t> metalIndices() const {
    std::vector<std::size_t> idx;
    for (std::size_t i = 0; i < shapes.size(); ++i)
      if (!shapes[i].isVia())
        idx.push_back(i);
    return idx;
  }

  std::vector<std::size_t> viaIndices() const {
    std::vector<std::size_t> idx;
    for (std::size_t i = 0; i < shapes.size(); ++i)
      if (shapes[i].isVia())
        idx.push_back(i);
    return idx;
  }
};

// Simple line-oriented layout format (.lay) — no external JSON dependency.
//
//   NAME design_name
//   METAL <layer> <net> <name> <x0> <y0> <x1> <y1>
//   VIA   <layer> <net> <name> <x0> <y0> <x1> <y1>
//   PIN   <pinName> <net> <layer> <dir> <x> <y>
//   # comments allowed
Layout loadLayout(const std::string& path);
void saveLayout(const Layout& layout, const std::string& path);

}  // namespace rcx
