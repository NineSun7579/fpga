#include "driving_demo.h"
#include "driving_overlay.h"
#include "driving_overlay_validation.h"
#include <QDir>
#include <QPainter>
#include <cstdio>

int runDrivingOverlayValidation(const QString &outputDirectory) {
    QDir directory(outputDirectory);
    if (!directory.mkpath(".")) return 2;
    const QStringList names{"tlr_motor_red", "tly_motor_amber", "tlg_motor_green"};
    const QRectF content(0, 56, 1920, 984);
    auto frame = [&](const char *name, int signal, DrivingMode mode, DrivingLane lane,
                     bool moving, bool alarm) {
        DrivingDemo demo;
        demo.setEnabled(true); demo.setLane(lane); demo.setMode(mode);
        Detection detection;
        detection.cls = signal; detection.score = 0.95f;
        demo.observe(names, {detection}, 1000, 1000);
        demo.observe(names, {detection}, 1200, 1200);
        const auto state = demo.snapshot(1200);
        if (state.moving != moving || state.alarm != alarm) return false;
        QImage image(1920, 1080, QImage::Format_ARGB32_Premultiplied);
        image.fill(QColor(15, 24, 35));
        QPainter painter(&image);
        painter.setPen(QPen(QColor(140, 150, 160), 3));
        painter.drawLine(320, 980, 800, 400);
        painter.drawLine(960, 980, 960, 400);
        painter.drawLine(1600, 980, 1120, 400);
        painter.drawLine(0, 600, 1920, 600);
        painter.setPen(QColor(250, 225, 70));
        QFont font; font.setPixelSize(25); painter.setFont(font);
        painter.drawText(QRect(20, 8, 1850, 40), "逻辑/绘制自测：合成检测结果，非实景识别截图");
        tdm::paintDrivingOverlay(painter, content, state);
        painter.end();
        if (alarm) {
            bool redBorder = false;
            for (int y = 58; y < 80; ++y) {
                const QColor color = image.pixelColor(2, y);
                redBorder |= color.red() > 180 && color.red() > color.green() * 2;
            }
            if (!redBorder) return false;
        }
        return image.save(directory.filePath(QString::fromLatin1(name) + ".png"));
    };
    const bool ok = frame("red_stop", 0, DrivingMode::Auto, DrivingLane::Straight, false, false) &&
        frame("green_straight", 2, DrivingMode::Auto, DrivingLane::Straight, true, false) &&
        frame("green_left", 2, DrivingMode::Auto, DrivingLane::Left, true, false) &&
        frame("red_forced_alarm", 0, DrivingMode::ForcedGo, DrivingLane::Right, true, true) &&
        frame("manual_stop", 2, DrivingMode::Stop, DrivingLane::Left, false, false);
    std::fprintf(stderr, ok ? "DRIVING_OVERLAY_SELFTEST_PASS\n" : "DRIVING_OVERLAY_SELFTEST_FAIL\n");
    return ok ? 0 : 2;
}
