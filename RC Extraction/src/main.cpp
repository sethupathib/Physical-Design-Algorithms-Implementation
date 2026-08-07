#include "extract.hpp"

#include <cstdlib>
#include <fstream>
#include <iostream>
#include <string>

static void usage(const char* argv0) {
  std::cerr
      << "Usage: " << argv0 << " <layout.lay> [--spef out.spef] [--elmore NET DRIVER_PIN]\n"
      << "\n"
      << "Educational RC extractor (GDS-like layout → R/C → SPEF → Elmore).\n"
      << "\n"
      << "Layout format (.lay):\n"
      << "  NAME design\n"
      << "  METAL <layer> <net> <name> <x0> <y0> <x1> <y1>\n"
      << "  VIA   <layer> <net> <name> <x0> <y0> <x1> <y1>\n"
      << "  PIN   <pin> <net> <layer> <I|O|B> <x> <y>\n";
}

int main(int argc, char** argv) {
  if (argc < 2) {
    usage(argv[0]);
    return 1;
  }

  std::string layout_path = argv[1];
  std::string spef_path;
  std::string elmore_net, elmore_drv;
  bool do_elmore = false;

  for (int i = 2; i < argc; ++i) {
    std::string a = argv[i];
    if (a == "--spef" && i + 1 < argc) {
      spef_path = argv[++i];
    } else if (a == "--elmore" && i + 2 < argc) {
      do_elmore = true;
      elmore_net = argv[++i];
      elmore_drv = argv[++i];
    } else if (a == "-h" || a == "--help") {
      usage(argv[0]);
      return 0;
    } else {
      std::cerr << "Unknown arg: " << a << "\n";
      usage(argv[0]);
      return 1;
    }
  }

  try {
    rcx::Layout layout = rcx::loadLayout(layout_path);
    rcx::ExtractionResult result = rcx::extractAll(std::move(layout));

    std::cout << rcx::reportExtraction(result) << "\n";

    if (!spef_path.empty()) {
      rcx::writeSpefFile(result.network, result.layout.name, spef_path);
      std::cout << "Wrote SPEF: " << spef_path << "\n";
    } else {
      std::cout << "----- SPEF -----\n" << result.spef;
    }

    if (do_elmore) {
      rcx::ElmoreResult er =
          rcx::elmoreDelay(result.network, elmore_net, elmore_drv);
      std::cout << "\n" << rcx::formatElmore(er);
    } else {
      // Auto-run Elmore for first output pin if possible
      for (const auto& pin : result.layout.pins) {
        if (pin.direction == "O") {
          try {
            auto er =
                rcx::elmoreDelay(result.network, pin.net, pin.name);
            std::cout << "\n(auto) ";
            std::cout << rcx::formatElmore(er);
          } catch (...) {
          }
          break;
        }
      }
    }
  } catch (const std::exception& ex) {
    std::cerr << "error: " << ex.what() << "\n";
    return 1;
  }
  return 0;
}
