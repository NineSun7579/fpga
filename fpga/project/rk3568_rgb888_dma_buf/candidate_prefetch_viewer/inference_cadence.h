#pragma once
#include <algorithm>
#include <cstdint>

namespace tdm {
// Prefetch changes only input preparation. Submission still uses the original
// timestamp of the last emitted request, including urgent and bypass policies.
struct InferenceCadence {
    static constexpr int64_t PrefetchLeadMs = 120;
    static bool due(int64_t now, int64_t lastRequest, int64_t interval, bool bypass) {
        return bypass || lastRequest < 0 || now - lastRequest >= interval;
    }
    static bool mayArm(int64_t now, int64_t lastRequest, int64_t interval, bool bypass) {
        return bypass || lastRequest < 0 ||
            now - lastRequest >= interval - std::min(interval, PrefetchLeadMs);
    }
};
}
