#include "metalfill/backend.hpp"

#ifdef _OPENMP
#include <omp.h>
#include <string>
#endif

namespace mf {

namespace {

// CPU implementation of the fill backend. The heavy stages delegate to the
// reference kernels in density.cpp / fill.cpp, which are OpenMP-parallel where
// the work is independent (keep-out dilation and per-tile fill placement).
class CpuBackend : public FillBackend {
public:
    std::string name() const override {
#ifdef _OPENMP
        return "cpu-openmp(" + std::to_string(omp_get_max_threads()) + " threads)";
#else
        return "cpu-serial";
#endif
    }

    SummedAreaTable build_sat(const Grid& grid) override { return mf::build_sat(grid); }

    DensityMap compute_density(const SummedAreaTable& sat, int win_cells,
                               int step_cells) override {
        return mf::compute_density(sat, win_cells, step_cells);
    }

    Grid compute_keepout(const Grid& occ, int keepout_cells) override {
        return mf::compute_keepout(occ, keepout_cells);
    }

    std::vector<FillShape> place_fill(const Grid& occ, const Grid& blocked,
                                      const FillParams& params, Grid& fill_occ) override {
        return mf::place_fill(occ, blocked, params, fill_occ);
    }
};

}  // namespace

std::unique_ptr<FillBackend> make_cpu_backend() { return std::make_unique<CpuBackend>(); }

std::unique_ptr<FillBackend> make_backend(bool prefer_gpu) {
    if (prefer_gpu) {
        if (auto gpu = make_cuda_backend()) return gpu;
    }
    return make_cpu_backend();
}

#ifndef USE_CUDA
// When built without CUDA support the GPU backend is simply unavailable.
std::unique_ptr<FillBackend> make_cuda_backend() { return nullptr; }
#endif

}  // namespace mf
