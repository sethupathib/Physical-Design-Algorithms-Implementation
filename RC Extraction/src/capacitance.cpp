#include "capacitance.hpp"

#include <algorithm>
#include <cmath>

namespace rcx {

double areaCap(const Shape& shape, const TechFile& tech) {
  return tech.metal(shape.layer).c_area * shape.rect.area();
}

double fringeCap(const Shape& shape, const TechFile& tech) {
  auto lw = shape.rect.lengthWidth();
  return tech.metal(shape.layer).c_fringe * lw.first;
}

double couplingCap(const Shape& a, const Shape& b, const TechFile& tech,
                   std::map<std::string, double>* meta) {
  if (a.layer != b.layer || a.isVia() || b.isVia())
    return 0.0;
  if (!a.net.empty() && a.net == b.net)
    return 0.0;

  const MetalLayer& layer = tech.metal(a.layer);
  const Rect& ra = a.rect;
  const Rect& rb = b.rect;

  struct Cand {
    double gap, lov;
  };
  std::vector<Cand> cands;

  // Separated in X, overlapping in Y
  if (ra.x1 <= rb.x0 || rb.x1 <= ra.x0) {
    double gap = (ra.x1 <= rb.x0) ? (rb.x0 - ra.x1) : (ra.x0 - rb.x1);
    double y0 = std::max(ra.y0, rb.y0);
    double y1 = std::min(ra.y1, rb.y1);
    double lov = y1 - y0;
    if (gap > 0 && lov > 0)
      cands.push_back({gap, lov});
  }

  // Separated in Y, overlapping in X
  if (ra.y1 <= rb.y0 || rb.y1 <= ra.y0) {
    double gap = (ra.y1 <= rb.y0) ? (rb.y0 - ra.y1) : (ra.y0 - rb.y1);
    double x0 = std::max(ra.x0, rb.x0);
    double x1 = std::min(ra.x1, rb.x1);
    double lov = x1 - x0;
    if (gap > 0 && lov > 0)
      cands.push_back({gap, lov});
  }

  if (cands.empty())
    return 0.0;

  Cand best = *std::min_element(
      cands.begin(), cands.end(),
      [](const Cand& u, const Cand& v) { return u.gap < v.gap; });

  if (best.gap > 2.0)  // µm search radius
    return 0.0;

  double c = layer.c_coup_k * layer.thickness * best.lov / best.gap;
  if (meta) {
    (*meta)["gap"] = best.gap;
    (*meta)["overlap"] = best.lov;
  }
  return c;
}

std::vector<Capacitor> extractCapacitance(const Layout& layout) {
  std::vector<Capacitor> caps;
  std::vector<std::size_t> metals = layout.metalIndices();

  for (std::size_t i : metals) {
    const Shape& shape = layout.shapes[i];
    const std::string net =
        shape.net.empty() ? ("unknown_" + std::to_string(i)) : shape.net;
    const std::string tag =
        shape.name.empty() || shape.name == "-" ? ("s" + std::to_string(i))
                                                : shape.name;
    const std::string node = net + ":" + tag + "_MID";

    Capacitor ca;
    ca.name = "Ca_" + tag;
    ca.net_pos = net;
    ca.node_pos = node;
    ca.value_ff = areaCap(shape, layout.tech);
    ca.kind = "area";
    ca.meta["shape_index"] = static_cast<double>(i);
    caps.push_back(ca);

    Capacitor cf;
    cf.name = "Cf_" + tag;
    cf.net_pos = net;
    cf.node_pos = node;
    cf.value_ff = fringeCap(shape, layout.tech);
    cf.kind = "fringe";
    cf.meta["shape_index"] = static_cast<double>(i);
    caps.push_back(cf);
  }

  int cc_id = 0;
  for (std::size_t ii = 0; ii < metals.size(); ++ii) {
    std::size_t i = metals[ii];
    const Shape& a = layout.shapes[i];
    for (std::size_t jj = ii + 1; jj < metals.size(); ++jj) {
      std::size_t j = metals[jj];
      const Shape& b = layout.shapes[j];
      std::map<std::string, double> meta;
      double c = couplingCap(a, b, layout.tech, &meta);
      if (c <= 0.0)
        continue;

      const std::string na =
          a.net.empty() ? ("unknown_" + std::to_string(i)) : a.net;
      const std::string nb =
          b.net.empty() ? ("unknown_" + std::to_string(j)) : b.net;
      const std::string ta =
          a.name.empty() || a.name == "-" ? ("s" + std::to_string(i)) : a.name;
      const std::string tb =
          b.name.empty() || b.name == "-" ? ("s" + std::to_string(j)) : b.name;

      Capacitor cc;
      cc.name = "Cc_" + std::to_string(cc_id++);
      cc.net_pos = na;
      cc.node_pos = na + ":" + ta + "_MID";
      cc.value_ff = c;
      cc.kind = "coupling";
      cc.net_neg = nb;
      cc.node_neg = nb + ":" + tb + "_MID";
      cc.meta = meta;
      caps.push_back(cc);
    }
  }

  return caps;
}

}  // namespace rcx
