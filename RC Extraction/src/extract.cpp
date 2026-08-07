#include "extract.hpp"

#include <iomanip>
#include <sstream>

namespace rcx {

ExtractionResult extractAll(Layout layout) {
  ExtractionResult r;
  r.nets = extractConnectivity(layout);
  r.resistors = extractResistance(layout);
  r.capacitors = extractCapacitance(layout);
  r.network = buildRCNetwork(layout, r.resistors, r.capacitors);
  r.spef = writeSpef(r.network, layout.name);
  r.layout = std::move(layout);
  return r;
}

std::string reportExtraction(const ExtractionResult& r) {
  std::ostringstream oss;
  oss << std::fixed << std::setprecision(4);
  oss << "=== RC Extraction Report: " << r.layout.name << " ===\n\n";
  oss << summarizeConnectivity(r.layout, r.nets) << "\n";

  oss << "Resistance elements (" << r.resistors.size() << "):\n";
  for (const auto& res : r.resistors) {
    oss << "  " << res.name << "  [" << res.kind << "]  " << res.value_ohm
        << " Ohm";
    if (res.kind == "wire" && res.meta.count("squares"))
      oss << "  (" << res.meta.at("squares") << " squares, L="
          << res.meta.at("L") << " W=" << res.meta.at("W") << ")";
    oss << "\n";
  }
  oss << "\n";

  double c_area = 0, c_fringe = 0, c_coup = 0;
  oss << "Capacitance elements (" << r.capacitors.size() << "):\n";
  for (const auto& c : r.capacitors) {
    oss << "  " << c.name << "  [" << c.kind << "]  " << c.value_ff << " fF";
    if (c.kind == "coupling")
      oss << "  (" << c.net_pos << " <-> " << c.net_neg << ")";
    oss << "\n";
    if (c.kind == "area")
      c_area += c.value_ff;
    else if (c.kind == "fringe")
      c_fringe += c.value_ff;
    else
      c_coup += c.value_ff;
  }
  oss << "  totals: area=" << c_area << " fringe=" << c_fringe
      << " coupling=" << c_coup << " fF\n\n";

  oss << "RC network: " << r.network.nodes.size() << " nodes, "
      << r.network.resistors.size() << " R, " << r.network.capacitors.size()
      << " C\n";
  for (const auto& kv : r.network.net_total_c_ff)
    oss << "  *D_NET " << kv.first << "  total_C=" << kv.second << " fF\n";

  return oss.str();
}

}  // namespace rcx
