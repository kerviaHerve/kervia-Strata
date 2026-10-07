// Synthetic input costs test policy recovery; no GPU or performance claim.
#include "strata/spec/draft_policy.hpp"
#include <cstdio>

void probe(int cap, int mtp) {
    strata::spec::DraftPolicy p(cap);
    for (int t=2; t<=cap; ++t) {
        if (t==mtp || t==cap) continue;
        for (int i=0; i<3; ++i) p.observe(false,t,t-1,0,1000.0);
    }
    for (int i=0; i<3; ++i) p.observe(false,mtp,mtp-1,0,40.0);
    for (int i=0; i<3; ++i) p.observe(true,cap,cap-1,40,1000.0);
    int large=0, first=-1;
    for (int i=0; i<256; ++i) {
        auto pick=p.choose(mtp,cap-1,40);
        if (pick.t==cap) { ++large; if(first<0)first=i; }
        // After the initial expensive samples, the full window costs only 44 ms.
        // This is a supplied test condition, not a measured GPU duration.
        p.observe(pick.lookup,pick.t,pick.t-1,40,pick.t==cap ? 44.0 : 40.0);
    }
    std::printf("cap=%d mtp=%d full_selected=%d/256 first_round=%d retained_full_cost_ms=%.3f\n",
                cap,mtp,large,first,p.cost_ms(cap));
}
int main() { probe(4,2); probe(6,4); }
