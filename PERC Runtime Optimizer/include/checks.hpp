#pragma once

#include "design.hpp"

#include <string>
#include <unordered_set>
#include <utility>
#include <vector>

namespace perc {

std::vector<Violation> check_esd_clamps(
    const Design& design,
    const std::vector<std::string>* pads = nullptr);

std::vector<Violation> check_floating_gates(
    const Design& design,
    const std::unordered_set<std::string>* device_scope = nullptr);

// Build once, reuse across hierarchical block scopes.
struct FloatingGateIndex {
  std::unordered_map<std::string, int> writers;
};
FloatingGateIndex build_floating_gate_index(const Design& design);
std::vector<Violation> check_floating_gates_indexed(
    const Design& design,
    const FloatingGateIndex& index,
    const std::unordered_set<std::string>* device_scope = nullptr);

std::vector<Violation> check_p2p_resistance(
    const Design& design,
    const std::vector<std::pair<std::string, std::string>>* pairs = nullptr,
    double limit_ohm = -1.0);

std::vector<Violation> check_current_density_paths(
    const Design& design,
    const std::vector<std::string>* pads = nullptr,
    double i_peak_a = 1.0,
    double jmax_proxy = 2.0);

// Nets relevant to ESD clamp + P2P (pads, rails, clamp/IO terminals).
std::unordered_set<std::string> esd_roi_nets(const Design& design);

}  // namespace perc
