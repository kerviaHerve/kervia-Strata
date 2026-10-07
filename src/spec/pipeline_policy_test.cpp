#include "strata/spec/pipeline_policy.hpp"
#include <cstdio>
#include <limits>
using strata::spec::PipelinePolicy;
static int failures = 0;
static void check(bool ok, const char* name) { if (!ok) { ++failures; std::fprintf(stderr, "%s\n", name); } }
int main() {
    PipelinePolicy p;
    check(p.launch(.25, 4, 4, .2), "cold gate retains fixed policy");
    check(!p.launch(.19, 4, 4, .2), "fixed probability floor");
    check(!p.launch(std::numeric_limits<double>::quiet_NaN(), 4, 4, .2), "reject NaN probability");
    for (int i = 0; i < 80; ++i) { p.stage(0, 4, 10); p.stage(1, 4, 12); p.outcome(.25, i % 10 == 0); }
    check(!p.launch(.25, 4, 4, .2), "measured misses reject expensive speculation");
    for (int i = 0; i < 160; ++i) p.outcome(.25, true);
    check(p.launch(.25, 4, 4, .2), "gated outcomes allow recovery without forced launches");
    check(p.launch(.8, 4, 4, .2), "unobserved probability bin keeps fallback");
    PipelinePolicy asymmetric;
    for (int i = 0; i < 80; ++i) {
        asymmetric.stage(0, 4, 1000); asymmetric.stage(1, 4, 1); asymmetric.outcome(.95, true);
    }
    check(!asymmetric.launch(.95, 4, 4, .2), "small overlap cannot pay for costly stage zero");
    asymmetric.stage(0, 4, std::numeric_limits<double>::infinity());
    check(!asymmetric.launch(.95, 4, 4, .2), "invalid timing cannot poison decision");
    return failures ? 1 : 0;
}
