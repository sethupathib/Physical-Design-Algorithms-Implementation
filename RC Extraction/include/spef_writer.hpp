#pragma once

#include "rc_network.hpp"

#include <string>

namespace rcx {

// Write IEEE-1481-ish SPEF (subset) for OpenSTA / educational inspection.
std::string writeSpef(const RCNetwork& net, const std::string& design_name);
void writeSpefFile(const RCNetwork& net, const std::string& design_name,
                   const std::string& path);

}  // namespace rcx
