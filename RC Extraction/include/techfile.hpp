#pragma once

#include <algorithm>
#include <map>
#include <string>
#include <utility>
#include <vector>

namespace rcx {

struct MetalLayer {
  std::string name;
  double thickness = 0;  // µm metal thickness T
  double height = 0;     // µm bottom above reference
  double sheet_r = 0;    // Ω/□
  double c_area = 0;     // fF/µm²
  double c_fringe = 0;   // fF/µm (along wire length)
  double c_coup_k = 0;   // coupling scale: C = k * T * Lov / S  (fF)
};

struct ViaLayer {
  std::string name;
  std::string lower_metal;
  std::string upper_metal;
  double resistance = 0;  // Ω per cut
  double size = 0.14;     // µm square cut edge
};

class TechFile {
 public:
  std::string name;
  std::map<std::string, MetalLayer> metals;
  std::map<std::string, ViaLayer> vias;

  void addMetal(const MetalLayer& m) { metals[m.name] = m; }
  void addVia(const ViaLayer& v) { vias[v.name] = v; }

  const MetalLayer& metal(const std::string& n) const { return metals.at(n); }
  const ViaLayer& via(const std::string& n) const { return vias.at(n); }

  const ViaLayer* viaBetween(const std::string& a, const std::string& b) const {
    for (const auto& kv : vias) {
      const auto& v = kv.second;
      if ((v.lower_metal == a && v.upper_metal == b) ||
          (v.lower_metal == b && v.upper_metal == a))
        return &v;
    }
    return nullptr;
  }

  std::vector<std::string> metalOrder() const {
    std::vector<std::pair<double, std::string>> tmp;
    for (const auto& kv : metals)
      tmp.push_back({kv.second.height, kv.first});
    std::sort(tmp.begin(), tmp.end());
    std::vector<std::string> out;
    for (auto& t : tmp)
      out.push_back(t.second);
    return out;
  }
};

// Synthetic 3-metal stack (educational, not a real PDK)
TechFile defaultTech();

}  // namespace rcx
