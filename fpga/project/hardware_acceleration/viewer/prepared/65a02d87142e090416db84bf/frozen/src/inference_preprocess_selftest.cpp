#include "inference_preprocess.h"
#include <cstdio>
#include <vector>

// Exact controller preprocessing from the captured baseline main.cpp:2817-2820.
static QImage baseline(const QImage& source) {
    QImage infer(640, 640, QImage::Format_RGB888);
    infer.fill(QColor(114, 114, 114));
    for (int y = 0; y < 480; ++y)
        memcpy(infer.scanLine(y + 80), source.constScanLine(y), 640 * 3);
    return infer;
}
static bool samePixels(const QImage* a, const QImage& b) {
    if (!a || a->size() != b.size()) return false;
    for (int y = 0; y < b.height(); ++y)
        if (memcmp(a->constScanLine(y), b.constScanLine(y), 640 * 3)) return false;
    return true;
}
int main() {
    bool ok = true;
    auto check = [&](bool value, const char* label) {
        if (!value) { std::fprintf(stderr, "FAIL: %s\n", label); ok = false; }
    };
    InferencePreprocessor prep;
    const uchar* storage = nullptr;
    for (int i = 0; i < 12; ++i) {
        // External RGB888 with row padding catches accidental contiguous copies.
        const int stride = 1920 + (i % 2 ? 28 : 0);
        std::vector<uchar> bytes(size_t(stride) * 480, 0xee);
        QImage source(bytes.data(), 640, 480, stride, QImage::Format_RGB888);
        for (int y = 0; y < 480; ++y)
            for (int x = 0; x < 1920; ++x)
                source.scanLine(y)[x] = uchar(i * 37 + y * 13 + x * 7);
        const auto* result = prep.prepare(source);
        check(samePixels(result, baseline(source)), "consecutive full baseline byte parity");
        if (!result) continue;
        if (!storage) storage = result->constBits();
        check(storage == result->constBits(), "worker storage reused");
        for (int y : {0, 79, 560, 639})
            for (int x = 0; x < 1920; ++x)
                check(result->constScanLine(y)[x] == 114, "padding is 114");
        check(bytes[stride - 1] == (stride == 1920 ? source.constScanLine(0)[1919] : 0xee),
              "source row padding preserved");
        std::vector<uchar> squareBytes(size_t(1948) * 640, uchar(i));
        QImage square(squareBytes.data(), 640, 640, 1948, QImage::Format_RGB888);
        check(prep.prepare(square) == &square && samePixels(prep.prepare(square), square),
              "strided square bypass preserves all pixels");
        QImage tight(640, 640, QImage::Format_RGB888); tight.fill(QColor(21, 42, 63));
        check(prep.prepare(tight) == &tight, "tight square bypass");
        check(samePixels(prep.prepare(source), baseline(source)), "square to raw preserves padding");
    }
    check(!prep.prepare(QImage()), "reject null");
    std::vector<uchar> shortRows(size_t(1916) * 480);
    QImage invalidStride(shortRows.data(), 640, 480, 1916, QImage::Format_RGB888);
    check(!prep.prepare(invalidStride), "reject undersized row stride");
    for (const auto size : {QSize(639, 480), QSize(641, 480), QSize(640, 479), QSize(640, 641)})
        check(!prep.prepare(QImage(size, QImage::Format_RGB888)), "reject dimensions");
    for (auto format : {QImage::Format_RGB32, QImage::Format_ARGB32, QImage::Format_RGB16,
                       QImage::Format_Grayscale8, QImage::Format_Indexed8})
        check(!prep.prepare(QImage(640, 480, format)), "reject non RGB888 formats");
    if (ok) std::puts("PREPROCESS_SELFTEST_PASS: baseline bytes, reuse, padding, stride, square transitions, malformed inputs");
    return ok ? 0 : 1;
}
