#pragma once

#include <algorithm>
#include <cctype>
#include <cmath>
#include <stdexcept>
#include <string>
#include <utility>

namespace rcx {

struct Rect {
  double x0 = 0, y0 = 0, x1 = 0, y1 = 0;

  Rect() = default;
  Rect(double x0_, double y0_, double x1_, double y1_)
      : x0(x0_), y0(y0_), x1(x1_), y1(y1_) {
    if (x1 <= x0 || y1 <= y0)
      throw std::runtime_error("Invalid rectangle");
  }

  double width() const { return x1 - x0; }
  double height() const { return y1 - y0; }
  double area() const { return width() * height(); }
  double cx() const { return 0.5 * (x0 + x1); }
  double cy() const { return 0.5 * (y0 + y1); }

  bool isHorizontal() const { return width() >= height(); }

  // (length along run, width perpendicular) for Manhattan wires
  std::pair<double, double> lengthWidth() const {
    if (isHorizontal())
      return {width(), height()};
    return {height(), width()};
  }

  bool overlaps(const Rect& o, double tol = 1e-9) const {
    return !(x1 < o.x0 - tol || o.x1 < x0 - tol || y1 < o.y0 - tol ||
             o.y1 < y0 - tol);
  }

  Rect expanded(double d) const {
    return Rect(x0 - d, y0 - d, x1 + d, y1 + d);
  }

  bool contains(double x, double y, double tol = 1e-9) const {
    return x >= x0 - tol && x <= x1 + tol && y >= y0 - tol && y <= y1 + tol;
  }
};

struct Shape {
  std::string layer;
  Rect rect;
  std::string net;   // filled by connectivity / input
  std::string name;  // optional tag

  bool isVia() const {
    if (layer.size() < 3)
      return false;
    std::string up = layer;
    for (char& c : up)
      c = static_cast<char>(std::toupper(static_cast<unsigned char>(c)));
    return up.rfind("VIA", 0) == 0;
  }
};

struct Pin {
  std::string name;       // e.g. "U1:Z"
  std::string net;
  std::string layer;
  double x = 0, y = 0;
  std::string direction = "I";  // I / O / B
};

}  // namespace rcx
