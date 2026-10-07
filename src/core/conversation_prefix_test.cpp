#include "strata/core/conversation_prefix.hpp"
#include <cstdio>
using namespace strata::core;
static int failures = 0;
static void check(bool ok, const char* name) { if (!ok) { ++failures; std::fprintf(stderr, "%s\n", name); } }
int main() {
    SavedConversation donor;
    donor.live.ids = {1, 2, 3, 4};
    donor.checkpoints.resize(2);
    donor.checkpoints[0].ids = {1, 2}; donor.checkpoints[0].gdn = {11};
    donor.checkpoints[1].ids = {1, 2, 3};
    donor.stage_images.push_back(donor);
    donor.stage_images[0].checkpoints[0].gdn = {22};
    std::vector<ConversationCheckpoint> checks;
    std::string error;
    int validated = 0, writes = 0;
    auto valid = [&](size_t, const SavedConversation&) { ++validated; return true; };
    check(conversation_prefix_prepare(donor, 2, 1, valid, checks, error), "prepare split prefix");
    check(validated == 2 && checks.size() == 1 && checks[0].gdn[0] == 11 &&
          checks[0].stage_parts.size() == 1 && checks[0].stage_parts[0].gdn[0] == 22, "both checkpoint states copied");
    checks[0].stage_parts[0].gdn[0] = 33;
    check(donor.stage_images[0].checkpoints[0].gdn[0] == 22, "donor checkpoint remains independent");
    auto invalid_last = [&](size_t k, const SavedConversation&) { return k == 0; };
    if (conversation_prefix_prepare(donor, 2, 1, invalid_last, checks, error)) ++writes;
    check(writes == 0 && checks.empty(), "invalid last stage prevents every restore write");
    donor.stage_images[0].checkpoints[0].ids[0] = 9;
    check(!conversation_prefix_prepare(donor, 2, 1, valid, checks, error), "misaligned checkpoint rejected");
    donor.stage_images[0].checkpoints[0].ids[0] = 1;
    check(!conversation_prefix_prepare(donor, 1, 1, valid, checks, error), "missing checkpoint rejected");
    check(!conversation_prefix_prepare(donor, 5, 1, valid, checks, error), "prefix past image rejected");
    check(!conversation_prefix_prepare(donor, 2, 2, valid, checks, error), "missing stage rejected");
    donor.stage_images[0].live.ids[0] = 9;
    check(!conversation_prefix_prepare(donor, 2, 1, valid, checks, error), "foreign conversation stage rejected");
    return failures ? 1 : 0;
}
