#pragma once

#include <cstdint>
#include <string>
#include <unordered_map>
#include <unordered_set>
#include <utility>
#include <vector>

namespace perc {

enum class DeviceKind {
  Mosfet,
  Diode,
  EsdClamp,
  Resistor,
  Capacitor,
  IoPad,
  Other
};

inline const char* to_string(DeviceKind k) {
  switch (k) {
    case DeviceKind::Mosfet: return "mosfet";
    case DeviceKind::Diode: return "diode";
    case DeviceKind::EsdClamp: return "esd_clamp";
    case DeviceKind::Resistor: return "resistor";
    case DeviceKind::Capacitor: return "capacitor";
    case DeviceKind::IoPad: return "io_pad";
    default: return "other";
  }
}

struct Device {
  std::string name;
  DeviceKind kind = DeviceKind::Other;
  // terminal -> net name
  std::unordered_map<std::string, std::string> terminals;
  double ron = 0.0;
};

struct Net {
  std::string name;
  bool is_power = false;
  bool is_ground = false;
  bool is_pad = false;
  std::string voltage_domain;
};

struct Block {
  std::string name;
  std::unordered_set<std::string> devices;
  std::unordered_set<std::string> nets;
  std::unordered_set<std::string> interface_nets;
};

struct REdge {
  int u = -1;
  int v = -1;
  double r = 0.0;
};

struct Violation {
  std::string rule;
  std::string message;
  std::string context;  // compact key=value;key=value
};

// Weighted undirected resistor graph keyed by integer node ids.
struct RGraph {
  std::vector<std::string> id_to_name;
  std::unordered_map<std::string, int> name_to_id;
  std::vector<std::vector<std::pair<int, double>>> adj;  // (neighbor, r)

  int get_or_add(const std::string& name);
  void add_edge(const std::string& a, const std::string& b, double r);
  bool has_node(const std::string& name) const;
  // Dijkstra shortest-path resistance. Returns false if unreachable.
  bool path_resistance(int src, int sink, double& out_r) const;
  bool shortest_path(int src, int sink, std::vector<int>& out_nodes) const;
  int node_count() const { return static_cast<int>(adj.size()); }
  int edge_count() const;
};

struct Design {
  std::string name;
  std::unordered_map<std::string, Device> devices;
  std::unordered_map<std::string, Net> nets;
  std::unordered_map<std::string, Block> blocks;
  RGraph rgraph;
  std::vector<std::string> pad_nets;
  double p2p_limit_ohm = 2.0;
  std::vector<std::string> touched_blocks;  // set by ECO mutation
  std::unordered_map<std::string, std::string> iface_to_pad;

  void add_device(Device d);
  void add_net(Net n);
  std::string fingerprint(const std::unordered_set<std::string>* scope_nets = nullptr) const;
  // Fingerprint limited to pads, global rails, and ESD/IO devices (stable across core ECOs).
  std::string esd_fingerprint() const;
};

std::unordered_map<std::string, int> summarize(const std::vector<Violation>& v);

}  // namespace perc
