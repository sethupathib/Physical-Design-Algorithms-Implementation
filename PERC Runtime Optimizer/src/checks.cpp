#include "checks.hpp"

#include <sstream>

namespace perc {
namespace {

std::string ctx(const std::vector<std::pair<std::string, std::string>>& kvs) {
  std::ostringstream oss;
  for (std::size_t i = 0; i < kvs.size(); ++i) {
    if (i) oss << ';';
    oss << kvs[i].first << '=' << kvs[i].second;
  }
  return oss.str();
}

}  // namespace

std::vector<Violation> check_esd_clamps(
    const Design& design,
    const std::vector<std::string>* pads) {
  std::vector<std::string> pad_list;
  if (pads) {
    pad_list = *pads;
  } else if (!design.pad_nets.empty()) {
    pad_list = design.pad_nets;
  } else {
    for (const auto& kv : design.nets) {
      if (kv.second.is_pad) pad_list.push_back(kv.first);
    }
  }

  std::unordered_set<std::string> clamped;
  for (const auto& kv : design.devices) {
    if (kv.second.kind != DeviceKind::EsdClamp) continue;
    auto it = kv.second.terminals.find("io");
    if (it == kv.second.terminals.end()) it = kv.second.terminals.find("pad");
    if (it != kv.second.terminals.end()) clamped.insert(it->second);
  }

  std::vector<Violation> out;
  for (const auto& pad : pad_list) {
    if (!clamped.count(pad)) {
      out.push_back({"ESD_CLAMP_MISSING", "Pad " + pad + " has no ESD clamp",
                     ctx({{"pad", pad}})});
    }
  }
  return out;
}

FloatingGateIndex build_floating_gate_index(const Design& design) {
  FloatingGateIndex idx;
  idx.writers.reserve(design.nets.size());
  for (const auto& kv : design.devices) {
    for (const auto& t : kv.second.terminals) {
      if (t.first == "d" || t.first == "s" || t.first == "a" || t.first == "c" ||
          t.first == "io" || t.first == "pad") {
        idx.writers[t.second]++;
      }
    }
  }
  for (const auto& kv : design.nets) {
    if (kv.second.is_power || kv.second.is_ground || kv.second.is_pad) {
      idx.writers[kv.first] += 1;
    }
  }
  return idx;
}

std::vector<Violation> check_floating_gates_indexed(
    const Design& design,
    const FloatingGateIndex& index,
    const std::unordered_set<std::string>* device_scope) {
  std::vector<Violation> out;
  auto check_one = [&](const std::string& name, const Device& d) {
    if (d.kind != DeviceKind::Mosfet) return;
    auto git = d.terminals.find("g");
    if (git == d.terminals.end()) return;
    const std::string& gnet = git->second;
    const int w = index.writers.count(gnet) ? index.writers.at(gnet) : 0;
    if (w == 0) {
      out.push_back({"FLOATING_GATE",
                     "Device " + name + " gate net " + gnet + " appears floating",
                     ctx({{"device", name}, {"net", gnet}})});
    }
  };

  if (device_scope) {
    for (const auto& name : *device_scope) {
      auto it = design.devices.find(name);
      if (it != design.devices.end()) check_one(name, it->second);
    }
  } else {
    for (const auto& kv : design.devices) check_one(kv.first, kv.second);
  }
  return out;
}

std::vector<Violation> check_floating_gates(
    const Design& design,
    const std::unordered_set<std::string>* device_scope) {
  const FloatingGateIndex idx = build_floating_gate_index(design);
  return check_floating_gates_indexed(design, idx, device_scope);
}

std::vector<Violation> check_p2p_resistance(
    const Design& design,
    const std::vector<std::pair<std::string, std::string>>* pairs,
    double limit_ohm) {
  const double limit = (limit_ohm > 0.0) ? limit_ohm : design.p2p_limit_ohm;
  std::vector<std::pair<std::string, std::string>> local;
  if (!pairs) {
    local.reserve(design.pad_nets.size() * 2);
    for (const auto& p : design.pad_nets) {
      local.emplace_back(p, "VSS");
      local.emplace_back(p, "VDD");
    }
    pairs = &local;
  }

  std::vector<Violation> out;
  for (const auto& pr : *pairs) {
    if (!design.rgraph.has_node(pr.first) || !design.rgraph.has_node(pr.second)) {
      out.push_back({"P2P_PATH_MISSING",
                     "No R-graph path endpoints for " + pr.first + " -> " + pr.second,
                     ctx({{"src", pr.first}, {"sink", pr.second}})});
      continue;
    }
    const int s = design.rgraph.name_to_id.at(pr.first);
    const int t = design.rgraph.name_to_id.at(pr.second);
    double r = 0.0;
    if (!design.rgraph.path_resistance(s, t, r)) {
      out.push_back({"P2P_PATH_MISSING",
                     "No resistive path " + pr.first + " -> " + pr.second,
                     ctx({{"src", pr.first}, {"sink", pr.second}})});
      continue;
    }
    if (r > limit) {
      std::ostringstream msg;
      msg << "R(" << pr.first << "," << pr.second << ")=" << r << "ohm exceeds " << limit << "ohm";
      out.push_back({"P2P_RESISTANCE_HIGH", msg.str(),
                     ctx({{"src", pr.first},
                          {"sink", pr.second},
                          {"r_ohm", std::to_string(r)},
                          {"limit", std::to_string(limit)}})});
    }
  }
  return out;
}

std::vector<Violation> check_current_density_paths(
    const Design& design,
    const std::vector<std::string>* pads,
    double i_peak_a,
    double jmax_proxy) {
  std::vector<std::string> pad_list = pads ? *pads : design.pad_nets;
  std::vector<Violation> out;
  if (!design.rgraph.has_node("VSS")) return out;
  const int sink = design.rgraph.name_to_id.at("VSS");

  for (const auto& pad : pad_list) {
    if (!design.rgraph.has_node(pad)) continue;
    const int src = design.rgraph.name_to_id.at(pad);
    std::vector<int> path;
    if (!design.rgraph.shortest_path(src, sink, path) || path.size() < 2) continue;
    for (std::size_t i = 1; i < path.size(); ++i) {
      const int a = path[i - 1];
      const int b = path[i];
      double r = 0.0;
      for (const auto& e : design.rgraph.adj[a]) {
        if (e.first == b) {
          r = e.second;
          break;
        }
      }
      const double stress = i_peak_a * r;
      if (stress > jmax_proxy) {
        std::ostringstream msg;
        msg << "Path " << pad << "->VSS edge " << design.rgraph.id_to_name[a] << "-"
            << design.rgraph.id_to_name[b] << " stress " << stress << " > " << jmax_proxy;
        out.push_back({"CURRENT_DENSITY", msg.str(),
                       ctx({{"pad", pad},
                            {"a", design.rgraph.id_to_name[a]},
                            {"b", design.rgraph.id_to_name[b]},
                            {"r", std::to_string(r)}})});
      }
    }
  }
  return out;
}

std::unordered_set<std::string> esd_roi_nets(const Design& design) {
  std::unordered_set<std::string> roi;
  for (const auto& kv : design.nets) {
    if (kv.second.is_pad || kv.second.is_power || kv.second.is_ground) roi.insert(kv.first);
  }
  for (const auto& kv : design.devices) {
    if (kv.second.kind == DeviceKind::EsdClamp || kv.second.kind == DeviceKind::IoPad ||
        kv.second.kind == DeviceKind::Diode) {
      for (const auto& t : kv.second.terminals) roi.insert(t.second);
    }
  }
  return roi;
}

}  // namespace perc
