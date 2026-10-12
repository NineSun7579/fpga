#include "hdmi_view.h"
#include <cstdio>

int tdm::runHdmiViewSelfTest() {
    int failures = 0;
    auto expect = [&](bool ok, const char *name) {
        std::fprintf(stderr, "%s %s\n", ok ? "[ok]" : "[FAIL]", name);
        failures += !ok;
    };
    QImage left(640, 480, QImage::Format_RGB16), right(640, 480, QImage::Format_RGB16);
    left.fill(Qt::red); right.fill(Qt::blue);
    QByteArray l(reinterpret_cast<const char *>(left.constBits()), left.sizeInBytes());
    QByteArray r(reinterpret_cast<const char *>(right.constBits()), right.sizeInBytes());
    const QImage image = hdmiAnalyticsImage(l, r);
    expect(image.size() == QSize(640, 480) && image.format() == QImage::Format_RGB888,
           "full HDMI uses the existing analytics image contract");
    expect(image.pixelColor(100, 100).red() > 240 && image.pixelColor(540, 100).blue() > 240,
           "both HDMI halves reach inference in left-to-right order");
    expect(image.pixelColor(100, 59).red() == 114 && image.pixelColor(100, 420).red() == 114 &&
           image.pixelColor(100, 60).red() > 240 && image.pixelColor(540, 419).blue() > 240,
           "16:9 image has exactly 60 rows of padding on each side");
    expect(hdmiAnalyticsImage(l, {}).isNull(), "missing right half is rejected");
    expect(hdmiPairReady(1000, 980, 990, 3, 3, 3), "fresh pair is accepted");
    expect(!hdmiPairReady(1000, 800, 990, 3, 3, 3), "stale half is rejected");
    expect(!hdmiPairReady(1000, 940, 990, 3, 3, 3), "excessive capture skew is rejected");
    expect(!hdmiPairReady(1000, 980, 990, 3, 2, 3), "pre-toggle half is rejected");
    // Verify the model-to-screen transform for a box crossing the join.
    const QRectF modelBox(300, hdmiModelPad + 90, 40, 180);
    const QRectF screenBox(modelBox.x() * 3, (modelBox.y() - hdmiModelPad) * 3,
                           modelBox.width() * 3, modelBox.height() * 3);
    expect(screenBox == QRectF(900, 270, 120, 540), "cross-seam box maps onto the full 1920x1080 image");
    std::fprintf(stderr, failures ? "HDMI_VIEW_SELFTEST_FAIL\n" : "HDMI_VIEW_SELFTEST_PASS\n");
    return failures ? 2 : 0;
}
