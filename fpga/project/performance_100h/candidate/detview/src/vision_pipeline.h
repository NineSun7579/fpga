#pragma once

#include "vision_types.h"
#include <QThread>
#include <QStringList>
#include <memory>

// Public entry points are safe from the controller and capture threads. The
// QThread object stays in its owner's thread; all vision work runs in run().
class VisionPipeline : public QThread {
    Q_OBJECT
public:
    explicit VisionPipeline(VisionOptions options, QObject* parent = nullptr);
    ~VisionPipeline() override;
    void submitFrame(const VisionFrame& frame);
    void configure(int sourceGeneration, int selectedCamera, bool lane,
                   const QStringList& modelPaths);
    void submitDetections(QString modelPath, int sourceGeneration, quint64 frameId,
                          QVector<Detection> detections, double inferMs);
    void inferenceFailed(int sourceGeneration, quint64 frameId);
    void stop();
    static bool selfTest();
signals:
    void inferenceRequested(VisionFrame frame);
    void tracksReady(QString modelPath, int sourceGeneration, quint64 frameId,
                     QVector<Detection> detections, double matchingMs);
    void stereoReady(int sourceGeneration, quint64 leftFrameId, QImage disparity,
                     QString status);
    void diagnostics(QString text);
protected:
    void run() override;
private:
    struct Impl;
    std::unique_ptr<Impl> d;
};
