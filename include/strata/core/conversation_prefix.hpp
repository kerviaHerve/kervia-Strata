#pragma once
#include "strata/core/conversation_cache.hpp"
#include <string>

namespace strata::core {
// Validate every stage and checkpoint before the caller parks or writes any live
// state. Copy only checkpoints on the borrowed path, never the donor's KV arrays.
// validate(stage, image) must be read-only; stage 0 is the outer image.
template<class Validate>
bool conversation_prefix_prepare(const SavedConversation& image, int64_t upto, size_t later_stages,
                                 Validate validate, std::vector<ConversationCheckpoint>& checks,
                                 std::string& error) {
    checks.clear();
    auto fail = [&](const char* reason) { error = reason; return false; };
    if (image.stage_images.size() != later_stages || upto < 1 || upto > int64_t(image.live.ids.size()))
        return fail("invalid borrowed prefix extent or stage count");
    if (!validate(0, image)) return false;
    for (size_t k = 0; k < later_stages; ++k) {
        const auto& part = image.stage_images[k];
        if (!part.stage_images.empty() || part.live.ids != image.live.ids || part.live.imgs != image.live.imgs ||
            part.cvec != image.cvec || part.checkpoints.size() != image.checkpoints.size())
            return fail("borrowed stages have different conversation identities");
        if (!validate(k + 1, part)) return false;
        for (size_t j = 0; j < image.checkpoints.size(); ++j)
            if (part.checkpoints[j].ids != image.checkpoints[j].ids ||
                part.checkpoints[j].imgs != image.checkpoints[j].imgs)
                return fail("borrowed stage checkpoints do not line up");
    }
    bool found = false;
    for (size_t j = 0; j < image.checkpoints.size(); ++j) {
        const auto& c = image.checkpoints[j];
        if (int64_t(c.ids.size()) > upto) continue;
        if (!c.stage_parts.empty() || !std::equal(c.ids.begin(), c.ids.end(), image.live.ids.begin()))
            return fail("borrowed checkpoint is not on the donor path");
        found |= int64_t(c.ids.size()) == upto;
    }
    if (!found) return fail("borrowed prefix has no matching checkpoint");
    for (size_t j = 0; j < image.checkpoints.size(); ++j) {
        const auto& c = image.checkpoints[j];
        if (int64_t(c.ids.size()) > upto) continue;
        checks.push_back(c);
        for (const auto& part : image.stage_images) checks.back().stage_parts.push_back(part.checkpoints[j]);
    }
    return true;
}
} // namespace strata::core
