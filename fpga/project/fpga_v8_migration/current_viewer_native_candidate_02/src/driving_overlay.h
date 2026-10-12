#pragma once

#include <QList>
#include <QRect>
#include <QRectF>

class QPainter;
struct DrivingSnapshot;

namespace tdm {
// Logical canvas coordinates. Includes alarm strips even when the alarm is off,
// so callers can clear a previous alarm without uploading the whole content.
QList<QRect> drivingOverlayRegions(const QRectF& content);
void paintDrivingOverlay(QPainter& painter, QRectF content,
                         const DrivingSnapshot& snapshot);
} // namespace tdm
