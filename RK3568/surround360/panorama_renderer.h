#pragma once

#include "capture_source.h"
#include "surround_engine.h"
#include <memory>

namespace surround {

// Call initialize(), draw() and release() with the owning GL context current.
// The caller selects the framebuffer/viewport and draws its HUD afterwards.
class PanoramaRenderer {
public:
    PanoramaRenderer();
    ~PanoramaRenderer();
    PanoramaRenderer(const PanoramaRenderer &) = delete;
    PanoramaRenderer &operator=(const PanoramaRenderer &) = delete;

    bool initialize(QString *error = nullptr);
    void release();
    bool draw(const CaptureSnapshot &snapshot, const Configuration &configuration,
              double yawDeg, double pitchDeg, double hfovDeg,
              float viewportAspect, qint64 nowMs, QString *error = nullptr);

    // Bytes uploaded in the most recent draw and over this GL initialization.
    quint64 uploadBytes() const;
    quint64 totalUploadBytes() const;

private:
    struct Impl;
    std::unique_ptr<Impl> d;
};

} // namespace surround
