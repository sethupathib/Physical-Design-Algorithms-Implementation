#include "extract.hpp"

#include <cmath>
#include <iostream>
#include <string>

static int g_fail = 0;

static void expect(bool cond, const std::string& msg) {
  if (!cond) {
    std::cerr << "FAIL: " << msg << "\n";
    ++g_fail;
  } else {
    std::cout << "ok  : " << msg << "\n";
  }
}

static void test_sheet_resistance() {
  rcx::TechFile tech = rcx::defaultTech();
  rcx::Shape s;
  s.layer = "M1";
  s.net = "n";
  s.name = "w";
  // 10 µm long, 1 µm wide → 10 squares → R = 0.08 * 10 = 0.8 Ohm
  s.rect = rcx::Rect(0, 0, 10, 1);
  double r = rcx::wireResistance(s, tech);
  expect(std::fabs(r - 0.8) < 1e-9, "M1 wire 10x1 → 0.8 Ohm");
}

static void test_via_parallel() {
  rcx::TechFile tech = rcx::defaultTech();
  rcx::Shape s;
  s.layer = "VIA1";
  s.net = "n";
  s.name = "v";
  // 0.28 x 0.14 → 2 cuts → R = 5/2 = 2.5
  s.rect = rcx::Rect(0, 0, 0.28, 0.14);
  double r = rcx::viaResistance(s, tech);
  expect(std::fabs(r - 2.5) < 1e-9, "VIA1 2-cut array → 2.5 Ohm");
}

static void test_connectivity_via_stitch() {
  rcx::Layout L;
  L.name = "t";
  rcx::Shape m1;
  m1.layer = "M1";
  m1.net = "a";
  m1.name = "m1";
  m1.rect = rcx::Rect(0, 0, 2, 0.2);

  rcx::Shape m2;
  m2.layer = "M2";
  m2.net = "a";
  m2.name = "m2";
  m2.rect = rcx::Rect(0.8, 0, 2.8, 0.2);

  rcx::Shape v;
  v.layer = "VIA1";
  v.net = "a";
  v.name = "v1";
  v.rect = rcx::Rect(0.93, 0.03, 1.07, 0.17);

  L.shapes = {m1, m2, v};
  auto nets = rcx::extractConnectivity(L);
  expect(nets.size() == 1, "via stitches M1+M2 into one net");
  expect(L.shapes[0].net == L.shapes[1].net, "both metals same net name");
}

static void test_coupling_nonzero() {
  rcx::Layout L;
  L.name = "c";
  rcx::Shape a;
  a.layer = "M1";
  a.net = "n1";
  a.name = "w1";
  a.rect = rcx::Rect(0, 0, 5, 0.2);
  rcx::Shape b;
  b.layer = "M1";
  b.net = "n2";
  b.name = "w2";
  b.rect = rcx::Rect(0, 0.4, 5, 0.6);  // gap = 0.2 µm, overlap L = 5
  L.shapes = {a, b};
  rcx::extractConnectivity(L);
  auto caps = rcx::extractCapacitance(L);
  int cc = 0;
  double cc_val = 0;
  for (const auto& c : caps) {
    if (c.kind == "coupling") {
      ++cc;
      cc_val = c.value_ff;
    }
  }
  expect(cc == 1, "one coupling cap between parallel wires");
  // C = 0.035 * 0.20 * 5 / 0.2 = 0.175 fF
  expect(std::fabs(cc_val - 0.175) < 1e-9, "coupling formula 0.175 fF");
}

static void test_full_pipeline_simple() {
  rcx::Layout L = rcx::loadLayout("examples/simple_net.lay");
  auto r = rcx::extractAll(std::move(L));
  expect(!r.resistors.empty(), "simple_net has resistors");
  expect(!r.capacitors.empty(), "simple_net has capacitors");
  expect(!r.spef.empty(), "SPEF emitted");
  expect(r.spef.find("*D_NET") != std::string::npos, "SPEF has *D_NET");
}

int main() {
  test_sheet_resistance();
  test_via_parallel();
  test_connectivity_via_stitch();
  test_coupling_nonzero();
  test_full_pipeline_simple();
  if (g_fail) {
    std::cerr << g_fail << " test(s) failed\n";
    return 1;
  }
  std::cout << "All tests passed.\n";
  return 0;
}
