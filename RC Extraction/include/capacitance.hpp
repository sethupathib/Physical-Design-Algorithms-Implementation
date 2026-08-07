#pragma once

#include "layout.hpp"

#include <map>
#include <string>
#include <vector>

namespace rcx {

struct Capacitor {
  std::string name;
  std::string net_pos;
  std::string node_pos;
  double value_ff = 0;
  std::string kind;  // "area" | "fringe" | "coupling"
  std::string net_neg = "GROUND";
  std::string node_neg = "GROUND";
  std::map<std::string, double> meta;
};

double areaCap(const Shape& shape, const TechFile& tech);
double fringeCap(const Shape& shape, const TechFile& tech);

// Returns coupling C in fF (0 if none). Fills meta with gap/overlap.
double couplingCap(const Shape& a, const Shape& b, const TechFile& tech,
                   std::map<std::string, double>* meta = nullptr);

std::vector<Capacitor> extractCapacitance(const Layout& layout);

}  // namespace rcx
