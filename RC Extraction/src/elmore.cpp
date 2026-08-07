#include "elmore.hpp"

#include <functional>
#include <queue>
#include <sstream>
#include <stdexcept>
#include <unordered_map>
#include <unordered_set>
#include <vector>

namespace rcx {

ElmoreResult elmoreDelay(const RCNetwork& net, const std::string& net_name,
                         const std::string& driver_pin) {
  // Resolve driver node: match pin name or exact node name on this net
  std::string driver;
  for (const auto& kv : net.nodes) {
    const RCNode& n = kv.second;
    if (n.net != net_name)
      continue;
    if (n.is_pin && n.pin_name == driver_pin) {
      driver = n.name;
      break;
    }
    if (n.name == driver_pin) {
      driver = n.name;
      break;
    }
  }
  if (driver.empty())
    throw std::runtime_error("Driver not found on net " + net_name + ": " +
                             driver_pin);

  // Adjacency for this net's resistors
  struct Edge {
    std::string to;
    double r;
  };
  std::unordered_map<std::string, std::vector<Edge>> adj;
  std::unordered_set<std::string> nodes;
  for (const auto& r : net.resistors) {
    if (r.net != net_name)
      continue;
    adj[r.node_a].push_back({r.node_b, r.value_ohm});
    adj[r.node_b].push_back({r.node_a, r.value_ohm});
    nodes.insert(r.node_a);
    nodes.insert(r.node_b);
  }
  nodes.insert(driver);

  // Grounded capacitance per node (coupling treated as grounded for Elmore demo)
  std::unordered_map<std::string, double> c_node;
  for (const auto& c : net.capacitors) {
    if (c.kind == "coupling") {
      if (c.net_pos == net_name)
        c_node[c.node_pos] += c.value_ff;
      if (c.net_neg == net_name)
        c_node[c.node_neg] += c.value_ff;
    } else if (c.net_pos == net_name) {
      c_node[c.node_pos] += c.value_ff;
    }
  }

  // BFS parent tree from driver
  std::unordered_map<std::string, std::string> parent;
  std::unordered_map<std::string, double> parent_r;
  std::queue<std::string> q;
  std::unordered_set<std::string> vis;
  q.push(driver);
  vis.insert(driver);
  parent[driver] = "";
  parent_r[driver] = 0.0;

  while (!q.empty()) {
    std::string u = q.front();
    q.pop();
    for (const auto& e : adj[u]) {
      if (vis.count(e.to))
        continue;
      vis.insert(e.to);
      parent[e.to] = u;
      parent_r[e.to] = e.r;
      q.push(e.to);
    }
  }

  // Children lists
  std::unordered_map<std::string, std::vector<std::string>> children;
  for (const auto& kv : parent) {
    if (!kv.second.empty())
      children[kv.second].push_back(kv.first);
  }

  // Downstream capacitance via DFS post-order
  ElmoreResult result;
  result.driver_node = driver;
  std::function<double(const std::string&)> downC = [&](const std::string& u) {
    double c = c_node[u];
    for (const auto& v : children[u])
      c += downC(v);
    result.downstream_c_ff[u] = c;
    return c;
  };
  downC(driver);

  // Elmore: T(u) = T(parent) + R(parent→u) * C_down(u)
  // Units: R in Ohm, C in fF → τ = R*C = Ohm*fE-15 F = 1e-15 s = 0.001 ps
  // Actually: 1 Ohm * 1 fF = 1e-15 s = 0.001 ps
  // So delay_ps = R_ohm * C_ff * 0.001
  constexpr double OHM_FF_TO_PS = 0.001;

  std::function<void(const std::string&, double)> assign =
      [&](const std::string& u, double t_ps) {
        result.delay_ps[u] = t_ps;
        for (const auto& v : children[u]) {
          double edge_r = parent_r[v];
          double add = edge_r * result.downstream_c_ff[v] * OHM_FF_TO_PS;
          assign(v, t_ps + add);
        }
      };
  assign(driver, 0.0);

  return result;
}

std::string formatElmore(const ElmoreResult& r) {
  std::ostringstream oss;
  oss << std::fixed;
  oss.precision(4);
  oss << "Elmore delay (driver=" << r.driver_node << ")\n";
  oss << "  node                          delay_ps    C_down_fF\n";
  for (const auto& kv : r.delay_ps) {
    double cd = 0.0;
    auto it = r.downstream_c_ff.find(kv.first);
    if (it != r.downstream_c_ff.end())
      cd = it->second;
    oss << "  " << kv.first;
    if (kv.first.size() < 28)
      oss << std::string(28 - kv.first.size(), ' ');
    oss << "  " << kv.second << "      " << cd << "\n";
  }
  return oss.str();
}

}  // namespace rcx
