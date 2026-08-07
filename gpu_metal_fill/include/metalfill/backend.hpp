#pragma once
#include <memory>
#include <string>
#include "metalfill/density.hpp"
#include "metalfill/fill.hpp"
#include "metalfill/raster.hpp"

namespace mf {

// The compute-heavy stages of metal fill are isolated behind this interface so
// they can be executed on the CPU (OpenMP) or offloaded to the GPU (CUDA).
//
// Every stage here is data-parallel and maps naturally onto the GPU:
//   * build_sat      -> parallel prefix sums
//   * compute_density-> box lookups over the SAT
//   * compute_keepout-> morphological dilation (box filter + threshold)
//   * place_fill     -> per-window independent stamping
class FillBackend {
public:
    virtual ~FillBackend() = default;
    virtual std::string name() const = 0;

    virtual SummedAreaTable build_sat(const Grid& grid) = 0;
    virtual DensityMap compute_density(const SummedAreaTable& sat, int win_cells,
                                       int step_cells) = 0;
    virtual Grid compute_keepout(const Grid& occ, int keepout_cells) = 0;
    virtual std::vector<FillShape> place_fill(const Grid& occ, const Grid& blocked,
                                              const FillParams& params,
                                              Grid& fill_occ) = 0;
};

// The default CPU backend (parallelized with OpenMP when available).
std::unique_ptr<FillBackend> make_cpu_backend();

// Returns a CUDA backend when the library is built with USE_CUDA and a device
// is present; otherwise returns nullptr.
std::unique_ptr<FillBackend> make_cuda_backend();

// Selects the CUDA backend if requested and available, else the CPU backend.
std::unique_ptr<FillBackend> make_backend(bool prefer_gpu);

}  // namespace mf
