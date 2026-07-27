#include "resistance.hpp"

#include <algorithm>
#include <cmath>
#include <stdexcept>

namespace rcx {

double wireResistance(const Shape& shape, const TechFile& tech) {
  const MetalLayer& layer = tech.metal(shape.layer);
  auto lw = shape.rect.lengthWidth();
  const double length = lw.first;
  const double width = lw.second;
  if (width <= 0.0)
    throw std::runtime_error("Zero width wire on " + shape.layer);
  return layer.sheet_r * (length / width);
}

double viaResistance(const Shape& shape, const TechFile& tech) {
  const ViaLayer& vdef = tech.via(shape.layer);
  int nx = std::max(1, static_cast<int>(shape.rect.width() / vdef.size + 1e-9));
  int ny = std::max(1, static_cast<int>(shape.rect.height() / vdef.size + 1e-9));
  int n = std::max(1, nx * ny);
  return vdef.resistance / static_cast<double>(n);
}

std::vector<Resistor> extractResistance(const Layout& layout) {
  std::vector<Resistor> out;
  out.reserve(layout.shapes.size());

  for (std::size_t i = 0; i < layout.shapes.size(); ++i) {
    const Shape& shape = layout.shapes[i];
    const std::string net =
        shape.net.empty() ? ("unknown_" + std::to_string(i)) : shape.net;
    const std::string tag =
        shape.name.empty() || shape.name == "-" ? ("s" + std::to_string(i))
                                                : shape.name;

    Resistor r;
    r.net = net;

    if (shape.isVia()) {
      r.name = "Rv_" + tag;
      r.node_a = net + ":" + tag + "_bot";
      r.node_b = net + ":" + tag + "_top";
      r.value_ohm = viaResistance(shape, layout.tech);
      r.kind = "via";
      r.meta["shape_index"] = static_cast<double>(i);
    } else {
      r.name = "Rw_" + tag;
      if (shape.rect.isHorizontal()) {
        r.node_a = net + ":" + tag + "_W";
        r.node_b = net + ":" + tag + "_E";
      } else {
        r.node_a = net + ":" + tag + "_S";
        r.node_b = net + ":" + tag + "_N";
      }
      r.value_ohm = wireResistance(shape, layout.tech);
      r.kind = "wire";
      auto lw = shape.rect.lengthWidth();
      r.meta["L"] = lw.first;
      r.meta["W"] = lw.second;
      r.meta["squares"] = lw.first / lw.second;
      r.meta["shape_index"] = static_cast<double>(i);
    }
    out.push_back(r);
  }
  return out;
}

}  // namespace rcx
