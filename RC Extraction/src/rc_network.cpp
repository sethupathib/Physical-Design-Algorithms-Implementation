#include "rc_network.hpp"

#include <cmath>
#include <map>
#include <set>
#include <string>
#include <vector>

namespace rcx {
namespace {

class UnionFindStr {
 public:
  std::string find(const std::string& x) {
    if (!parent_.count(x))
      parent_[x] = x;
    if (parent_[x] != x)
      parent_[x] = find(parent_[x]);
    return parent_[x];
  }

  void unite(const std::string& a, const std::string& b) {
    std::string ra = find(a), rb = find(b);
    if (ra == rb)
      return;
    if (ra.size() <= rb.size())
      parent_[rb] = ra;
    else
      parent_[ra] = rb;
  }

 private:
  std::map<std::string, std::string> parent_;
};

std::string shapeTag(const Shape& s, std::size_t i) {
  if (s.name.empty() || s.name == "-")
    return "s" + std::to_string(i);
  return s.name;
}

void wireEnds(const Shape& s, double& ax, double& ay, double& bx, double& by) {
  if (s.rect.isHorizontal()) {
    ax = s.rect.x0;
    ay = s.rect.cy();
    bx = s.rect.x1;
    by = s.rect.cy();
  } else {
    ax = s.rect.cx();
    ay = s.rect.y0;
    bx = s.rect.cx();
    by = s.rect.y1;
  }
}

std::string endNodeA(const std::string& net, const std::string& tag,
                     const Shape& s) {
  return net + ":" + tag + (s.rect.isHorizontal() ? "_W" : "_S");
}

std::string endNodeB(const std::string& net, const std::string& tag,
                     const Shape& s) {
  return net + ":" + tag + (s.rect.isHorizontal() ? "_E" : "_N");
}

std::string midNode(const std::string& net, const std::string& tag) {
  return net + ":" + tag + "_MID";
}

std::string nearestWireNode(double x, double y, const Shape& m,
                            const std::string& mA, const std::string& mB,
                            const std::string& mM) {
  double ax, ay, bx, by;
  wireEnds(m, ax, ay, bx, by);
  double dA = std::hypot(x - ax, y - ay);
  double dB = std::hypot(x - bx, y - by);
  double dM = std::hypot(x - m.rect.cx(), y - m.rect.cy());
  if (dA <= dB && dA <= dM)
    return mA;
  if (dB <= dM)
    return mB;
  return mM;
}

}  // namespace

RCNetwork buildRCNetwork(const Layout& layout,
                         const std::vector<Resistor>& resistors,
                         const std::vector<Capacitor>& capacitors) {
  RCNetwork net;
  UnionFindStr uf;

  struct PendingR {
    std::string name, net, a, b, kind;
    double ohms;
  };
  std::vector<PendingR> pending;

  // π-model: wire R → R/2 — MID — R/2
  for (const auto& r : resistors) {
    uf.find(r.node_a);
    uf.find(r.node_b);
    if (r.kind == "wire") {
      auto pos = r.node_a.find(':');
      std::string netname = r.node_a.substr(0, pos);
      std::string rest = r.node_a.substr(pos + 1);
      auto us = rest.find_last_of('_');
      std::string tag = rest.substr(0, us);
      std::string mid = midNode(netname, tag);
      uf.find(mid);
      pending.push_back(
          {r.name + "_1", r.net, r.node_a, mid, "wire", r.value_ohm * 0.5});
      pending.push_back(
          {r.name + "_2", r.net, mid, r.node_b, "wire", r.value_ohm * 0.5});
    } else {
      pending.push_back(
          {r.name, r.net, r.node_a, r.node_b, r.kind, r.value_ohm});
    }
  }

  for (const auto& c : capacitors) {
    uf.find(c.node_pos);
    if (c.kind == "coupling")
      uf.find(c.node_neg);
  }

  const auto metals = layout.metalIndices();

  // Merge abutting metal endpoints on the same net/layer
  for (std::size_t ii = 0; ii < metals.size(); ++ii) {
    std::size_t i = metals[ii];
    const Shape& a = layout.shapes[i];
    const std::string ta = shapeTag(a, i);
    double aax, aay, abx, aby;
    wireEnds(a, aax, aay, abx, aby);
    std::string aA = endNodeA(a.net, ta, a);
    std::string aB = endNodeB(a.net, ta, a);
    std::string aM = midNode(a.net, ta);

    for (std::size_t jj = ii + 1; jj < metals.size(); ++jj) {
      std::size_t j = metals[jj];
      const Shape& b = layout.shapes[j];
      if (a.net != b.net || a.layer != b.layer)
        continue;
      if (!a.rect.expanded(1e-9).overlaps(b.rect))
        continue;

      const std::string tb = shapeTag(b, j);
      double bax, bay, bbx, bby;
      wireEnds(b, bax, bay, bbx, bby);
      std::string bA = endNodeA(b.net, tb, b);
      std::string bB = endNodeB(b.net, tb, b);
      std::string bM = midNode(b.net, tb);

      auto mergeIfInside = [&](const std::string& node, double x, double y,
                               const Shape& other, const std::string& oA,
                               const std::string& oB, const std::string& oM) {
        if (other.rect.contains(x, y))
          uf.unite(node, nearestWireNode(x, y, other, oA, oB, oM));
      };

      mergeIfInside(aA, aax, aay, b, bA, bB, bM);
      mergeIfInside(aB, abx, aby, b, bA, bB, bM);
      mergeIfInside(bA, bax, bay, a, aA, aB, aM);
      mergeIfInside(bB, bbx, bby, a, aA, aB, aM);
    }
  }

  // Via terminals → overlapping metals
  for (std::size_t vi : layout.viaIndices()) {
    const Shape& via = layout.shapes[vi];
    const std::string tag = shapeTag(via, vi);
    const std::string bot = via.net + ":" + tag + "_bot";
    const std::string top = via.net + ":" + tag + "_top";
    auto vit = layout.tech.vias.find(via.layer);
    if (vit == layout.tech.vias.end())
      continue;
    const ViaLayer& vd = vit->second;
    const double vx = via.rect.cx(), vy = via.rect.cy();

    for (std::size_t mi : metals) {
      const Shape& m = layout.shapes[mi];
      if (m.net != via.net || !via.rect.overlaps(m.rect))
        continue;
      const std::string mt = shapeTag(m, mi);
      std::string mA = endNodeA(m.net, mt, m);
      std::string mB = endNodeB(m.net, mt, m);
      std::string mM = midNode(m.net, mt);
      std::string attach = nearestWireNode(vx, vy, m, mA, mB, mM);
      if (m.layer == vd.lower_metal)
        uf.unite(bot, attach);
      if (m.layer == vd.upper_metal)
        uf.unite(top, attach);
    }
  }

  // Pins → containing metal
  for (const auto& pin : layout.pins) {
    std::string pin_node = pin.net + ":PIN:" + pin.name;
    uf.find(pin_node);
    for (std::size_t mi : metals) {
      const Shape& m = layout.shapes[mi];
      if (m.net != pin.net || m.layer != pin.layer)
        continue;
      if (!m.rect.contains(pin.x, pin.y))
        continue;
      const std::string mt = shapeTag(m, mi);
      std::string mA = endNodeA(m.net, mt, m);
      std::string mB = endNodeB(m.net, mt, m);
      std::string mM = midNode(m.net, mt);
      uf.unite(pin_node, nearestWireNode(pin.x, pin.y, m, mA, mB, mM));
      break;
    }
  }

  auto canon = [&](const std::string& n) { return uf.find(n); };

  std::set<std::string> seen;
  auto addNode = [&](const std::string& raw, const std::string& netname) {
    std::string c = canon(raw);
    if (seen.count(c))
      return;
    seen.insert(c);
    RCNode node;
    node.name = c;
    node.net = netname;
    net.nodes[c] = node;
  };

  for (const auto& pr : pending) {
    addNode(pr.a, pr.net);
    addNode(pr.b, pr.net);
    std::string ca = canon(pr.a), cb = canon(pr.b);
    if (ca == cb)
      continue;
    RCEdgeR e;
    e.name = pr.name;
    e.net = pr.net;
    e.node_a = ca;
    e.node_b = cb;
    e.value_ohm = pr.ohms;
    e.kind = pr.kind;
    net.resistors.push_back(e);
  }

  for (const auto& pin : layout.pins) {
    std::string pin_node = pin.net + ":PIN:" + pin.name;
    std::string c = canon(pin_node);
    addNode(pin_node, pin.net);
    net.nodes[c].is_pin = true;
    net.nodes[c].pin_name = pin.name;
    net.nodes[c].pin_dir = pin.direction;
  }

  for (const auto& c : capacitors) {
    RCCap out;
    out.name = c.name;
    out.kind = c.kind;
    out.value_ff = c.value_ff;
    out.net_pos = c.net_pos;
    out.node_pos = canon(c.node_pos);
    addNode(c.node_pos, c.net_pos);

    if (c.kind == "coupling") {
      out.net_neg = c.net_neg;
      out.node_neg = canon(c.node_neg);
      addNode(c.node_neg, c.net_neg);
      net.net_total_c_ff[c.net_pos] += c.value_ff;
      net.net_total_c_ff[c.net_neg] += c.value_ff;
    } else {
      out.net_neg = "GROUND";
      out.node_neg = "GROUND";
      net.net_total_c_ff[c.net_pos] += c.value_ff;
    }
    net.capacitors.push_back(out);
  }

  return net;
}

}  // namespace rcx
