#pragma once

#include <algorithm>
#include <array>
#include <cmath>

namespace strata::spec {
// Experimental launch gate. Timings are host-observed stage completion intervals,
// not isolated CUDA kernel times. The cost model deliberately charges a miss for
// a whole stage-0 window; actual overlap and contention are judged by A/B runs.
class PipelinePolicy {
public:
    void stage(int stage, int tokens, double ms) {
        if (stage < 0 || stage > 1 || tokens < 1 || tokens > 8 || !std::isfinite(ms) || ms <= 0) return;
        auto& c = costs_[stage][tokens];
        c.ms = c.n++ ? 0.9 * c.ms + 0.1 * ms : ms;
    }
    void outcome(double raw, bool on) {
        if (!std::isfinite(raw) || raw < 0 || raw > 1) return;
        auto& b = bins_[bin(raw)];
        b.on = 0.98 * b.on + (on ? 1 : 0);
        b.n = 0.98 * b.n + 1;
        ++observations_;
    }
    bool launch(double raw, int parent_tokens, int next_tokens, double fallback) const {
        if (!std::isfinite(raw) || raw < fallback || raw > 1) return false;
        if (parent_tokens < 1 || parent_tokens > 8 || next_tokens < 1 || next_tokens > 8) return false;
        const auto& a = costs_[1][parent_tokens];
        const auto& b = costs_[0][next_tokens];
        const auto& p = bins_[bin(raw)];
        if (observations_ < 32 || p.n < 8 || a.n < 3 || b.n < 3) return true;
        const double calibrated = (p.on + 4 * raw) / (p.n + 4);
        return calibrated * std::min(a.ms, b.ms) > (1 - calibrated) * b.ms;
    }
    int observations() const { return observations_; }
private:
    struct Cost { double ms = 0; int n = 0; };
    struct Bin { double n = 0, on = 0; };
    static int bin(double p) { return std::clamp(int(p * 10), 0, 9); }
    std::array<std::array<Cost, 9>, 2> costs_{};
    std::array<Bin, 10> bins_{};
    int observations_ = 0;
};
} // namespace strata::spec
