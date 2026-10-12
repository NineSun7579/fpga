#pragma once

#include <QImage>
#include <QList>
#include <QRegion>
#include <algorithm>
#include <cstring>
#include <queue>
#include <set>
#include <tuple>
#include <vector>

namespace hudupload {
int runSelfTest();
inline qint64 area(const QRect& r) { return qint64(r.width()) * r.height(); }

// Cost model: one saved GL call may spend at most callPixels additional RGBA
// pixels. This is a configurable hypothesis, not a measured Mali call cost.
// Total transferred area (including repeated overlapping uploads) is bounded.
inline QList<QRect> coalesce(const QRegion& dirty, const QRect& bounds,
                            qint64 callPixels = 512) {
    struct Node { QRect rect; bool active = true; };
    struct Pair {
        qint64 cost; size_t a, b;
        bool operator<(const Pair& o) const {
            if (cost != o.cost) return cost > o.cost;
            if (a != o.a) return a > o.a;
            return b > o.b;
        }
    };
    std::vector<Node> nodes;
    qint64 base = 0;
    for (const QRect& r : dirty & bounds) { nodes.push_back({r}); base += area(r); }
    const qint64 limit = base + base / 4;
    qint64 transferred = base;
    std::priority_queue<Pair> pairs;
    auto offer = [&](size_t a, size_t b) {
        const qint64 cost = area(nodes[a].rect.united(nodes[b].rect)) -
                            area(nodes[a].rect) - area(nodes[b].rect);
        if (cost <= std::max(qint64(0), callPixels)) pairs.push({cost, a, b});
    };
    // Search a bounded spatial neighborhood rather than every pair: Qt can
    // produce thousands of strips. Two axis orderings find nearby horizontal
    // and vertical candidates without quadratic planning on the GUI thread.
    using Key = std::tuple<int, int, size_t>;
    std::set<Key> byX, byY;
    auto xKey = [&](size_t i) { return Key(nodes[i].rect.x(), nodes[i].rect.y(), i); };
    auto yKey = [&](size_t i) { return Key(nodes[i].rect.y(), nodes[i].rect.x(), i); };
    auto neighbors = [&](const std::set<Key>& index, const Key& key, size_t i) {
        auto at = index.find(key), before = at, after = at;
        for (int n = 0; n < 8; ++n) {
            if (before != index.begin()) { --before; offer(std::get<2>(*before), i); }
            if (after != index.end()) {
                ++after;
                if (after != index.end()) offer(std::get<2>(*after), i);
            }
        }
    };
    auto insert = [&](size_t i) {
        byX.insert(xKey(i)); byY.insert(yKey(i));
        neighbors(byX, xKey(i), i); neighbors(byY, yKey(i), i);
    };
    for (size_t i = 0; i < nodes.size(); ++i) insert(i);
    while (!pairs.empty()) {
        const Pair p = pairs.top(); pairs.pop();
        if (!nodes[p.a].active || !nodes[p.b].active) continue;
        // The heap is ordered by incremental transfer cost. If the cheapest
        // live pair exceeds the remaining budget, no other pair can fit.
        if (transferred + p.cost > limit) break;
        const QRect merged = nodes[p.a].rect.united(nodes[p.b].rect);
        byX.erase(xKey(p.a)); byX.erase(xKey(p.b));
        byY.erase(yKey(p.a)); byY.erase(yKey(p.b));
        nodes[p.a].active = nodes[p.b].active = false;
        transferred += p.cost;
        const size_t next = nodes.size();
        nodes.push_back({merged});
        insert(next);
    }
    QList<QRect> result;
    for (const auto& n : nodes) if (n.active) result.append(n.rect);
    return result;
}

// GLES2 has no core UNPACK_ROW_LENGTH. Pack RGBA rows tightly, honoring the
// source stride; each packed row is a multiple of four bytes. Buffer capacity
// persists across tiles and frames. The callback must consume bytes immediately.
template<class Upload>
inline void packedTiles(const QImage& image, const QList<QRect>& rects,
                        std::vector<unsigned char>& buffer, Upload upload) {
    Q_ASSERT(image.format() == QImage::Format_RGBA8888_Premultiplied ||
             image.format() == QImage::Format_RGBA8888);
    for (const QRect& r : rects) {
        Q_ASSERT(!r.isEmpty() && image.rect().contains(r));
        const size_t rowBytes = size_t(r.width()) * 4;
        buffer.resize(rowBytes * size_t(r.height()));
        for (int y = 0; y < r.height(); ++y)
            std::memcpy(buffer.data() + size_t(y) * rowBytes,
                        image.constScanLine(r.y() + y) + size_t(r.x()) * 4, rowBytes);
        upload(r, buffer.data());
    }
}
} // namespace hudupload
