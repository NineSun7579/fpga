#include "driving_overlay.h"
#include "driving_demo.h"

#include <QColor>
#include <QFont>
#include <QFontMetricsF>
#include <QPainter>
#include <QPainterPath>
#include <QPen>
#include <QTransform>
#include <QtMath>

#include <algorithm>

namespace {
const QColor textColor(239, 246, 250);
const QColor mutedColor(168, 185, 197);
const QColor turquoise(69, 220, 217);
const QColor goColor(65, 231, 133);
const QColor alarmColor(255, 65, 75);
const QColor warningColor(255, 197, 76);

struct OverlayLayout {
    qreal scale = 0;
    QRectF panel;
    QRectF arrows;
    QList<QRectF> borders;
};

OverlayLayout overlayLayout(const QRectF& content) {
    OverlayLayout layout;
    if (content.isEmpty() || !qIsFinite(content.x()) || !qIsFinite(content.y()) ||
        !qIsFinite(content.width()) || !qIsFinite(content.height()) ||
        !qIsFinite(content.right()) || !qIsFinite(content.bottom()))
        return layout;

    layout.scale = std::min(qreal(1), std::min(content.width() / 1920,
                                            content.height() / 1080));
    const qreal s = layout.scale;
    layout.panel = QRectF(content.right() - 24 * s - 570 * s,
                          content.top() + 48 * s, 570 * s, 225 * s);
    layout.arrows = QRectF(content.center().x() - 180 * s,
                           content.bottom() - 32 * s - 130 * s, 360 * s, 130 * s);
    const qreal border = std::min(qreal(6) * s,
                                 std::min(content.width(), content.height()) / 2);
    layout.borders << QRectF(content.left(), content.top(), content.width(), border)
                   << QRectF(content.left(), content.bottom() - border,
                             content.width(), border)
                   << QRectF(content.left(), content.top() + border,
                             border, content.height() - 2 * border)
                   << QRectF(content.right() - border, content.top() + border,
                             border, content.height() - 2 * border);
    return layout;
}

QString laneText(DrivingLane lane) {
    switch (lane) {
    case DrivingLane::Left: return QStringLiteral("左转");
    case DrivingLane::Right: return QStringLiteral("右转");
    case DrivingLane::Straight: return QStringLiteral("直行");
    }
    return QStringLiteral("未知");
}

QString signalText(DrivingSignal signal) {
    switch (signal) {
    case DrivingSignal::Red: return QStringLiteral("红灯");
    case DrivingSignal::Amber: return QStringLiteral("黄灯");
    case DrivingSignal::Green: return QStringLiteral("绿灯");
    case DrivingSignal::Off: return QStringLiteral("熄灭");
    case DrivingSignal::Unknown: return QStringLiteral("未知");
    }
    return QStringLiteral("未知");
}

QColor signalColor(DrivingSignal signal) {
    switch (signal) {
    case DrivingSignal::Red: return alarmColor;
    case DrivingSignal::Amber: return warningColor;
    case DrivingSignal::Green: return goColor;
    default: return mutedColor;
    }
}

QString modeText(DrivingMode mode) {
    switch (mode) {
    case DrivingMode::Auto: return QStringLiteral("自动");
    case DrivingMode::Stop: return QStringLiteral("停车");
    case DrivingMode::ForcedGo: return QStringLiteral("强制行驶");
    }
    return QStringLiteral("未知");
}

void setFont(QPainter& painter, int pixels, bool bold = false) {
    QFont font = painter.font();
    font.setPixelSize(pixels);
    font.setBold(bold);
    painter.setFont(font);
}

void drawText(QPainter& painter, const QRectF& rect, const QString& text,
              const QColor& color, int pixels, bool bold = false,
              int alignment = Qt::AlignLeft | Qt::AlignVCenter) {
    setFont(painter, pixels, bold);
    painter.setPen(color);
    const QString fitted = QFontMetricsF(painter.font()).elidedText(
        text, Qt::ElideRight, rect.width());
    painter.drawText(rect, alignment | Qt::TextSingleLine, fitted);
}

void drawDot(QPainter& painter, const QPointF& center, bool lit, const QColor& color) {
    painter.setPen(QPen(lit ? color.lighter(125) : QColor(98, 115, 126), 1.5));
    painter.setBrush(lit ? color : QColor(38, 49, 59));
    painter.drawEllipse(center, 6, 6);
}

void paintPanel(QPainter& painter, const DrivingSnapshot& snapshot) {
    painter.setPen(QPen(snapshot.alarm ? alarmColor : turquoise, 1.5));
    painter.setBrush(snapshot.alarm ? QColor(62, 13, 21, 238) : QColor(12, 23, 35, 232));
    painter.drawRoundedRect(QRectF(1, 1, 568, 223), 10, 10);

    drawText(painter, QRectF(16, 10, 330, 30), QStringLiteral("智能驾驶模拟"),
             textColor, 25, true);
    drawText(painter, QRectF(360, 12, 194, 26), QStringLiteral("SIMULATED"),
             turquoise, 16, true, Qt::AlignRight | Qt::AlignVCenter);
    drawText(painter, QRectF(16, 45, 170, 28),
             QStringLiteral("车道  %1").arg(laneText(snapshot.lane)), textColor, 21, true);
    drawText(painter, QRectF(194, 45, 170, 28),
             QStringLiteral("信号  %1").arg(signalText(snapshot.signal)),
             signalColor(snapshot.signal), 21, true);
    drawText(painter, QRectF(380, 45, 174, 28),
             snapshot.moving ? QStringLiteral("行为  行驶") : QStringLiteral("行为  停车"),
             snapshot.moving ? goColor : textColor, 21, true);

    drawText(painter, QRectF(16, 78, 295, 25),
             QStringLiteral("模式  %1").arg(modeText(snapshot.mode)), mutedColor, 19);
    const bool warning = snapshot.warning ||
        (snapshot.mode == DrivingMode::ForcedGo && snapshot.signal == DrivingSignal::Unknown);
    if (snapshot.alarm) {
        drawText(painter, QRectF(310, 77, 244, 27), QStringLiteral("闯红灯报警"),
                 alarmColor, 23, true, Qt::AlignRight | Qt::AlignVCenter);
    } else if (warning) {
        drawText(painter, QRectF(310, 77, 244, 27), QStringLiteral("强制行驶警告"),
                 warningColor, 20, true, Qt::AlignRight | Qt::AlignVCenter);
    }

    QString reason = snapshot.reason.simplified();
    if (!snapshot.inputAvailable && reason.isEmpty()) reason = QStringLiteral("输入不可用，模拟车辆停车");
    if (reason.isEmpty()) {
        if (snapshot.alarm) reason = QStringLiteral("红灯下强制行驶");
        else if (warning) reason = QStringLiteral("信号未确认，强制行驶存在风险");
        else reason = snapshot.moving ? QStringLiteral("模拟行驶中") : QStringLiteral("模拟停车中");
    }
    drawText(painter, QRectF(16, 106, 538, 28),
             QStringLiteral("%1  %2").arg(warning && !snapshot.alarm
                                        ? QStringLiteral("警告") : QStringLiteral("状态"), reason),
             snapshot.alarm ? alarmColor : warning ? warningColor : textColor, 18);

    const DrivingLane lanes[] = {DrivingLane::Left, DrivingLane::Straight, DrivingLane::Right};
    const QString ledLabels[] = {QStringLiteral("LED0 左"), QStringLiteral("LED1 直"),
                                 QStringLiteral("LED2 右")};
    for (int i = 0; i < 3; ++i) {
        const qreal x = 23 + i * 137;
        const bool lit = snapshot.moving && snapshot.lane == lanes[i];
        drawDot(painter, QPointF(x, 148), lit, goColor);
        drawText(painter, QRectF(x + 13, 136, 113, 24), ledLabels[i],
                 lit ? goColor : mutedColor, 17, lit);
    }
    drawDot(painter, QPointF(438, 148), snapshot.alarm, alarmColor);
    drawText(painter, QRectF(451, 136, 103, 24), QStringLiteral("ALARM"),
             snapshot.alarm ? alarmColor : mutedColor, 16, snapshot.alarm);
    drawText(painter, QRectF(16, 164, 538, 22),
             QStringLiteral("行人 %1    车辆 %2    斑马线 %3")
                 .arg(snapshot.personCount).arg(snapshot.vehicleCount).arg(snapshot.zebraCount),
             mutedColor, 16);
    drawText(painter, QRectF(16, 191, 538, 23),
             QStringLiteral("← 左转 ↑ 直行 → 右转 | A 自动 X 停车 B 强制行驶"),
             textColor, 15);
}

QPainterPath arrowPath(DrivingLane lane) {
    QPainterPath path;
    if (lane == DrivingLane::Straight) {
        path.moveTo(50, 4);
        path.lineTo(78, 31);
        path.lineTo(60, 31);
        path.lineTo(60, 74);
        path.lineTo(40, 74);
        path.lineTo(40, 31);
        path.lineTo(22, 31);
    } else {
        path.moveTo(8, 27);
        path.lineTo(33, 4);
        path.lineTo(33, 18);
        path.lineTo(68, 18);
        path.quadTo(84, 18, 84, 34);
        path.lineTo(84, 74);
        path.lineTo(65, 74);
        path.lineTo(65, 37);
        path.lineTo(33, 37);
        path.lineTo(33, 51);
    }
    path.closeSubpath();
    if (lane == DrivingLane::Right) {
        QTransform mirror;
        mirror.translate(100, 0);
        mirror.scale(-1, 1);
        path = mirror.map(path);
    }
    return path;
}

void paintArrows(QPainter& painter, const DrivingSnapshot& snapshot) {
    const DrivingLane lanes[] = {DrivingLane::Left, DrivingLane::Straight, DrivingLane::Right};
    for (int i = 0; i < 3; ++i) {
        painter.save();
        painter.translate(i * 120 + 4, 4);
        const bool selected = snapshot.lane == lanes[i];
        const QColor outline = selected ? (snapshot.moving ? goColor : turquoise)
                                        : QColor(104, 120, 135);
        painter.setPen(QPen(outline, selected ? 2.5 : 1));
        painter.setBrush(QColor(12, 23, 35, 225));
        painter.drawRoundedRect(QRectF(0, 0, 112, 122), 10, 10);
        painter.translate(6, 6);
        painter.setPen(QPen(outline, selected ? 2.5 : 1.5, Qt::SolidLine,
                            Qt::RoundCap, Qt::RoundJoin));
        painter.setBrush(selected && snapshot.moving ? goColor : QColor(68, 83, 98));
        painter.drawPath(arrowPath(lanes[i]));
        drawText(painter, QRectF(0, 84, 100, 25), laneText(lanes[i]),
                 selected ? outline : mutedColor, 20, selected,
                 Qt::AlignHCenter | Qt::AlignVCenter);
        painter.restore();
    }
}
} // namespace

namespace tdm {
QList<QRect> drivingOverlayRegions(const QRectF& content) {
    const OverlayLayout layout = overlayLayout(content);
    QList<QRect> regions;
    if (layout.scale <= 0) return regions;
    const QRect bounds = content.toAlignedRect();
    const auto appendRegion = [&](const QRectF& rect) {
        const QRect region = rect.toAlignedRect().intersected(bounds);
        if (!region.isEmpty()) regions.append(region);
    };
    appendRegion(layout.panel);
    appendRegion(layout.arrows);
    for (const QRectF& border : layout.borders) appendRegion(border);
    return regions;
}

void paintDrivingOverlay(QPainter& painter, QRectF content,
                         const DrivingSnapshot& snapshot) {
    if (!snapshot.enabled) return;
    const OverlayLayout layout = overlayLayout(content);
    if (layout.scale <= 0) return;
    painter.save();
    painter.setClipRect(content, Qt::IntersectClip);
    painter.setRenderHint(QPainter::Antialiasing, true);
    painter.setRenderHint(QPainter::TextAntialiasing, true);
    if (snapshot.alarm) {
        for (const QRectF& border : layout.borders) painter.fillRect(border, alarmColor);
    }
    painter.save();
    painter.translate(layout.panel.topLeft());
    painter.scale(layout.scale, layout.scale);
    painter.setClipRect(QRectF(0, 0, 570, 225), Qt::IntersectClip);
    paintPanel(painter, snapshot);
    painter.restore();
    painter.save();
    painter.translate(layout.arrows.topLeft());
    painter.scale(layout.scale, layout.scale);
    painter.setClipRect(QRectF(0, 0, 360, 130), Qt::IntersectClip);
    paintArrows(painter, snapshot);
    painter.restore();
    painter.restore();
}
} // namespace tdm
