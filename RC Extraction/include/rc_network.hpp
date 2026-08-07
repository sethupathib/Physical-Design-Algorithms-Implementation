#pragma once

#include "capacitance.hpp"
#include "layout.hpp"
#include "resistance.hpp"

#include <map>
#include <string>
#include <vector>

namespace rcx {

// After raw R/C extraction, merge geometrically touching nodes into an RC graph
// suitable for SPEF and Elmore delay.
struct RCNode {
  std::string name;
  std::string net;
  bool is_pin = false;
  std::string pin_name;
  std::string pin_dir;
};

struct RCEdgeR {
  std::string name;
  std::string net;
  std::string node_a;  // canonical names after merge
  std::string node_b;
  double value_ohm = 0;
  std::string kind;
};

struct RCCap {
  std::string name;
  std::string net_pos;
  std::string node_pos;
  double value_ff = 0;
  std::string kind;
  std::string net_neg = "GROUND";
  std::string node_neg = "GROUND";
};

struct RCNetwork {
  std::map<std::string, RCNode> nodes;  // canonical node name → node
  std::vector<RCEdgeR> resistors;
  std::vector<RCCap> capacitors;
  // Per-net total grounded C (fF), for SPEF *D_NET header
  std::map<std::string, double> net_total_c_ff;
};

RCNetwork buildRCNetwork(const Layout& layout,
                         const std::vector<Resistor>& resistors,
                         const std::vector<Capacitor>& capacitors);

}  // namespace rcx
