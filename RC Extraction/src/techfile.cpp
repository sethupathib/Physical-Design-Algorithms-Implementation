#include "techfile.hpp"

namespace rcx {

TechFile defaultTech() {
  TechFile tech;
  tech.name = "toy_3metal";

  // Synthetic stack roughly inspired by older ~65–90 nm interconnect feel.
  // Numbers are educational — not a real PDK.
  MetalLayer m1;
  m1.name = "M1";
  m1.thickness = 0.20;
  m1.height = 0.40;
  m1.sheet_r = 0.080;
  m1.c_area = 0.086;
  m1.c_fringe = 0.045;
  m1.c_coup_k = 0.035;
  tech.addMetal(m1);

  MetalLayer m2;
  m2.name = "M2";
  m2.thickness = 0.25;
  m2.height = 0.80;
  m2.sheet_r = 0.060;
  m2.c_area = 0.043;
  m2.c_fringe = 0.050;
  m2.c_coup_k = 0.035;
  tech.addMetal(m2);

  MetalLayer m3;
  m3.name = "M3";
  m3.thickness = 0.35;
  m3.height = 1.30;
  m3.sheet_r = 0.040;
  m3.c_area = 0.027;
  m3.c_fringe = 0.055;
  m3.c_coup_k = 0.035;
  tech.addMetal(m3);

  ViaLayer v1;
  v1.name = "VIA1";
  v1.lower_metal = "M1";
  v1.upper_metal = "M2";
  v1.resistance = 5.0;
  v1.size = 0.14;
  tech.addVia(v1);

  ViaLayer v2;
  v2.name = "VIA2";
  v2.lower_metal = "M2";
  v2.upper_metal = "M3";
  v2.resistance = 4.0;
  v2.size = 0.14;
  tech.addVia(v2);

  return tech;
}

}  // namespace rcx
