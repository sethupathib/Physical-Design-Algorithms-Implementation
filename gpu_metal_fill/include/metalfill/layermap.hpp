#pragma once
#include <vector>
#include "metalfill/rules.hpp"

namespace mf {

// GDS layer numbering used by this project (illustrative; not a real PDK).
//
//   FEOL (base) layers:
//       OD (active/diffusion) = 1
//       PO (poly)            = 2
//   BEOL (metal) layers:
//       M1 .. M14            = 10 .. 23   (Mn -> layer 9 + n)
//
// Fill shapes are written on the same layer number with datatype 10.
constexpr int kOdLayer = 1;
constexpr int kPoLayer = 2;
constexpr int kMetalBaseLayer = 9;  // M1 = 10
constexpr int kNumMetals = 14;      // M1 .. M14
constexpr int kFillDatatype = 10;

inline int metal_layer(int n) { return kMetalBaseLayer + n; }  // n in [1..14]

// Builds the default layer map: 2 FEOL layers + M1..M14 BEOL layers.
//
// Lower metals use small, tight fill; upper metals use larger fill on a coarser
// pitch (mirrors real metal stacks where top layers are thicker/wider).
std::vector<FillRule> default_layermap();

}  // namespace mf
