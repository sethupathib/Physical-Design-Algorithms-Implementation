#include "layout.hpp"

#include <cctype>
#include <fstream>
#include <sstream>
#include <stdexcept>

namespace rcx {
namespace {

std::string trim(const std::string& s) {
  std::size_t b = 0;
  while (b < s.size() && std::isspace(static_cast<unsigned char>(s[b])))
    ++b;
  std::size_t e = s.size();
  while (e > b && std::isspace(static_cast<unsigned char>(s[e - 1])))
    --e;
  return s.substr(b, e - b);
}

}  // namespace

Layout loadLayout(const std::string& path) {
  std::ifstream in(path);
  if (!in)
    throw std::runtime_error("Cannot open layout: " + path);

  Layout layout;
  layout.name = "unnamed";
  std::string line;
  int lineno = 0;
  while (std::getline(in, line)) {
    ++lineno;
    line = trim(line);
    if (line.empty() || line[0] == '#')
      continue;

    std::istringstream ss(line);
    std::string kw;
    ss >> kw;

    if (kw == "NAME") {
      ss >> layout.name;
    } else if (kw == "METAL" || kw == "VIA") {
      Shape s;
      ss >> s.layer >> s.net >> s.name;
      double x0, y0, x1, y1;
      if (!(ss >> x0 >> y0 >> x1 >> y1))
        throw std::runtime_error("Bad " + kw + " at line " +
                                 std::to_string(lineno));
      s.rect = Rect(x0, y0, x1, y1);
      layout.shapes.push_back(s);
    } else if (kw == "PIN") {
      Pin p;
      ss >> p.name >> p.net >> p.layer >> p.direction >> p.x >> p.y;
      if (!ss)
        throw std::runtime_error("Bad PIN at line " + std::to_string(lineno));
      layout.pins.push_back(p);
    } else {
      throw std::runtime_error("Unknown keyword '" + kw + "' at line " +
                               std::to_string(lineno));
    }
  }
  return layout;
}

void saveLayout(const Layout& layout, const std::string& path) {
  std::ofstream out(path);
  if (!out)
    throw std::runtime_error("Cannot write layout: " + path);
  out << "NAME " << layout.name << "\n";
  for (const auto& s : layout.shapes) {
    out << (s.isVia() ? "VIA" : "METAL") << " " << s.layer << " "
        << (s.net.empty() ? "-" : s.net) << " "
        << (s.name.empty() ? "-" : s.name) << " " << s.rect.x0 << " "
        << s.rect.y0 << " " << s.rect.x1 << " " << s.rect.y1 << "\n";
  }
  for (const auto& p : layout.pins) {
    out << "PIN " << p.name << " " << p.net << " " << p.layer << " "
        << p.direction << " " << p.x << " " << p.y << "\n";
  }
}

}  // namespace rcx
