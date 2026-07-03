#pragma once
#include <vector>
#include "metalfill/geometry.hpp"

namespace mf {

// One leaf of the recursive partitioning of the die.
//
//   core : the region this leaf is responsible for emitting fill in. Cores of
//          different leaves are disjoint and tile the die. Core edges are
//          aligned to the density-window / fill-pitch lattice.
//   halo : core expanded by a guard band. Geometry inside the halo is used as
//          read-only context so density and spacing are correct at the core
//          edge, but fill is only *emitted* inside the core.
struct PartitionRect {
    BBox core;
    BBox halo;
    int depth = 0;
};

struct PartitionConfig {
    dbu anchor_x = 0;   // lattice origin (die xmin)
    dbu anchor_y = 0;   // lattice origin (die ymin)
    dbu align_x = 1;    // atomic cut unit in x (== lcm(window, pitch_x))
    dbu align_y = 1;    // atomic cut unit in y (== lcm(window, pitch_y))
    dbu margin = 0;     // halo guard band (multiple of align)
    int max_leaf = 2;   // stop splitting when leaf <= max_leaf align-units per side
    int max_depth = 24; // hard recursion cap
    BBox clip;          // die bounds; cores are clamped to this for emission
};

// Recursively partitions `area` (the die bounds) into leaves via a quadtree.
// Splits happen only on the align lattice so windows and fill pitch stay
// coherent across boundaries.
std::vector<PartitionRect> partition_recursive(const BBox& area, const PartitionConfig& cfg);

// Integer gcd / lcm helpers on database units.
dbu gcd_dbu(dbu a, dbu b);
dbu lcm_dbu(dbu a, dbu b);

}  // namespace mf
