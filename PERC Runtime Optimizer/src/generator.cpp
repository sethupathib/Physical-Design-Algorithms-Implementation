#include "generator.hpp"

#include <algorithm>
#include <random>
#include <sstream>
#include <vector>

namespace perc {
namespace {

std::string net_name(int b, int d, char side) {
  std::ostringstream oss;
  oss << "N_" << b << '_' << d << '_' << side;
  return oss.str();
}

}  // namespace

Design generate_design(const GenConfig& cfg) {
  std::mt19937 rng(cfg.seed);
  std::uniform_real_distribution<double> uni(0.0, 1.0);

  Design design;
  {
    std::ostringstream oss;
    oss << "synth_p" << cfg.n_pads << "_b" << cfg.n_blocks << "_d" << cfg.devices_per_block;
    design.name = oss.str();
  }

  design.add_net(Net{"VDD", true, false, false, "core"});
  design.add_net(Net{"VSS", false, true, false, "core"});

  design.pad_nets.clear();
  design.pad_nets.reserve(cfg.n_pads);
  for (int i = 0; i < cfg.n_pads; ++i) {
    std::string pad = "PAD_" + std::to_string(i);
    design.pad_nets.push_back(pad);
    design.add_net(Net{pad, false, false, true, "io"});
    Device io;
    io.name = "IO_" + std::to_string(i);
    io.kind = DeviceKind::IoPad;
    io.terminals = {{"pad", pad}, {"vdd", "VDD"}, {"vss", "VSS"}};
    design.add_device(std::move(io));

    if (uni(rng) >= cfg.missing_clamp_rate) {
      Device clamp;
      clamp.name = "CLAMP_" + std::to_string(i);
      clamp.kind = DeviceKind::EsdClamp;
      clamp.terminals = {{"io", pad}, {"vdd", "VDD"}, {"vss", "VSS"}};
      clamp.ron = 0.3 + uni(rng) * 1.2;
      design.add_device(std::move(clamp));
    }
  }

  std::unordered_set<std::string> clamp_pads;
  for (const auto& kv : design.devices) {
    if (kv.second.kind == DeviceKind::EsdClamp) {
      auto it = kv.second.terminals.find("io");
      if (it != kv.second.terminals.end()) clamp_pads.insert(it->second);
    }
  }

  // Build pad→rail edges early (ESD-critical).
  for (const auto& pad : design.pad_nets) {
    if (clamp_pads.count(pad)) {
      design.rgraph.add_edge(pad, "VDD", 0.2 + uni(rng) * 0.6);
      design.rgraph.add_edge(pad, "VSS", 0.2 + uni(rng) * 0.6);
    } else {
      design.rgraph.add_edge(pad, "VDD", 8.0 + uni(rng) * 17.0);
      design.rgraph.add_edge(pad, "VSS", 8.0 + uni(rng) * 17.0);
    }
  }
  design.rgraph.add_edge("VDD", "VSS", 0.01 + uni(rng) * 0.04);

  const int iface_per = std::max(1, cfg.n_pads / std::max(cfg.n_blocks, 1));

  for (int b = 0; b < cfg.n_blocks; ++b) {
    Block block;
    block.name = "BLK_" + std::to_string(b);
    const std::string local_vdd = "VDD_BLK_" + std::to_string(b);
    const std::string local_vss = "VSS_BLK_" + std::to_string(b);
    design.add_net(Net{local_vdd, true, false, false, "blk" + std::to_string(b)});
    design.add_net(Net{local_vss, false, true, false, "blk" + std::to_string(b)});
    block.nets.insert(local_vdd);
    block.nets.insert(local_vss);
    block.interface_nets.insert(local_vdd);
    block.interface_nets.insert(local_vss);
    block.interface_nets.insert("VDD");
    block.interface_nets.insert("VSS");

    Device rtie_vdd;
    rtie_vdd.name = "RTIE_VDD_" + std::to_string(b);
    rtie_vdd.kind = DeviceKind::Resistor;
    rtie_vdd.terminals = {{"a", "VDD"}, {"b", local_vdd}};
    rtie_vdd.ron = 0.05 + uni(rng) * 0.15;
    design.add_device(std::move(rtie_vdd));

    Device rtie_vss;
    rtie_vss.name = "RTIE_VSS_" + std::to_string(b);
    rtie_vss.kind = DeviceKind::Resistor;
    rtie_vss.terminals = {{"a", "VSS"}, {"b", local_vss}};
    rtie_vss.ron = 0.05 + uni(rng) * 0.15;
    design.add_device(std::move(rtie_vss));

    design.rgraph.add_edge(local_vdd, "VDD", 0.05 + uni(rng) * 0.25);
    design.rgraph.add_edge(local_vss, "VSS", 0.05 + uni(rng) * 0.25);

    std::vector<std::string> block_net_list;
    block_net_list.push_back(local_vdd);
    block_net_list.push_back(local_vss);

    for (int d = 0; d < cfg.devices_per_block; ++d) {
      const std::string na = net_name(b, d, 'A');
      const std::string nb = net_name(b, d, 'B');
      design.add_net(Net{na, false, false, false, "blk" + std::to_string(b)});
      design.add_net(Net{nb, false, false, false, "blk" + std::to_string(b)});
      block.nets.insert(na);
      block.nets.insert(nb);
      block_net_list.push_back(na);
      block_net_list.push_back(nb);

      if (uni(rng) > 0.08) {
        Device m;
        m.name = "M_" + std::to_string(b) + "_" + std::to_string(d);
        m.kind = DeviceKind::Mosfet;
        std::string gate = nb;
        if (uni(rng) < 0.02) {
          gate = "FLOAT_" + std::to_string(b) + "_" + std::to_string(d);
          design.add_net(Net{gate, false, false, false, "blk" + std::to_string(b)});
          block.nets.insert(gate);
        }
        m.terminals = {
            {"d", na},
            {"g", gate},
            {"s", (uni(rng) > 0.5 ? local_vss : local_vdd)},
            {"b", local_vss},
        };
        block.devices.insert(m.name);
        design.add_device(std::move(m));
      } else {
        Device diode;
        diode.name = "D_" + std::to_string(b) + "_" + std::to_string(d);
        diode.kind = DeviceKind::Diode;
        diode.terminals = {{"a", na}, {"c", local_vss}};
        block.devices.insert(diode.name);
        design.add_device(std::move(diode));
      }
    }

    // Interface buffers toward pads.
    for (int k = 0; k < iface_per; ++k) {
      const int pad_idx = (b * iface_per + k) % cfg.n_pads;
      const std::string iface = "IF_" + std::to_string(b) + "_" + std::to_string(k);
      design.add_net(Net{iface, false, false, false, "blk" + std::to_string(b)});
      block.nets.insert(iface);
      block.interface_nets.insert(iface);
      block_net_list.push_back(iface);
      design.iface_to_pad[iface] = design.pad_nets[pad_idx];

      Device buf;
      buf.name = "BUF_" + std::to_string(b) + "_" + std::to_string(k);
      buf.kind = DeviceKind::Mosfet;
      buf.terminals = {
          {"d", iface},
          {"g", net_name(b, k % std::max(1, cfg.devices_per_block), 'A')},
          {"s", local_vss},
          {"b", local_vss},
      };
      block.devices.insert(buf.name);
      design.add_device(std::move(buf));
      design.rgraph.add_edge(iface, design.pad_nets[pad_idx], 0.3 + uni(rng) * 1.7);
    }

    // Sparse R-mesh inside the block (spanning path + extras).
    std::shuffle(block_net_list.begin(), block_net_list.end(), rng);
    for (std::size_t i = 1; i < block_net_list.size(); ++i) {
      design.rgraph.add_edge(block_net_list[i - 1], block_net_list[i], 0.5 + uni(rng) * 4.5);
    }
    const int extra = static_cast<int>(block_net_list.size() * cfg.r_mesh_density);
    for (int e = 0; e < extra && block_net_list.size() >= 2; ++e) {
      const int i = static_cast<int>(rng() % block_net_list.size());
      const int j = static_cast<int>(rng() % block_net_list.size());
      if (i == j) continue;
      design.rgraph.add_edge(block_net_list[i], block_net_list[j], 0.5 + uni(rng) * 7.5);
    }

    design.blocks.emplace(block.name, std::move(block));
  }

  design.p2p_limit_ohm = 2.0;
  return design;
}

Design mutate_eco(const Design& design, double touch_fraction, unsigned seed,
                  int max_blocks_to_touch) {
  std::mt19937 rng(seed);
  Design eco = design;
  eco.name = design.name + "_eco";
  eco.touched_blocks.clear();

  std::vector<std::string> block_names;
  for (const auto& kv : eco.blocks) block_names.push_back(kv.first);
  std::sort(block_names.begin(), block_names.end());
  std::shuffle(block_names.begin(), block_names.end(), rng);
  if (max_blocks_to_touch > 0 &&
      static_cast<int>(block_names.size()) > max_blocks_to_touch) {
    block_names.resize(max_blocks_to_touch);
  }
  std::unordered_set<std::string> allowed_blocks(block_names.begin(), block_names.end());

  std::vector<std::string> mosfets;
  for (const auto& kv : eco.devices) {
    if (kv.second.kind != DeviceKind::Mosfet) continue;
    bool in_allowed = allowed_blocks.empty();
    for (const auto& bname : allowed_blocks) {
      if (eco.blocks.at(bname).devices.count(kv.first)) {
        in_allowed = true;
        break;
      }
    }
    // Also allow devices not listed in block.devices (e.g. BUF_*) if their nets are in block
    if (!in_allowed) {
      for (const auto& bname : allowed_blocks) {
        for (const auto& t : kv.second.terminals) {
          if (eco.blocks.at(bname).nets.count(t.second)) {
            in_allowed = true;
            break;
          }
        }
        if (in_allowed) break;
      }
    }
    if (in_allowed) mosfets.push_back(kv.first);
  }
  if (mosfets.empty()) return eco;

  const int n_touch = std::max(1, static_cast<int>(mosfets.size() * touch_fraction));
  std::shuffle(mosfets.begin(), mosfets.end(), rng);
  mosfets.resize(std::min(n_touch, static_cast<int>(mosfets.size())));

  std::unordered_set<std::string> touched;
  for (const auto& dname : mosfets) {
    Device& d = eco.devices[dname];
    auto it = d.terminals.find("d");
    if (it == d.terminals.end()) continue;
    const std::string old = it->second;
    const std::string neu = old + "_ECO";
    it->second = neu;
    Net n;
    n.name = neu;
    auto old_it = eco.nets.find(old);
    if (old_it != eco.nets.end()) n.voltage_domain = old_it->second.voltage_domain;
    eco.add_net(std::move(n));

    if (eco.rgraph.has_node(old)) {
      const int oid = eco.rgraph.name_to_id[old];
      // Snapshot neighbors first — add_edge may reallocate adj / id_to_name.
      std::vector<std::pair<std::string, double>> nbrs;
      nbrs.reserve(eco.rgraph.adj[oid].size());
      for (const auto& [nbr, r] : eco.rgraph.adj[oid]) {
        nbrs.emplace_back(eco.rgraph.id_to_name[nbr], r);
      }
      std::uniform_real_distribution<double> jitter(0.9, 1.1);
      for (const auto& [nbr_name, r] : nbrs) {
        eco.rgraph.add_edge(neu, nbr_name, r * jitter(rng));
      }
    }

    for (auto& bkv : eco.blocks) {
      if (bkv.second.devices.count(dname) || bkv.second.nets.count(old)) {
        bkv.second.nets.insert(neu);
        touched.insert(bkv.first);
      }
    }
  }

  eco.touched_blocks.assign(touched.begin(), touched.end());
  std::sort(eco.touched_blocks.begin(), eco.touched_blocks.end());
  return eco;
}

}  // namespace perc
