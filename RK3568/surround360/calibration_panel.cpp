#include "calibration_panel.h"

#include <QCheckBox>
#include <QComboBox>
#include <QDateTime>
#include <QDir>
#include <QDoubleSpinBox>
#include <QFileDialog>
#include <QFileInfo>
#include <QGroupBox>
#include <QHBoxLayout>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QLabel>
#include <QMessageBox>
#include <QMouseEvent>
#include <QPainter>
#include <QPushButton>
#include <QSaveFile>
#include <QScrollArea>
#include <QStringList>
#include <QVBoxLayout>
#include <algorithm>
#include <cmath>
#include <functional>
#include <utility>

namespace surround {
namespace {
const char *const Roles[CameraCount] = {"前双目1", "前双目2", "左侧", "右侧", "后双目1", "后双目2"};
const QColor PointColors[4] = {QColor("#ffcc33"), QColor("#40d9ff"),
                             QColor("#ff7198"), QColor("#83ed75")};

// A QWidget canvas keeps selection, drawing and dragging in the same fitted coordinates.
class GroundCanvas : public QWidget {
public:
    explicit GroundCanvas(bool bird, QWidget *parent = nullptr) : QWidget(parent), bird_(bird) {
        setMinimumSize(bird ? QSize(512, 512) : QSize(640, 480));
        setSizePolicy(QSizePolicy::Expanding, QSizePolicy::Expanding);
        setMouseTracking(true);
    }
    std::array<QPointF, 4> points{};
    std::function<void()> changed;
    QImage image;
    QString placeholder;
    double yaw = 0;
    int birdSize = 512;
    QSize coordinates() const { return bird_ ? QSize(birdSize, birdSize) : QSize(SourceWidth, SourceHeight); }
    QRectF content() const {
        const QSize logical = coordinates();
        const double scale = std::min((width() - 28.0) / logical.width(),
                                      (height() - 28.0) / logical.height());
        const QSizeF fitted(logical.width() * scale, logical.height() * scale);
        return QRectF(QPointF((width() - fitted.width()) / 2, (height() - fitted.height()) / 2), fitted);
    }
    QPointF screen(const QPointF &p) const {
        const QRectF r = content(); const QSize s = coordinates();
        return r.topLeft() + QPointF(p.x() * r.width() / s.width(), p.y() * r.height() / s.height());
    }
protected:
    void paintEvent(QPaintEvent *) override {
        QPainter p(this); p.setRenderHint(QPainter::Antialiasing);
        p.fillRect(rect(), QColor("#202731"));
        const QRectF r = content();
        p.save(); p.setClipRect(r);
        p.fillRect(r, QColor("#111923"));
        if (!bird_ && !image.isNull()) p.drawImage(r, image);
        if (bird_) {
            p.setPen(QPen(QColor("#364552"), 1));
            for (int i = 0; i <= 8; ++i) {
                const double x = r.left() + i * r.width() / 8;
                const double y = r.top() + i * r.height() / 8;
                p.drawLine(QPointF(x, r.top()), QPointF(x, r.bottom()));
                p.drawLine(QPointF(r.left(), y), QPointF(r.right(), y));
            }
            p.setPen(QPen(QColor("#8296aa"), 1));
            p.drawLine(QPointF(r.center().x(), r.top()), QPointF(r.center().x(), r.bottom()));
            p.drawLine(QPointF(r.left(), r.center().y()), QPointF(r.right(), r.center().y()));
            const double factor = birdSize / 512.0;
            const QRectF vehicle(screen(QPointF(birdSize / 2.0 - 40 * factor, birdSize / 2.0 - 65 * factor)),
                                 screen(QPointF(birdSize / 2.0 + 40 * factor, birdSize / 2.0 + 65 * factor)));
            p.fillRect(vehicle, QColor(45, 61, 78, 225));
            p.setPen(QColor("#cbd6df")); p.drawRect(vehicle);
            p.drawText(vehicle, Qt::AlignCenter, QStringLiteral("车头 ↑\n车辆"));
            const double angle = yaw * 3.14159265358979323846 / 180.0;
            const QPointF start = r.center();
            const QPointF end = start + QPointF(std::sin(angle), -std::cos(angle)) * (r.width() * .3);
            p.setPen(QPen(QColor("#f7bc51"), 3)); p.drawLine(start, end);
            const QPointF side(std::cos(angle), std::sin(angle));
            const QPointF along(std::sin(angle), -std::cos(angle));
            p.drawLine(end, end - along * 13 + side * 7);
            p.drawLine(end, end - along * 13 - side * 7);
            p.setPen(QColor("#b7c7d7"));
            p.drawText(r.adjusted(8, 6, -8, -6), Qt::AlignTop | Qt::AlignLeft,
                       QStringLiteral("前 ↑    像素坐标 0…%1\n网格间隔 %2 像素").arg(birdSize - 1).arg(birdSize / 8));
        } else if (image.isNull()) {
            p.setPen(QColor("#cbd6df")); p.drawText(r.adjusted(20, 20, -20, -20), Qt::AlignCenter | Qt::TextWordWrap, placeholder);
        }
        QPolygonF poly; for (const auto &point : points) poly << screen(point);
        p.setBrush(QColor(30, 160, 230, 35)); p.setPen(QPen(QColor("#eeeeee"), 2)); p.drawPolygon(poly);
        for (int i = 0; i < 4; ++i) {
            const QPointF pos = screen(points[i]);
            p.setBrush(PointColors[i]); p.setPen(QPen(Qt::black, 1)); p.drawEllipse(pos, 8, 8);
            p.setPen(Qt::black); p.drawText(QRectF(pos.x() - 8, pos.y() - 8, 16, 16), Qt::AlignCenter, QString::number(i + 1));
            const QString text = QStringLiteral("%1 %2 (%3, %4)").arg(i + 1)
                .arg(i < 2 ? QStringLiteral("远") : QStringLiteral("近"))
                .arg(qRound(points[i].x())).arg(qRound(points[i].y()));
            const QSizeF textSize(p.fontMetrics().horizontalAdvance(text) + 10, p.fontMetrics().height() + 4);
            const double tx = std::clamp(pos.x() + 12, r.left(), std::max(r.left(), r.right() - textSize.width()));
            const double ty = std::clamp(pos.y() - 22, r.top(), std::max(r.top(), r.bottom() - textSize.height()));
            const QRectF label(QPointF(tx, ty), textSize);
            p.fillRect(label, QColor(0, 0, 0, 170)); p.setPen(PointColors[i]); p.drawText(label, Qt::AlignCenter, text);
        }
        p.restore(); p.setPen(QColor("#657382")); p.drawRect(r);
    }
    void mousePressEvent(QMouseEvent *event) override {
        if (event->button() != Qt::LeftButton) return;
        double best = 15 * 15; drag_ = -1;
        for (int i = 0; i < 4; ++i) {
            const QPointF d = screen(points[i]) - event->localPos();
            const double distance = d.x() * d.x() + d.y() * d.y();
            if (distance <= best) { best = distance; drag_ = i; }
        }
        if (drag_ >= 0) setCursor(Qt::ClosedHandCursor);
    }
    void mouseMoveEvent(QMouseEvent *event) override {
        if (drag_ < 0) return;
        const QRectF r = content(); const QSize s = coordinates();
        points[drag_] = QPointF(std::clamp((event->localPos().x() - r.left()) * s.width() / r.width(), 0.0, s.width() - 1.0),
                               std::clamp((event->localPos().y() - r.top()) * s.height() / r.height(), 0.0, s.height() - 1.0));
        update(); if (changed) changed();
    }
    void mouseReleaseEvent(QMouseEvent *) override { drag_ = -1; unsetCursor(); }
private:
    bool bird_;
    int drag_ = -1;
};

// Display the same rectified pixel plane used by the engine's ground control points.
QImage rectifiedImage(const QImage &input, const CameraCalibration &c) {
    if (input.isNull()) return {};
    const QImage raw = input.scaled(SourceWidth, SourceHeight, Qt::IgnoreAspectRatio, Qt::SmoothTransformation).convertToFormat(QImage::Format_RGB32);
    const double radians = c.hfovDeg * 3.14159265358979323846 / 180.0;
    const double fx = c.intrinsicCalibrated ? c.K[0] : (c.lens == LensModel::Fisheye ? SourceWidth / radians : SourceWidth / (2 * std::tan(radians / 2)));
    const double fy = c.intrinsicCalibrated ? c.K[4] : fx;
    const double skew = c.intrinsicCalibrated ? c.K[1] : 0;
    const double cx = c.intrinsicCalibrated ? c.K[2] : SourceWidth * .5;
    const double cy = c.intrinsicCalibrated ? c.K[5] : SourceHeight * .5;
    QImage result(SourceWidth, SourceHeight, QImage::Format_RGB32); result.fill(Qt::black);
    for (int row = 0; row < SourceHeight; ++row) {
        QRgb *out = reinterpret_cast<QRgb *>(result.scanLine(row));
        for (int col = 0; col < SourceWidth; ++col) {
            double y = (row - cy) / fy, x = (col - cx - skew * y) / fx;
            const double r2 = x * x + y * y;
            if (c.lens == LensModel::Fisheye) {
                const double r = std::sqrt(r2), theta = std::atan(r), t2 = theta * theta;
                double td = theta;
                if (c.intrinsicCalibrated) td *= 1 + c.D[0] * t2 + c.D[1] * t2 * t2 + c.D[2] * t2 * t2 * t2 + c.D[3] * t2 * t2 * t2 * t2;
                const double factor = r > 1e-12 ? td / r : 1; x *= factor; y *= factor;
            } else if (c.intrinsicCalibrated) {
                const double r4 = r2 * r2, r6 = r4 * r2;
                const double divisor = c.distortionCount == 8 ? 1 + c.D[5] * r2 + c.D[6] * r4 + c.D[7] * r6 : 1;
                if (std::abs(divisor) < 1e-12) continue;
                const double radial = (1 + c.D[0] * r2 + c.D[1] * r4 + (c.distortionCount >= 5 ? c.D[4] * r6 : 0)) / divisor;
                const double dx = x * radial + 2 * c.D[2] * x * y + c.D[3] * (r2 + 2 * x * x);
                y = y * radial + c.D[2] * (r2 + 2 * y * y) + 2 * c.D[3] * x * y; x = dx;
            }
            const double px = fx * x + skew * y + cx, py = fy * y + cy;
            if (std::isfinite(px) && std::isfinite(py) && px >= 0 && py >= 0 && px < SourceWidth - 1 && py < SourceHeight - 1)
                out[col] = raw.pixel(qRound(px), qRound(py));
        }
    }
    return result;
}

class PanelContent : public QWidget {
public:
    PanelContent(const Configuration &config, const CaptureSnapshot &snapshot, QString path,
                 std::function<void(Configuration)> applied, QWidget *parent)
        : QWidget(parent), draft_(config), snapshot_(snapshot), path_(std::move(path)), applied_(std::move(applied)), openedMs_(captureMonotonicMs()) {
        for (int i = 0; i < CameraCount; ++i) {
            const qint64 age = openedMs_ - snapshot_.capturedMs[i];
            if (age < 0 || age > 1000) snapshot_.images[i] = QImage();
        }
        presets();
        auto *outer = new QVBoxLayout(this);
        auto *intro = new QLabel(QStringLiteral("拖动同色编号，使图像与俯视网格中的四个地面点一一对应：1、2 为远侧，3、4 为近侧，沿四边形依次排列。\n需要对应地面控制点，未测量前属于近似投影。所有编辑保留为草稿，保存并应用后更新预览。"));
        intro->setWordWrap(true); outer->addWidget(intro);
        auto *controls = new QHBoxLayout;
        camera_ = new QComboBox;
        for (int i = 0; i < CameraCount; ++i) camera_->addItem(QStringLiteral("C%1 · %2").arg(i + 1).arg(QString::fromUtf8(Roles[i])));
        controls->addWidget(new QLabel(QStringLiteral("相机"))); controls->addWidget(camera_);
        yaw_ = spin(-180, 180); hfov_ = spin(30, 170); pitch_ = spin(-89, 89); roll_ = spin(-180, 180);
        hfov_->setToolTip(QStringLiteral("镜头未标定时用于近似投影；导入已标定镜头参数后使用其实际内参。"));
        for (const auto &item : {std::make_pair(QStringLiteral("环绕方向"), yaw_), std::make_pair(QStringLiteral("水平视场"), hfov_),
                                std::make_pair(QStringLiteral("俯仰"), pitch_), std::make_pair(QStringLiteral("横滚"), roll_)}) {
            controls->addWidget(new QLabel(item.first)); controls->addWidget(item.second);
        }
        outer->addLayout(controls);
        auto *flags = new QHBoxLayout;
        yawMeasured_ = new QCheckBox(QStringLiteral("已手动对齐环绕方向"));
        auto *align = new QPushButton(QStringLiteral("确认方向对齐"));
        groundMeasured_ = new QCheckBox(QStringLiteral("已测量地面对应点"));
        groundMeasured_->setToolTip(QStringLiteral("仅在四点实际地面位置已测量、且两图编号对应时勾选。未勾选时使用默认近似投影。"));
        lensStatus_ = new QLabel;
        flags->addWidget(yawMeasured_); flags->addWidget(align); flags->addSpacing(16);
        flags->addWidget(groundMeasured_); flags->addStretch(); flags->addWidget(lensStatus_); outer->addLayout(flags);
        auto *scroll = new QScrollArea; scroll->setWidgetResizable(true);
        auto *canvases = new QWidget; auto *row = new QHBoxLayout(canvases);
        source_ = new GroundCanvas(false); destination_ = new GroundCanvas(true);
        auto *sourceBox = new QGroupBox(QStringLiteral("图像地面四点 · 640 × 480"));
        auto *destBox = new QGroupBox(QStringLiteral("俯视地面四点 · 前方朝上"));
        auto *sourceLayout = new QVBoxLayout(sourceBox); sourceLayout->addWidget(source_);
        auto *destLayout = new QVBoxLayout(destBox); destLayout->addWidget(destination_);
        row->addWidget(sourceBox); row->addWidget(destBox); scroll->setWidget(canvases); outer->addWidget(scroll, 1);
        captureStatus_ = new QLabel; captureStatus_->setWordWrap(true); outer->addWidget(captureStatus_);
        status_ = new QLabel(QStringLiteral("草稿尚未应用。")); status_->setWordWrap(true); outer->addWidget(status_);
        auto *actions = new QHBoxLayout;
        auto *capture = new QPushButton(QStringLiteral("采集六路标定图"));
        auto *import = new QPushButton(QStringLiteral("导入配置"));
        auto *reset = new QPushButton(QStringLiteral("恢复预览参数"));
        auto *save = new QPushButton(QStringLiteral("保存并应用"));
        auto *close = new QPushButton(QStringLiteral("关闭"));
        for (auto *button : {align, capture, import, reset, save, close}) button->setAutoDefault(false);
        actions->addWidget(capture); actions->addWidget(import); actions->addWidget(reset); actions->addStretch();
        actions->addWidget(save); actions->addWidget(close); outer->addLayout(actions);
        connect(camera_, QOverload<int>::of(&QComboBox::currentIndexChanged), this, [this](int i) { store(); selected_ = i; load(); });
        connect(align, &QPushButton::clicked, this, [this] { yawMeasured_->setChecked(true); dirty(); });
        connect(yawMeasured_, &QCheckBox::clicked, this, [this] { dirty(); });
        connect(groundMeasured_, &QCheckBox::clicked, this, [this] { dirty(); });
        connect(yaw_, QOverload<double>::of(&QDoubleSpinBox::valueChanged), this, [this](double value) {
            if (loading_) return;
            yawMeasured_->setChecked(false); destination_->yaw = value; destination_->update(); dirty();
        });
        for (auto *field : {hfov_, pitch_, roll_})
            connect(field, QOverload<double>::of(&QDoubleSpinBox::valueChanged), this, [this](double) {
                if (loading_) return;
                store();
                source_->image = rectifiedImage(snapshot_.images[selected_], draft_.cameras[selected_]);
                source_->update();
                dirty();
            });
        source_->changed = destination_->changed = [this] { dirty(); };
        connect(capture, &QPushButton::clicked, this, [this] { exportCaptures(); });
        connect(import, &QPushButton::clicked, this, [this] {
            const QString file = QFileDialog::getOpenFileName(this, QStringLiteral("导入镜头与标定配置"), QFileInfo(path_).absolutePath(), QStringLiteral("JSON (*.json)"));
            if (file.isEmpty()) return;
            Configuration imported; QString error;
            if (!Configuration::load(file, imported, &error)) { showError(QStringLiteral("导入失败"), error); return; }
            draft_ = imported; presets(); load(); dirty();
        });
        connect(reset, &QPushButton::clicked, this, [this] { draft_ = Configuration(); presets(); load(); dirty(); });
        connect(save, &QPushButton::clicked, this, [this] {
            store(); QString error;
            if (!draft_.validate(&error)) { showError(QStringLiteral("参数无效"), error); return; }
            if (!draft_.save(path_, &error)) { showError(QStringLiteral("保存失败"), error); return; }
            applied_(draft_); status_->setText(QStringLiteral("已保存并应用。可继续调整或关闭。"));
        });
        connect(close, &QPushButton::clicked, parent, [parent] { static_cast<QDialog *>(parent)->close(); });
        load(); updateCaptureStatus();
    }
private:
    QDoubleSpinBox *spin(double low, double high) {
        auto *value = new QDoubleSpinBox; value->setRange(low, high); value->setDecimals(2);
        value->setSingleStep(.5); value->setSuffix(QStringLiteral("°")); value->setKeyboardTracking(false); return value;
    }
    void presets() {
        const Configuration defaults;
        for (int i = 0; i < CameraCount; ++i) {
            auto &c = draft_.cameras[i];
            const auto zero = [](const std::array<QPointF, 4> &quad) {
                return std::all_of(quad.begin(), quad.end(), [](const QPointF &p) { return p.isNull(); });
            };
            if (zero(c.groundSrc)) c.groundSrc = defaults.cameras[i].groundSrc;
            if (zero(c.groundDst)) {
                const std::array<QPointF, 4> local{{QPointF(-240, -210), QPointF(240, -210), QPointF(80, -65), QPointF(-80, -65)}};
                const double angle = c.yawDeg * 3.14159265358979323846 / 180.0;
                const double scale = draft_.birdSize / 512.0;
                for (int k = 0; k < 4; ++k) c.groundDst[k] = QPointF(draft_.birdSize * .5 + scale * (std::cos(angle) * local[k].x() - std::sin(angle) * local[k].y()),
                                                                 draft_.birdSize * .5 + scale * (std::sin(angle) * local[k].x() + std::cos(angle) * local[k].y()));
            }
        }
    }
    void store() {
        if (loading_) return;
        auto &c = draft_.cameras[selected_];
        c.yawDeg = yaw_->value(); c.hfovDeg = hfov_->value(); c.pitchDeg = pitch_->value(); c.rollDeg = roll_->value();
        c.yawCalibrated = yawMeasured_->isChecked(); c.groundCalibrated = groundMeasured_->isChecked();
        c.groundSrc = source_->points; c.groundDst = destination_->points;
    }
    void load() {
        loading_ = true;
        const auto &c = draft_.cameras[selected_];
        yaw_->setValue(c.yawDeg); hfov_->setValue(c.hfovDeg); pitch_->setValue(c.pitchDeg); roll_->setValue(c.rollDeg);
        yawMeasured_->setChecked(c.yawCalibrated); groundMeasured_->setChecked(c.groundCalibrated);
        lensStatus_->setText(QStringLiteral("%1 · 镜头参数%2").arg(c.lens == LensModel::Fisheye ? QStringLiteral("鱼眼") : QStringLiteral("针孔"))
                            .arg(c.intrinsicCalibrated ? QStringLiteral("已标定") : QStringLiteral("未标定")));
        source_->points = c.groundSrc; destination_->points = c.groundDst;
        source_->image = rectifiedImage(snapshot_.images[selected_], c);
        source_->placeholder = QStringLiteral("C%1 · %2\n暂无可用标定截图\n可导入配置或在重新打开时采集画面").arg(selected_ + 1).arg(QString::fromUtf8(Roles[selected_]));
        if (!snapshot_.error.isEmpty()) source_->placeholder += QStringLiteral("\n") + snapshot_.error;
        destination_->birdSize = draft_.birdSize; destination_->yaw = c.yawDeg;
        source_->update(); destination_->update(); loading_ = false;
    }
    void dirty() {
        if (loading_) return;
        status_->setText(groundMeasured_->isChecked() ? QStringLiteral("草稿尚未应用。请确认同色四点为已测量的对应地面点。")
                                                    : QStringLiteral("草稿尚未应用。未测量地面对应点时使用近似投影，编辑的四点仅保留为草稿。"));
    }
    void showError(const QString &title, const QString &detail) { QMessageBox::warning(this, title, detail); }
    void updateCaptureStatus() {
        QStringList present, missing;
        for (int i = 0; i < CameraCount; ++i) {
            if (snapshot_.images[i].isNull()) missing << QStringLiteral("C%1").arg(i + 1);
            else present << QStringLiteral("C%1（%2 ms）").arg(i + 1).arg(openedMs_ - snapshot_.capturedMs[i]);
        }
        captureStatus_->setText(QStringLiteral("截图用于标定，非同步；画面固定于打开面板时。打开时帧龄：%1。%2")
            .arg(present.isEmpty() ? QStringLiteral("无可用画面") : present.join(QStringLiteral("、")))
            .arg(missing.isEmpty() ? QString() : QStringLiteral("无画面或超过一秒：%1").arg(missing.join(QStringLiteral("、")))));
    }
    void exportCaptures();
    Configuration draft_;
    CaptureSnapshot snapshot_;
    QString path_;
    std::function<void(Configuration)> applied_;
    qint64 openedMs_;
    int selected_ = 0;
    bool loading_ = false;
    QComboBox *camera_;
    QDoubleSpinBox *yaw_, *hfov_, *pitch_, *roll_;
    QCheckBox *yawMeasured_, *groundMeasured_;
    QLabel *lensStatus_, *status_, *captureStatus_;
    GroundCanvas *source_, *destination_;
};

void PanelContent::exportCaptures() {
    const int available = int(std::count_if(snapshot_.images.begin(), snapshot_.images.end(),
                                           [](const QImage &image) { return !image.isNull(); }));
    if (!available) { showError(QStringLiteral("无法采集"), QStringLiteral("没有可用画面。请等待相机出图后重新打开标定面板。")); return; }
    const QDateTime utc = QDateTime::currentDateTimeUtc();
    QDir root(QFileInfo(path_).absolutePath());
    const QString base = QStringLiteral("calibration_captures/") + utc.toString(QStringLiteral("yyyyMMdd'T'HHmmsszzz'Z'"));
    QString relative = base;
    for (int suffix = 1; root.exists(relative); ++suffix) relative = base + QStringLiteral("_%1").arg(suffix);
    if (!root.mkpath(relative)) { showError(QStringLiteral("采集失败"), QStringLiteral("无法创建截图目录：%1").arg(root.filePath(relative))); return; }
    const QDir folder(root.filePath(relative));
    const qint64 savedMs = captureMonotonicMs();
    QJsonArray frames;
    for (int i = 0; i < CameraCount; ++i) {
        const QString filename = QStringLiteral("C%1.png").arg(i + 1);
        const bool present = !snapshot_.images[i].isNull();
        QJsonObject item{{QStringLiteral("camera"), QStringLiteral("C%1").arg(i + 1)},
                         {QStringLiteral("role"), QString::fromUtf8(Roles[i])},
                         {QStringLiteral("available"), present},
                         {QStringLiteral("capturedMs"), QString::number(snapshot_.capturedMs[i])},
                         {QStringLiteral("sequence"), QString::number(snapshot_.sequences[i])},
                         {QStringLiteral("ageAtOpenMs"), double(openedMs_ - snapshot_.capturedMs[i])},
                         {QStringLiteral("ageAtSaveMs"), double(savedMs - snapshot_.capturedMs[i])},
                         {QStringLiteral("fps"), snapshot_.fps[i]},
                         {QStringLiteral("errors"), QString::number(snapshot_.errors[i])}};
        if (present) {
            QSaveFile output(folder.filePath(filename));
            if (!output.open(QIODevice::WriteOnly) || !snapshot_.images[i].save(&output, "PNG") || !output.commit()) {
                showError(QStringLiteral("采集失败"), QStringLiteral("无法保存 %1。已保存的截图位于：%2\n%3").arg(filename, folder.absolutePath(), output.errorString())); return;
            }
            item.insert(QStringLiteral("file"), filename);
            item.insert(QStringLiteral("width"), snapshot_.images[i].width());
            item.insert(QStringLiteral("height"), snapshot_.images[i].height());
        } else item.insert(QStringLiteral("reason"), QStringLiteral("missing_or_older_than_1000ms_at_open"));
        frames.append(item);
    }
    const QJsonObject manifest{{QStringLiteral("version"), 1},
                               {QStringLiteral("savedUtc"), utc.toString(Qt::ISODateWithMs)},
                               {QStringLiteral("simultaneous"), false},
                               {QStringLiteral("note"), QStringLiteral("截图用于标定，非同步；保存的是打开面板时的固定画面。")},
                               {QStringLiteral("openedMonotonicMs"), QString::number(openedMs_)},
                               {QStringLiteral("savedMonotonicMs"), QString::number(savedMs)},
                               {QStringLiteral("frames"), frames}};
    QSaveFile output(folder.filePath(QStringLiteral("manifest.json")));
    const QByteArray data = QJsonDocument(manifest).toJson(QJsonDocument::Indented);
    if (!output.open(QIODevice::WriteOnly) || output.write(data) != data.size() || !output.commit()) {
        showError(QStringLiteral("采集失败"), QStringLiteral("截图已保存，但截图说明保存失败：%1\n%2").arg(folder.absolutePath(), output.errorString())); return;
    }
    status_->setText(QStringLiteral("已保存 %1 路标定截图（非同步）：%2").arg(available).arg(folder.absolutePath()));
}

} // namespace

CalibrationPanel::CalibrationPanel(const Configuration &config, const CaptureSnapshot &snapshot,
                                   QString configPath, QWidget *parent) : QDialog(parent) {
    setWindowTitle(QStringLiteral("六路环绕标定")); resize(1270, 850);
    auto *layout = new QVBoxLayout(this);
    layout->addWidget(new PanelContent(config, snapshot, std::move(configPath),
                                      [this](Configuration value) { emit applied(value); }, this));
}

} // namespace surround
