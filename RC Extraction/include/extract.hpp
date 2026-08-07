#pragma once

#include "capacitance.hpp"
#include "connectivity.hpp"
#include "elmore.hpp"
#include "layout.hpp"
#include "rc_network.hpp"
#include "resistance.hpp"
#include "spef_writer.hpp"

#include <map>
#include <string>
#include <vector>

namespace rcx {

struct ExtractionResult {
  Layout layout;
  std::map<std::string, Net> nets;
  std::vector<Resistor> resistors;
  std::vector<Capacitor> capacitors;
  RCNetwork network;
  std::string spef;
};

// Full pipeline: layout → connectivity → R → C → RC network → SPEF
ExtractionResult extractAll(Layout layout);

std::string reportExtraction(const ExtractionResult& r);

}  // namespace rcx
