#pragma once

#include "layout.hpp"

#include <map>
#include <string>
#include <vector>

namespace rcx {

struct Resistor {
  std::string name;
  std::string net;
  std::string node_a;
  std::string node_b;
  double value_ohm = 0;
  std::string kind;  // "wire" | "via"
  std::map<std::string, double> meta;
};

double wireResistance(const Shape& shape, const TechFile& tech);
double viaResistance(const Shape& shape, const TechFile& tech);

std::vector<Resistor> extractResistance(const Layout& layout);

}  // namespace rcx
