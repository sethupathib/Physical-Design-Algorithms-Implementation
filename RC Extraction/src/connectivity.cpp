#include "connectivity.hpp"

#include <cctype>
#include <sstream>

namespace rcx {
namespace {

class UnionFind {
 public:
  explicit UnionFind(std::size_t n) : parent_(n), rank_(n, 0) {
    for (std::size_t i = 0; i < n; ++i)
      parent_[i] = i;
  }

  std::size_t find(std::size_t x) {
    while (parent_[x] != x) {
      parent_[x] = parent_[parent_[x]];
      x = parent_[x];
    }
    return x;
  }

  void unite(std::size_t a, std::size_t b) {
    a = find(a);
    b = find(b);
    if (a == b)
      return;
    if (rank_[a] < rank_[b])
      parent_[a] = b;
    else if (rank_[a] > rank_[b])
      parent_[b] = a;
    else {
      parent_[b] = a;
      rank_[a]++;
    }
  }

 private:
  std::vector<std::size_t> parent_;
  std::vector<int> rank_;
};

bool sameLayerTouch(const Shape& a, const Shape& b, double tol = 1e-9) {
  if (a.layer != b.layer)
    return false;
  return a.rect.expanded(tol).overlaps(b.rect);
}

bool viaConnects(const Shape& via, const Shape& metal, const TechFile& tech) {
  auto it = tech.vias.find(via.layer);
  if (it == tech.vias.end())
    return false;
  const ViaLayer& v = it->second;
  if (metal.layer != v.lower_metal && metal.layer != v.upper_metal)
    return false;
  return via.rect.overlaps(metal.rect);
}

}  // namespace

std::map<std::string, Net> extractConnectivity(Layout& layout) {
  const std::size_t n = layout.shapes.size();
  UnionFind uf(n);

  // 1) Same-layer metal abutment / overlap
  for (std::size_t i = 0; i < n; ++i) {
    if (layout.shapes[i].isVia())
      continue;
    for (std::size_t j = i + 1; j < n; ++j) {
      if (layout.shapes[j].isVia())
        continue;
      if (sameLayerTouch(layout.shapes[i], layout.shapes[j]))
        uf.unite(i, j);
    }
  }

  // 2) Via stitches adjacent metals
  for (std::size_t vi = 0; vi < n; ++vi) {
    if (!layout.shapes[vi].isVia())
      continue;
    for (std::size_t mi = 0; mi < n; ++mi) {
      if (layout.shapes[mi].isVia())
        continue;
      if (viaConnects(layout.shapes[vi], layout.shapes[mi], layout.tech))
        uf.unite(vi, mi);
    }
  }

  std::map<std::size_t, std::vector<std::size_t>> groups;
  for (std::size_t i = 0; i < n; ++i)
    groups[uf.find(i)].push_back(i);

  // Pin location → preferred net name
  std::map<std::size_t, std::string> pin_hints;
  for (const auto& pin : layout.pins) {
    for (std::size_t i = 0; i < n; ++i) {
      const Shape& s = layout.shapes[i];
      if (s.isVia())
        continue;
      if (s.layer == pin.layer && s.rect.contains(pin.x, pin.y))
        pin_hints[i] = pin.net;
    }
  }

  std::map<std::string, Net> nets;
  std::set<std::string> used;
  int auto_id = 0;

  for (const auto& g : groups) {
    const auto& members = g.second;
    std::vector<std::string> candidates;
    for (std::size_t i : members) {
      if (!layout.shapes[i].net.empty() && layout.shapes[i].net != "-")
        candidates.push_back(layout.shapes[i].net);
      auto ph = pin_hints.find(i);
      if (ph != pin_hints.end())
        candidates.push_back(ph->second);
    }

    std::string name;
    for (const auto& c : candidates) {
      if (!used.count(c)) {
        name = c;
        break;
      }
    }
    if (name.empty()) {
      do {
        name = "net_" + std::to_string(auto_id++);
      } while (used.count(name));
    }

    used.insert(name);
    Net net;
    net.name = name;
    for (std::size_t i : members) {
      net.shape_indices.insert(i);
      layout.shapes[i].net = name;
    }
    nets[name] = net;
  }

  return nets;
}

std::string summarizeConnectivity(const Layout& layout,
                                  const std::map<std::string, Net>& nets) {
  std::ostringstream oss;
  oss << "Connectivity: " << nets.size() << " net(s)\n";
  for (const auto& kv : nets) {
    int metals = 0, vias = 0;
    std::set<std::string> layers;
    for (std::size_t i : kv.second.shape_indices) {
      if (layout.shapes[i].isVia())
        ++vias;
      else {
        ++metals;
        layers.insert(layout.shapes[i].layer);
      }
    }
    oss << "  " << kv.first << ": " << metals << " metal rect(s) on [";
    bool first = true;
    for (const auto& L : layers) {
      if (!first)
        oss << ",";
      first = false;
      oss << L;
    }
    oss << "], " << vias << " via(s)\n";
  }
  return oss.str();
}

}  // namespace rcx
