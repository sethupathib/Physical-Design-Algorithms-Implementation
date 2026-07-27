#include "design.hpp"

#include <algorithm>
#include <cmath>
#include <functional>
#include <limits>
#include <queue>
#include <sstream>

namespace perc {

int RGraph::get_or_add(const std::string& name) {
  auto it = name_to_id.find(name);
  if (it != name_to_id.end()) return it->second;
  int id = static_cast<int>(id_to_name.size());
  name_to_id.emplace(name, id);
  id_to_name.push_back(name);
  adj.emplace_back();
  return id;
}

void RGraph::add_edge(const std::string& a, const std::string& b, double r) {
  if (a == b) return;
  int u = get_or_add(a);
  int v = get_or_add(b);
  adj[u].push_back({v, r});
  adj[v].push_back({u, r});
}

bool RGraph::has_node(const std::string& name) const {
  return name_to_id.find(name) != name_to_id.end();
}

int RGraph::edge_count() const {
  int e = 0;
  for (const auto& row : adj) e += static_cast<int>(row.size());
  return e / 2;
}

bool RGraph::path_resistance(int src, int sink, double& out_r) const {
  const int n = node_count();
  if (src < 0 || sink < 0 || src >= n || sink >= n) return false;
  std::vector<double> dist(n, std::numeric_limits<double>::infinity());
  using Node = std::pair<double, int>;
  std::priority_queue<Node, std::vector<Node>, std::greater<Node>> pq;
  dist[src] = 0.0;
  pq.push({0.0, src});
  while (!pq.empty()) {
    auto [d, u] = pq.top();
    pq.pop();
    if (d > dist[u]) continue;
    if (u == sink) {
      out_r = d;
      return true;
    }
    for (const auto& [v, w] : adj[u]) {
      double nd = d + w;
      if (nd < dist[v]) {
        dist[v] = nd;
        pq.push({nd, v});
      }
    }
  }
  return false;
}

bool RGraph::shortest_path(int src, int sink, std::vector<int>& out_nodes) const {
  const int n = node_count();
  if (src < 0 || sink < 0 || src >= n || sink >= n) return false;
  std::vector<double> dist(n, std::numeric_limits<double>::infinity());
  std::vector<int> prev(n, -1);
  using Node = std::pair<double, int>;
  std::priority_queue<Node, std::vector<Node>, std::greater<Node>> pq;
  dist[src] = 0.0;
  pq.push({0.0, src});
  while (!pq.empty()) {
    auto [d, u] = pq.top();
    pq.pop();
    if (d > dist[u]) continue;
    if (u == sink) break;
    for (const auto& [v, w] : adj[u]) {
      double nd = d + w;
      if (nd < dist[v]) {
        dist[v] = nd;
        prev[v] = u;
        pq.push({nd, v});
      }
    }
  }
  if (!std::isfinite(dist[sink])) return false;
  out_nodes.clear();
  for (int cur = sink; cur != -1; cur = prev[cur]) out_nodes.push_back(cur);
  std::reverse(out_nodes.begin(), out_nodes.end());
  return true;
}

void Design::add_device(Device d) {
  for (const auto& kv : d.terminals) {
    if (!nets.count(kv.second)) {
      Net n;
      n.name = kv.second;
      nets.emplace(n.name, n);
    }
  }
  devices[d.name] = std::move(d);
}

void Design::add_net(Net n) {
  nets[n.name] = std::move(n);
}

std::string Design::fingerprint(const std::unordered_set<std::string>* scope_nets) const {
  std::ostringstream oss;
  std::vector<std::string> net_names;
  if (scope_nets) {
    net_names.assign(scope_nets->begin(), scope_nets->end());
  } else {
    net_names.reserve(nets.size());
    for (const auto& kv : nets) net_names.push_back(kv.first);
  }
  std::sort(net_names.begin(), net_names.end());
  for (const auto& name : net_names) {
    auto it = nets.find(name);
    if (it == nets.end()) continue;
    const Net& n = it->second;
    oss << "N|" << name << '|' << n.is_power << n.is_ground << n.is_pad << '|'
        << n.voltage_domain << '\n';
  }

  std::vector<std::string> dev_names;
  for (const auto& kv : devices) {
    if (scope_nets) {
      bool hit = false;
      for (const auto& t : kv.second.terminals) {
        if (scope_nets->count(t.second)) {
          hit = true;
          break;
        }
      }
      if (!hit) continue;
    }
    dev_names.push_back(kv.first);
  }
  std::sort(dev_names.begin(), dev_names.end());
  for (const auto& name : dev_names) {
    const Device& d = devices.at(name);
    oss << "D|" << name << '|' << to_string(d.kind) << '|';
    std::vector<std::pair<std::string, std::string>> terms(d.terminals.begin(), d.terminals.end());
    std::sort(terms.begin(), terms.end());
    for (const auto& t : terms) oss << t.first << ':' << t.second << ',';
    oss << '\n';
  }

  // Stable hash via FNV-1a over the structural string.
  const std::string s = oss.str();
  std::uint64_t h = 1469598103934665603ULL;
  for (unsigned char c : s) {
    h ^= c;
    h *= 1099511628211ULL;
  }
  std::ostringstream hex;
  hex << std::hex << h;
  return hex.str();
}

std::string Design::esd_fingerprint() const {
  std::unordered_set<std::string> scope;
  scope.insert("VDD");
  scope.insert("VSS");
  for (const auto& p : pad_nets) scope.insert(p);
  for (const auto& kv : devices) {
    if (kv.second.kind == DeviceKind::EsdClamp || kv.second.kind == DeviceKind::IoPad) {
      for (const auto& t : kv.second.terminals) scope.insert(t.second);
    }
  }
  // Hash only ESD/IO devices + scoped nets (ignore core MOSFET churn).
  std::ostringstream oss;
  std::vector<std::string> net_names(scope.begin(), scope.end());
  std::sort(net_names.begin(), net_names.end());
  for (const auto& name : net_names) {
    auto it = nets.find(name);
    if (it == nets.end()) continue;
    const Net& n = it->second;
    oss << "N|" << name << '|' << n.is_power << n.is_ground << n.is_pad << '|'
        << n.voltage_domain << '\n';
  }
  std::vector<std::string> dev_names;
  for (const auto& kv : devices) {
    if (kv.second.kind == DeviceKind::EsdClamp || kv.second.kind == DeviceKind::IoPad) {
      dev_names.push_back(kv.first);
    }
  }
  std::sort(dev_names.begin(), dev_names.end());
  for (const auto& name : dev_names) {
    const Device& d = devices.at(name);
    oss << "D|" << name << '|' << to_string(d.kind) << '|';
    std::vector<std::pair<std::string, std::string>> terms(d.terminals.begin(), d.terminals.end());
    std::sort(terms.begin(), terms.end());
    for (const auto& t : terms) oss << t.first << ':' << t.second << ',';
    oss << '\n';
  }
  // Include pad→rail R edges only.
  for (const auto& pad : pad_nets) {
    if (!rgraph.has_node(pad)) continue;
    const int id = rgraph.name_to_id.at(pad);
    std::vector<std::pair<std::string, double>> nbrs;
    for (const auto& e : rgraph.adj[id]) {
      const std::string& nn = rgraph.id_to_name[e.first];
      if (nn == "VDD" || nn == "VSS") nbrs.emplace_back(nn, e.second);
    }
    std::sort(nbrs.begin(), nbrs.end());
    for (const auto& n : nbrs) oss << "R|" << pad << '|' << n.first << '|' << n.second << '\n';
  }
  const std::string s = oss.str();
  std::uint64_t h = 1469598103934665603ULL;
  for (unsigned char c : s) {
    h ^= c;
    h *= 1099511628211ULL;
  }
  std::ostringstream hex;
  hex << std::hex << h;
  return hex.str();
}

std::unordered_map<std::string, int> summarize(const std::vector<Violation>& v) {
  std::unordered_map<std::string, int> counts;
  for (const auto& x : v) counts[x.rule]++;
  return counts;
}

}  // namespace perc
