#include "spef_writer.hpp"

#include <fstream>
#include <iomanip>
#include <map>
#include <set>
#include <sstream>
#include <stdexcept>
#include <vector>

namespace rcx {

std::string writeSpef(const RCNetwork& net, const std::string& design_name) {
  std::ostringstream out;
  out << std::fixed << std::setprecision(6);

  out << "*SPEF \"IEEE 1481-1998\"\n";
  out << "*DESIGN \"" << design_name << "\"\n";
  out << "*DATE \"N/A\"\n";
  out << "*VENDOR \"RC-Extraction-Teaching\"\n";
  out << "*PROGRAM \"rcx_extract\"\n";
  out << "*VERSION \"1.0\"\n";
  out << "*DESIGN_FLOW \"NETLIST_TYPE_VERILOG\"\n";
  out << "*DIVIDER /\n";
  out << "*DELIMITER :\n";
  out << "*BUS_DELIMITER [ ]\n";
  out << "*T_UNIT 1 PS\n";
  out << "*C_UNIT 1 FF\n";
  out << "*R_UNIT 1 OHM\n";
  out << "*L_UNIT 1 HENRY\n\n";

  // Collect nets
  std::set<std::string> nets;
  for (const auto& kv : net.nodes)
    if (!kv.second.net.empty())
      nets.insert(kv.second.net);

  // Name map (*NAME_MAP) — optional; use expanded names for clarity
  out << "*NAME_MAP\n";
  int nid = 1;
  std::map<std::string, int> name_id;
  for (const auto& n : nets) {
    name_id[n] = nid;
    out << "*" << nid << " " << n << "\n";
    ++nid;
  }
  out << "\n";

  for (const auto& netname : nets) {
    double total_c = 0.0;
    auto itc = net.net_total_c_ff.find(netname);
    if (itc != net.net_total_c_ff.end())
      total_c = itc->second;

    out << "*D_NET " << netname << " " << total_c << "\n";

    // Connections (pins)
    out << "*CONN\n";
    bool any_pin = false;
    for (const auto& kv : net.nodes) {
      const RCNode& n = kv.second;
      if (n.net != netname || !n.is_pin)
        continue;
      any_pin = true;
      // *I <pin> <dir>
      out << "*I " << n.pin_name << " " << n.pin_dir << "\n";
    }
    if (!any_pin)
      out << "*P " << netname << "_orphan B\n";

    // Caps
    out << "*CAP\n";
    int cid = 1;
    for (const auto& c : net.capacitors) {
      if (c.kind == "coupling") {
        if (c.net_pos != netname && c.net_neg != netname)
          continue;
        // Emit coupling once, from the lexicographically smaller net
        if (c.net_pos != netname)
          continue;
        if (c.net_pos > c.net_neg)
          continue;
        out << cid++ << " " << c.node_pos << " " << c.node_neg << " "
            << c.value_ff << "\n";
      } else {
        if (c.net_pos != netname)
          continue;
        out << cid++ << " " << c.node_pos << " " << c.value_ff << "\n";
      }
    }

    // Resistors
    out << "*RES\n";
    int rid = 1;
    for (const auto& r : net.resistors) {
      if (r.net != netname)
        continue;
      out << rid++ << " " << r.node_a << " " << r.node_b << " " << r.value_ohm
          << "\n";
    }

    out << "*END\n\n";
  }

  return out.str();
}

void writeSpefFile(const RCNetwork& net, const std::string& design_name,
                   const std::string& path) {
  std::ofstream f(path);
  if (!f)
    throw std::runtime_error("Cannot write SPEF: " + path);
  f << writeSpef(net, design_name);
}

}  // namespace rcx
