#include "hud_upload.h"
#include <QGuiApplication>
#include <QElapsedTimer>
#include <QOffscreenSurface>
#include <QOpenGLContext>
#include <QOpenGLFunctions>
#include <QPainter>
#include <cstdio>
#include <random>
#include <stdexcept>

namespace hudupload {
namespace {
void require(bool ok, const char* message) {
    if (!ok) throw std::runtime_error(message);
}
QList<QRect> check(const QRegion& region, const QRect& bounds, qint64 cost = 512) {
    const QRegion clipped = region & bounds;
    const auto tiles = coalesce(region, bounds, cost);
    QRegion covered;
    qint64 original = 0, bytesArea = 0;
    for (const auto& r : clipped) original += area(r);
    for (const auto& r : tiles) {
        require(!r.isEmpty() && bounds.contains(r), "tile outside image");
        covered += r; bytesArea += area(r);
    }
    require((clipped - covered).isEmpty(), "dirty pixels lost");
    require(bytesArea <= original + original / 4, "transfer budget exceeded");
    if (cost == 0) require(bytesArea <= original, "zero cost increased transfer");
    require(tiles.size() <= clipped.rectCount(), "call count grew");
    return tiles;
}
void outline(QRegion& r, QRect box, int thickness = 3) {
    r += QRegion(box) - QRegion(box.adjusted(thickness, thickness, -thickness, -thickness));
}
void geometryTests() {
    const QRect bounds(0, 0, 1898, 955);
    check({}, bounds);
    check(QRegion(QRect(-200, -200, 230, 230)) + QRect(1880, 930, 100, 100), bounds);
    check(QRegion(bounds), bounds);
    const QRegion smallGap = QRegion(QRect(10, 10, 10, 10)) + QRect(21, 10, 10, 10);
    require(check(smallGap, bounds).size() == 1, "cheap merge rejected");
    require(check(smallGap, bounds, 0).size() == 2, "zero cost allowed extra transfer");
    const QRegion expensiveGap = QRegion(QRect(10, 10, 10, 10)) + QRect(31, 10, 10, 10);
    require(check(expensiveGap, bounds).size() == 2, "global budget not enforced");
    QRegion oldLabels;
    oldLabels += QRect(0, 0, 1898, 56); oldLabels += QRect(0, 915, 1898, 40);
    for (int y : {62, 492}) for (int x : {6, 638, 1270}) oldLabels += QRect(x, y, 280, 30);
    QRegion fragmented = oldLabels;
    outline(fragmented, QRect(1, 57, 630, 428), 2);
    for (int i = 0; i < 12; ++i) {
        const QRect b(40 + i * 31, 100 + i * 17, 150 + i * 7, 210);
        outline(fragmented, b);
        fragmented += QRect(b.x(), b.y(), 150, 24);
        outline(fragmented, b.translated(7, 4)); // previous boxes
    }
    auto oldTiles = check(oldLabels, bounds);
    QElapsedTimer plannerTimer; plannerTimer.start();
    auto newTiles = check(fragmented, bounds);
    std::printf("moving-boxes planner_ms=%.3f (single local sample, not Mali)\n", plannerTimer.nsecsElapsed() / 1e6);
    require(newTiles.size() < fragmented.rectCount(), "fragmentation fixture did not batch");
    auto report = [](const char* name, QRegion r, const QList<QRect>& tiles) {
        qint64 a = 0, b = 0;
        for (auto box : r) a += area(box);
        for (auto box : tiles) b += area(box);
        std::printf("fixture=%s rects=%d->%d bytes=%lld->%lld\n", name, r.rectCount(),
                    int(tiles.size()), static_cast<long long>(a * 4), static_cast<long long>(b * 4));
    };
    report("labels", oldLabels, oldTiles); report("moving-boxes", fragmented, newTiles);
    std::mt19937 random(0x3568);
    for (int trial = 0; trial < 300; ++trial) {
        QRegion r;
        for (int n = 0; n < 25; ++n)
            r += QRect(int(random() % 240) - 20, int(random() % 180) - 20,
                       1 + int(random() % 60), 1 + int(random() % 60));
        check(r, QRect(0, 0, 200, 140), trial % 3 == 0 ? 0 : 512);
    }
}
void packingTests() {
    constexpr int w = 37, h = 29, stride = w * 4 + 20;
    std::vector<unsigned char> source(stride * h, 0xcc);
    for (int y = 0; y < h; ++y) for (int x = 0; x < w; ++x) for (int c = 0; c < 4; ++c)
        source[y * stride + x * 4 + c] = static_cast<unsigned char>((x * 17 + y * 31 + c * 43) & 255);
    QImage image(source.data(), w, h, stride, QImage::Format_RGBA8888);
    std::vector<unsigned char> packed;
    const QList<QRect> tiles{QRect(3, 7, 17, 13), QRect(36, 28, 1, 1), image.rect()};
    packedTiles(image, tiles, packed, [&](QRect r, const unsigned char* bytes) {
        for (int y = 0; y < r.height(); ++y) for (int x = 0; x < r.width(); ++x) for (int c = 0; c < 4; ++c)
            require(bytes[(y * r.width() + x) * 4 + c] ==
                    source[(r.y() + y) * stride + (r.x() + x) * 4 + c], "packed bytes/stride mismatch");
    });
    const auto* storage = packed.data();
    const size_t capacity = packed.capacity();
    packedTiles(image, {QRect(3, 7, 17, 13)}, packed, [](QRect, const unsigned char*) {});
    require(packed.data() == storage && packed.capacity() == capacity, "buffer not reused");
}
void readbackTests() {
    QOpenGLContext context;
    context.setFormat(QSurfaceFormat::defaultFormat());
    require(context.create(), "GL context creation failed");
    QOffscreenSurface surface; surface.setFormat(context.format()); surface.create();
    require(surface.isValid() && context.makeCurrent(&surface), "GL makeCurrent failed");
    auto* gl = context.functions(); gl->initializeOpenGLFunctions();
    std::printf("GL renderer=%s version=%s\n", gl->glGetString(GL_RENDERER), gl->glGetString(GL_VERSION));
    GLuint texture = 0, fbo = 0;
    gl->glGenTextures(1, &texture); gl->glBindTexture(GL_TEXTURE_2D, texture);
    gl->glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST);
    gl->glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST);
    gl->glPixelStorei(GL_UNPACK_ALIGNMENT, 4);
    gl->glPixelStorei(GL_PACK_ALIGNMENT, 4);
    QImage image(160, 120, QImage::Format_RGBA8888_Premultiplied);
    image.fill(Qt::transparent);
    const QRect previous(12, 10, 43, 70), current(83, 29, 55, 61);
    { QPainter p(&image); p.fillRect(previous, QColor(40, 200, 80, 190)); }
    gl->glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, image.width(), image.height(), 0,
                     GL_RGBA, GL_UNSIGNED_BYTE, image.constBits());
    gl->glGenFramebuffers(1, &fbo); gl->glBindFramebuffer(GL_FRAMEBUFFER, fbo);
    gl->glFramebufferTexture2D(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, GL_TEXTURE_2D, texture, 0);
    require(gl->glCheckFramebufferStatus(GL_FRAMEBUFFER) == GL_FRAMEBUFFER_COMPLETE, "FBO incomplete");
    QRegion currentRegion;
    outline(currentRegion, current);
    currentRegion += QRect(78, 38, 65, 14);
    currentRegion += QRect(90, 50, 55, 15);
    QRegion dirty = QRegion(previous) + currentRegion;
    { QPainter p(&image); p.setClipRegion(dirty); p.setCompositionMode(QPainter::CompositionMode_Source);
      p.fillRect(previous, Qt::transparent); p.fillRect(current, QColor(240, 30, 60, 170)); }
    std::vector<unsigned char> packed;
    const auto tiles = check(dirty, image.rect());
    require(tiles.size() < dirty.rectCount(), "readback fixture did not coalesce");
    packedTiles(image, tiles, packed, [&](QRect r, const unsigned char* bytes) {
        gl->glTexSubImage2D(GL_TEXTURE_2D, 0, r.x(), r.y(), r.width(), r.height(), GL_RGBA, GL_UNSIGNED_BYTE, bytes);
    });
    QImage result(image.size(), image.format());
    gl->glReadPixels(0, 0, image.width(), image.height(), GL_RGBA, GL_UNSIGNED_BYTE, result.bits());
    require(gl->glGetError() == GL_NO_ERROR, "GL upload/readback error");
    // Compare the entire texture to the independent full CPU image, including
    // removed pixels, gaps and all untouched pixels, not a copy of the packer.
    require(result == image, "GPU readback differs from full raster image");
    require(result.pixelColor(previous.center()).alpha() == 0, "removed box is not transparent");
    gl->glDeleteFramebuffers(1, &fbo); gl->glDeleteTextures(1, &texture);
    context.doneCurrent();
}
} // namespace
int runSelfTest() {
    try { geometryTests(); packingTests(); readbackTests(); }
    catch (const std::exception& e) { std::fprintf(stderr, "HUD_UPLOAD_SELFTEST_FAIL: %s\n", e.what()); return 2; }
    std::puts("HUD_UPLOAD_SELFTEST_PASS"); return 0;
}
} // namespace hudupload
#ifdef HUD_UPLOAD_STANDALONE
int main(int argc, char** argv) { QGuiApplication app(argc, argv); return hudupload::runSelfTest(); }
#endif
