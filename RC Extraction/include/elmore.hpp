#pragma once

#include "rc_network.hpp"

#include <map>
#include <string>
#include <vector>

namespace rcx {

struct ElmoreResult {
  std::string driver_node;
  std::map<std::string, double> delay_ps;  // node → Elmore delay (ps)
  std::map<std::string, double> downstream_c_ff;
};

// Elmore delay on an RC tree. driver_pin is a pin name (e.g. "U1:Z") or node.
// Assumes the net is a tree rooted at the driver (typical for digital nets).
ElmoreResult elmoreDelay(const RCNetwork& net, const std::string& net_name,
                         const std::string& driver_pin);

std::string formatElmore(const ElmoreResult& r);

}  // namespace rcx
