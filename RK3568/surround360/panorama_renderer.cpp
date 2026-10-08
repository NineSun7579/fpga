#include "panorama_renderer.h"
#include "stereo_selection.h"

#include <QMatrix3x3>
#include <QOpenGLContext>
#include <QOpenGLFunctions>
#include <QOpenGLShaderProgram>
#include <QVector2D>
#include <QVector4D>
#include <algorithm>
#include <array>
#include <cmath>
#include <vector>

namespace surround {
namespace {
constexpr double Pi = 3.14159265358979323846;
using Matrix = std::array<double, 9>;
using Ray = std::array<double, 3>;
double radians(double degrees) { return degrees * Pi / 180.0; }
bool fail(QString *error, const QString &message) {
    if (error) *error = message;
    return false;
}
Matrix multiply(const Matrix &a, const Matrix &b) {
    Matrix out{};
    for (int r = 0; r < 3; ++r)
        for (int c = 0; c < 3; ++c)
            for (int k = 0; k < 3; ++k) out[r * 3 + c] += a[r * 3 + k] * b[k * 3 + c];
    return out;
}
Matrix rotation(double yaw, double pitch, double roll = 0) {
    const double y = radians(yaw), p = radians(pitch), r = radians(roll);
    const Matrix ry{{std::cos(y), 0, std::sin(y), 0, 1, 0, -std::sin(y), 0, std::cos(y)}};
    const Matrix rx{{1, 0, 0, 0, std::cos(p), -std::sin(p), 0, std::sin(p), std::cos(p)}};
    const Matrix rz{{std::cos(r), -std::sin(r), 0, std::sin(r), std::cos(r), 0, 0, 0, 1}};
    return multiply(multiply(ry, rx), rz);
}
Matrix transpose(const Matrix &m) {
    return {{m[0], m[3], m[6], m[1], m[4], m[7], m[2], m[5], m[8]}};
}
QMatrix3x3 qtMatrix(const Matrix &m) {
    QMatrix3x3 out;
    for (int r = 0; r < 3; ++r)
        for (int c = 0; c < 3; ++c) out(r, c) = float(m[r * 3 + c]);
    return out;
}
struct Model {
    Matrix inverse;
    double fx, fy, cx, cy, skew;
    std::array<double, 8> distortion{};
    bool fisheye;
};
Model modelFor(const CameraCalibration &c) {
    Model m;
    m.inverse = transpose(rotation(c.yawDeg, c.pitchDeg, c.rollDeg));
    m.fisheye = c.lens == LensModel::Fisheye;
    if (c.intrinsicCalibrated) {
        m.fx = c.K[0]; m.fy = c.K[4]; m.skew = c.K[1]; m.cx = c.K[2]; m.cy = c.K[5];
        for (int i = 0; i < c.distortionCount; ++i) m.distortion[i] = c.D[i];
    } else {
        m.fx = m.fisheye ? SourceWidth / radians(c.hfovDeg)
                        : SourceWidth / (2 * std::tan(radians(c.hfovDeg) * .5));
        m.fy = m.fx; m.skew = 0; m.cx = SourceWidth * .5; m.cy = SourceHeight * .5;
    }
    return m;
}
// Sparse CPU overlap probes use the same projection as the fragment shader.
bool project(const Model &m, const Ray &world, QPointF &pixel) {
    Ray ray{};
    for (int r = 0; r < 3; ++r)
        for (int c = 0; c < 3; ++c) ray[r] += m.inverse[r * 3 + c] * world[c];
    if (ray[2] <= 1e-6) return false;
    double x = ray[0] / ray[2], y = ray[1] / ray[2];
    const double r2 = x * x + y * y;
    const auto &d = m.distortion;
    if (m.fisheye) {
        const double r = std::sqrt(r2), t = std::atan(r), t2 = t * t;
        const double factor = r > 1e-12
            ? t * (1 + t2 * (d[0] + t2 * (d[1] + t2 * (d[2] + t2 * d[3])))) / r : 1;
        x *= factor; y *= factor;
    } else {
        const double den = 1 + r2 * (d[5] + r2 * (d[6] + r2 * d[7]));
        if (std::abs(den) < 1e-12) return false;
        const double radial = (1 + r2 * (d[0] + r2 * (d[1] + r2 * d[4]))) / den;
        const double xd = x * radial + 2 * d[2] * x * y + d[3] * (r2 + 2 * x * x);
        y = y * radial + d[2] * (r2 + 2 * y * y) + 2 * d[3] * x * y;
        x = xd;
    }
    pixel = QPointF(m.fx * x + m.skew * y + m.cx, m.fy * y + m.cy);
    return std::isfinite(pixel.x()) && std::isfinite(pixel.y()) &&
           pixel.x() >= 12 && pixel.x() < SourceWidth - 13 &&
           pixel.y() >= 12 && pixel.y() < SourceHeight - 13;
}
double luminance(const QImage &image, const QPointF &p) {
    const int x = int(p.x()), y = int(p.y());
    const double tx = p.x() - x, ty = p.y() - y;
    auto gray = [](const uchar *v) { return .299 * v[0] + .587 * v[1] + .114 * v[2]; };
    const uchar *a = image.constScanLine(y) + x * 3;
    const uchar *b = image.constScanLine(y + 1) + x * 3;
    return (1 - ty) * ((1 - tx) * gray(a) + tx * gray(a + 3)) +
           ty * ((1 - tx) * gray(b) + tx * gray(b + 3));
}
bool sameConfiguration(const Configuration &a, const Configuration &b) {
    if (a.exposureBalance != b.exposureBalance || a.freshMs != b.freshMs || a.staleMs != b.staleMs)
        return false;
    for (int i = 0; i < CameraCount; ++i) {
        const auto &x = a.cameras[i]; const auto &y = b.cameras[i];
        if (x.yawDeg != y.yawDeg || x.pitchDeg != y.pitchDeg || x.rollDeg != y.rollDeg ||
            x.hfovDeg != y.hfovDeg || x.lens != y.lens || x.K != y.K || x.D != y.D ||
            x.intrinsicCalibrated != y.intrinsicCalibrated || x.distortionCount != y.distortionCount)
            return false;
    }
    return true;
}
const char *vertexShader = R"GLSL(
attribute vec2 position;
varying vec2 screenUv;
void main() {
    gl_Position = vec4(position, 0.0, 1.0);
    screenUv = vec2(position.x * 0.5 + 0.5, 0.5 - position.y * 0.5);
}
)GLSL";
const char *fragmentCore = R"GLSL(
#ifdef GL_ES
#ifdef GL_FRAGMENT_PRECISION_HIGH
precision highp float;
#else
precision mediump float;
#endif
#endif
varying vec2 screenUv;
uniform mat3 viewRotation;
uniform vec2 viewScale;
// meta = freshness, fisheye selector, intrinsic skew, exposure gain.
vec4 cameraPixel(sampler2D image, mat3 inverseRotation, vec4 k,
                 vec4 d0, vec4 d1, vec4 meta, vec3 world) {
    // A negative freshness disables an unselected stereo eye's geometry too.
    if (meta.x < 0.0) return vec4(0.0);
    vec3 ray = inverseRotation * world;
    if (ray.z <= 0.000001) return vec4(0.0);
    vec2 p = ray.xy / ray.z;
    float r2 = dot(p, p);
    if (meta.y > 0.5) {
        float r = sqrt(r2);
        float theta = atan(r);
        float t2 = theta * theta;
        float td = theta * (1.0 + t2 * (d0.x + t2 * (d0.y + t2 * (d0.z + t2 * d0.w))));
        p *= r > 0.000001 ? td / r : 1.0;
    } else {
        float den = 1.0 + r2 * (d1.y + r2 * (d1.z + r2 * d1.w));
        if (abs(den) < 0.000001) return vec4(0.0);
        float radial = (1.0 + r2 * (d0.x + r2 * (d0.y + r2 * d1.x))) / den;
        p = p * radial + vec2(2.0 * d0.z * p.x * p.y + d0.w * (r2 + 2.0 * p.x * p.x),
                             d0.z * (r2 + 2.0 * p.y * p.y) + 2.0 * d0.w * p.x * p.y);
    }
    vec2 pixel = vec2(k.x * p.x + meta.z * p.y + k.z, k.y * p.y + k.w);
    // Negated positive comparisons reject NaNs as well as out-of-image rays.
    if (!(pixel.x >= 0.0 && pixel.y >= 0.0 && pixel.x < 639.0 && pixel.y < 479.0))
        return vec4(0.0);
    float edge = min(min(pixel.x, 639.0 - pixel.x), min(pixel.y, 479.0 - pixel.y));
    float weight = smoothstep(0.0, 48.0, edge);
    vec3 color = vec3(0.0);
    if (meta.x > 0.0) color = texture2D(image, (pixel + 0.5) / vec2(640.0, 480.0)).rgb;
    // Alpha always carries geometric support, even for missing/stale cameras.
    return vec4(color * (weight * meta.x * meta.w), weight);
}
)GLSL";
QByteArray fragmentShader() {
    QByteArray source(fragmentCore);
    for (int i = 0; i < CameraCount; ++i) {
        const QByteArray n = QByteArray::number(i);
        source += "uniform sampler2D image" + n + ";\nuniform mat3 rotation" + n +
                  ";\nuniform vec4 k" + n + ", d0_" + n + ", d1_" + n + ", meta" + n + ";\n";
    }
    source += "void main() {\nvec3 world = viewRotation * vec3((screenUv * 2.0 - 1.0) * viewScale, 1.0);\nvec4 sum = vec4(0.0);\n";
    // Explicit calls allow ES 2.0's fixed sampler indexing on Mali.
    for (int i = 0; i < CameraCount; ++i) {
        const QByteArray n = QByteArray::number(i);
        source += "sum += cameraPixel(image" + n + ", rotation" + n + ", k" + n +
                  ", d0_" + n + ", d1_" + n + ", meta" + n + ", world);\n";
    }
    source += "gl_FragColor = vec4(sum.a > 0.000001 ? sum.rgb / sum.a : vec3(0.0), 1.0);\n}\n";
    return source;
}
} // namespace

struct PanoramaRenderer::Impl : QOpenGLFunctions {
    struct Locations { int image, rotation, k, d0, d1, meta; };
    struct Probe { QPointF a, b; };
    struct Overlap { int a, b; std::vector<Probe> probes; };
    QOpenGLContext *context = nullptr;
    std::unique_ptr<QOpenGLShaderProgram> program;
    std::array<GLuint, CameraCount> textures{};
    GLuint quad = 0;
    std::array<Locations, CameraCount> locations{};
    int position = -1, viewRotation = -1, viewScale = -1;
    std::array<Model, CameraCount> models{};
    std::array<QImage, CameraCount> images;
    std::array<quint64, CameraCount> sequences{}, keys{}, balanceSequences{}, balanceKeys{};
    std::array<bool, CameraCount> uploaded{};
    std::array<bool, CameraCount> lastBalanceSelected{};
    std::array<double, CameraCount> gains{{1, 1, 1, 1, 1, 1}};
    std::vector<Overlap> overlaps;
    Configuration config;
    bool configured = false;
    qint64 lastBalanceMs = -1;
    quint64 lastBytes = 0, totalBytes = 0;

    void configure(const Configuration &cfg) {
        config = cfg; configured = true;
        gains.fill(1); lastBalanceMs = -1; balanceSequences.fill(0); balanceKeys.fill(0);
        lastBalanceSelected.fill(false);
        overlaps.clear();
        for (int i = 0; i < CameraCount; ++i) models[i] = modelFor(cfg.cameras[i]);
        // Include every overlapping physical direction so either stereo eye
        // retains both side neighbors after fallback. Never balance two eyes
        // within the same stereo module against each other.
        for (int i = 0; i < CameraCount; ++i) for (int j = i + 1; j < CameraCount; ++j) {
            if ((i == 0 && j == 1) || (i == 4 && j == 5)) continue;
            Overlap overlap{i, j, {}};
            const double a = cfg.cameras[i].yawDeg;
            const double b = a + std::remainder(cfg.cameras[j].yawDeg - a, 360.0);
            for (int dy = -3; dy <= 3; ++dy)
                for (int elevation = -20; elevation <= 20; elevation += 10) {
                    const double y = radians((a + b) * .5 + dy * 3), e = radians(elevation);
                    const Ray ray{{std::cos(e) * std::sin(y), -std::sin(e), std::cos(e) * std::cos(y)}};
                    Probe probe;
                    if (project(models[overlap.a], ray, probe.a) && project(models[overlap.b], ray, probe.b))
                        overlap.probes.push_back(probe);
                }
            overlaps.push_back(std::move(overlap));
        }
    }
    void balance(const CaptureSnapshot &snapshot, const std::array<qint64, CameraCount> &ages,
                 const std::array<bool, CameraCount> &selected, qint64 now) {
        if (!config.exposureBalance) { gains.fill(1); return; }
        if (lastBalanceMs >= 0 && now >= lastBalanceMs && now - lastBalanceMs < 100) return;
        bool changed = selected != lastBalanceSelected;
        for (int i = 0; i < CameraCount; ++i)
            changed |= balanceSequences[i] != sequences[i] || balanceKeys[i] != keys[i];
        if (!changed) return;
        lastBalanceMs = now; balanceSequences = sequences; balanceKeys = keys;
        lastBalanceSelected = selected;
        struct Edge { int a, b; double ratio, confidence; };
        std::vector<Edge> edges;
        for (const auto &overlap : overlaps) {
            const int a = overlap.a, b = overlap.b;
            if (!selected[a] || !selected[b] || ages[a] < 0 || ages[b] < 0 || ages[a] > config.freshMs || ages[b] > config.freshMs ||
                std::abs(snapshot.capturedMs[a] - snapshot.capturedMs[b]) > 100) continue;
            double sumA = 0, sumB = 0; int count = 0;
            for (const auto &probe : overlap.probes) {
                const double va = luminance(images[a], probe.a), vb = luminance(images[b], probe.b);
                if (va < 15 || vb < 15 || va > 240 || vb > 240) continue;
                sumA += va; sumB += vb; ++count;
            }
            if (count >= 8) {
                const double confidence = std::min(1.0, count / 24.0) *
                    (1.0 - double(std::max(ages[a], ages[b])) / double(config.freshMs + 1));
                edges.push_back({a, b, std::log(sumB / sumA), confidence});
            }
        }
        if (edges.empty()) return;
        // Small regularized graph solve, anchored around unity rather than any
        // camera's whole-frame mean. Disconnected cameras keep a unity target.
        std::array<double, CameraCount> target{};
        for (int pass = 0; pass < 24; ++pass) {
            std::array<double, CameraCount> sums{}, weights{};
            weights.fill(.05);
            for (const auto &e : edges) {
                sums[e.a] += e.confidence * (target[e.b] + e.ratio);
                sums[e.b] += e.confidence * (target[e.a] - e.ratio);
                weights[e.a] += e.confidence; weights[e.b] += e.confidence;
            }
            for (int i = 0; i < CameraCount; ++i)
                target[i] = .5 * target[i] + .5 * sums[i] / weights[i];
        }
        for (int i = 0; i < CameraCount; ++i) {
            const double requested = std::clamp(std::exp(target[i]), .85, 1.15);
            gains[i] = std::clamp(.92 * gains[i] + .08 * requested, .85, 1.15);
        }
    }
};

PanoramaRenderer::PanoramaRenderer() : d(new Impl) {}
// GL cleanup is explicitly owned by the caller, while its context is current.
PanoramaRenderer::~PanoramaRenderer() = default;
quint64 PanoramaRenderer::uploadBytes() const { return d->lastBytes; }
quint64 PanoramaRenderer::totalUploadBytes() const { return d->totalBytes; }

bool PanoramaRenderer::initialize(QString *error) {
    if (error) error->clear();
    auto *context = QOpenGLContext::currentContext();
    if (!context) return fail(error, QStringLiteral("GPU panorama requires a current OpenGL context"));
    if (d->context) {
        if (d->context == context) return true;
        return fail(error, QStringLiteral("Release GPU panorama in its original context before reinitializing"));
    }
    d->initializeOpenGLFunctions();
    GLint units = 0, vectors = 0;
    d->glGetIntegerv(GL_MAX_TEXTURE_IMAGE_UNITS, &units);
    if (context->isOpenGLES()) d->glGetIntegerv(GL_MAX_FRAGMENT_UNIFORM_VECTORS, &vectors);
    // The desktop enum may be absent in Qt builds using GLES-only headers.
    else { d->glGetIntegerv(0x8B49 /* GL_MAX_FRAGMENT_UNIFORM_COMPONENTS */, &vectors); vectors /= 4; }
    if (units < CameraCount || vectors < 64)
        return fail(error, QString("GPU panorama needs six fragment texture units and 64 uniform vectors (available %1/%2)").arg(units).arg(vectors));
    d->context = context;
    d->program.reset(new QOpenGLShaderProgram);
    if (!d->program->addShaderFromSourceCode(QOpenGLShader::Vertex, vertexShader) ||
        !d->program->addShaderFromSourceCode(QOpenGLShader::Fragment, fragmentShader()) || !d->program->link()) {
        const QString log = d->program->log(); release();
        return fail(error, QStringLiteral("GPU panorama shader compilation/link failed: ") + log);
    }
    d->position = d->program->attributeLocation("position");
    d->viewRotation = d->program->uniformLocation("viewRotation");
    d->viewScale = d->program->uniformLocation("viewScale");
    for (int i = 0; i < CameraCount; ++i) {
        const QByteArray n = QByteArray::number(i);
        d->locations[i] = {d->program->uniformLocation(("image" + n).constData()),
            d->program->uniformLocation(("rotation" + n).constData()), d->program->uniformLocation(("k" + n).constData()),
            d->program->uniformLocation(("d0_" + n).constData()), d->program->uniformLocation(("d1_" + n).constData()),
            d->program->uniformLocation(("meta" + n).constData())};
    }
    const GLfloat quad[] = {-1, -1, 1, -1, -1, 1, 1, 1};
    d->glGenBuffers(1, &d->quad); d->glBindBuffer(GL_ARRAY_BUFFER, d->quad);
    d->glBufferData(GL_ARRAY_BUFFER, sizeof(quad), quad, GL_STATIC_DRAW);
    d->glBindBuffer(GL_ARRAY_BUFFER, 0);
    d->glGenTextures(CameraCount, d->textures.data());
    d->glPixelStorei(GL_UNPACK_ALIGNMENT, 1);
    // Complete black textures before the first snapshot; allocate only once.
    QImage black(SourceWidth, SourceHeight, QImage::Format_RGB888); black.fill(Qt::black);
    for (int i = 0; i < CameraCount; ++i) {
        d->glActiveTexture(GL_TEXTURE0 + i); d->glBindTexture(GL_TEXTURE_2D, d->textures[i]);
        d->glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR);
        d->glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR);
        d->glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE);
        d->glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE);
        d->glTexImage2D(GL_TEXTURE_2D, 0, GL_RGB, SourceWidth, SourceHeight, 0, GL_RGB, GL_UNSIGNED_BYTE, black.constBits());
    }
    d->glActiveTexture(GL_TEXTURE0); d->glPixelStorei(GL_UNPACK_ALIGNMENT, 4);
    const GLenum status = d->glGetError();
    if (status != GL_NO_ERROR) {
        release(); return fail(error, QString("GPU panorama initialization GL error 0x%1").arg(status, 0, 16));
    }
    return true;
}

void PanoramaRenderer::release() {
    if (!d->context || QOpenGLContext::currentContext() != d->context) return;
    d->glDeleteTextures(CameraCount, d->textures.data());
    if (d->quad) d->glDeleteBuffers(1, &d->quad);
    d->textures.fill(0); d->quad = 0; d->program.reset(); d->context = nullptr;
    d->uploaded.fill(false); d->keys.fill(0); d->sequences.fill(0);
    d->images.fill(QImage()); d->configured = false; d->lastBytes = 0; d->totalBytes = 0;
    d->glActiveTexture(GL_TEXTURE0);
}

bool PanoramaRenderer::draw(const CaptureSnapshot &snapshot, const Configuration &configuration,
                           double yawDeg, double pitchDeg, double hfovDeg,
                           float viewportAspect, qint64 nowMs, QString *error) {
    if (error) error->clear();
    d->lastBytes = 0;
    if (!d->context || QOpenGLContext::currentContext() != d->context)
        return fail(error, QStringLiteral("GPU panorama draw requires its initialized context current"));
    if (!std::isfinite(yawDeg) || !std::isfinite(pitchDeg) || !std::isfinite(hfovDeg) ||
        !std::isfinite(viewportAspect) || viewportAspect <= 0 || hfovDeg <= 0 || hfovDeg > 175)
        return fail(error, QStringLiteral("GPU panorama requires finite view angles, 0 < HFOV <= 175 and positive viewport aspect"));
    if (!d->configured || !sameConfiguration(d->config, configuration)) {
        if (!configuration.validate(error)) return false;
        d->configure(configuration);
    }
    std::array<qint64, CameraCount> ages{};
    std::array<double, CameraCount> freshness{};
    ages.fill(-1);
    d->glPixelStorei(GL_UNPACK_ALIGNMENT, 1);
    for (int i = 0; i < CameraCount; ++i) {
        d->glActiveTexture(GL_TEXTURE0 + i); d->glBindTexture(GL_TEXTURE_2D, d->textures[i]);
        const auto &image = snapshot.images[i];
        if (image.isNull() || image.width() != SourceWidth || image.height() != SourceHeight ||
            snapshot.capturedMs[i] > nowMs || snapshot.capturedMs[i] < 0 || nowMs < 0) continue;
        const qint64 age = nowMs - snapshot.capturedMs[i];
        if (age >= configuration.staleMs) continue;
        ages[i] = age;
        freshness[i] = age <= configuration.freshMs ? 1.0 :
            double(configuration.staleMs - age) / double(configuration.staleMs - configuration.freshMs);
        const quint64 key = quint64(image.cacheKey());
        if (!d->uploaded[i] || d->sequences[i] != snapshot.sequences[i] || d->keys[i] != key) {
            d->images[i] = image.format() == QImage::Format_RGB888 ? image : image.convertToFormat(QImage::Format_RGB888);
            const QImage &rgb = d->images[i];
            if (rgb.bytesPerLine() == SourceWidth * 3) {
                d->glTexSubImage2D(GL_TEXTURE_2D, 0, 0, 0, SourceWidth, SourceHeight, GL_RGB, GL_UNSIGNED_BYTE, rgb.constBits());
            } else {
                // ES2 has no unpack row length. This only applies to external
                // RGB888 images with a nonstandard stride, not CaptureSource.
                for (int row = 0; row < SourceHeight; ++row)
                    d->glTexSubImage2D(GL_TEXTURE_2D, 0, 0, row, SourceWidth, 1, GL_RGB, GL_UNSIGNED_BYTE, rgb.constScanLine(row));
            }
            d->lastBytes += quint64(SourceWidth) * SourceHeight * 3;
            d->sequences[i] = snapshot.sequences[i]; d->keys[i] = key; d->uploaded[i] = true;
        }
    }
    d->totalBytes += d->lastBytes;
    const auto selected = selectStereoEyes(freshness);
    d->balance(snapshot, ages, selected, nowMs);
    if (!d->program->bind()) {
        d->glActiveTexture(GL_TEXTURE0); d->glPixelStorei(GL_UNPACK_ALIGNMENT, 4);
        return fail(error, QStringLiteral("Could not bind GPU panorama shader"));
    }
    d->program->setUniformValue(d->viewRotation, qtMatrix(rotation(std::remainder(yawDeg, 360.0), std::remainder(pitchDeg, 360.0))));
    const float tangent = float(std::tan(radians(hfovDeg) * .5));
    d->program->setUniformValue(d->viewScale, QVector2D(tangent, tangent / viewportAspect));
    for (int i = 0; i < CameraCount; ++i) {
        const auto &m = d->models[i]; const auto &u = d->locations[i]; const auto &dist = m.distortion;
        d->program->setUniformValue(u.image, i);
        d->program->setUniformValue(u.rotation, qtMatrix(m.inverse));
        d->program->setUniformValue(u.k, QVector4D(float(m.fx), float(m.fy), float(m.cx), float(m.cy)));
        d->program->setUniformValue(u.d0, QVector4D(float(dist[0]), float(dist[1]), float(dist[2]), float(dist[3])));
        d->program->setUniformValue(u.d1, QVector4D(float(dist[4]), float(dist[5]), float(dist[6]), float(dist[7])));
        d->program->setUniformValue(u.meta, QVector4D(selected[i] ? float(freshness[i]) : -1.f,
            m.fisheye ? 1.f : 0.f, float(m.skew), float(d->gains[i])));
    }
    d->glDisable(GL_BLEND); d->glDisable(GL_DEPTH_TEST); d->glDisable(GL_CULL_FACE);
    d->glBindBuffer(GL_ARRAY_BUFFER, d->quad);
    d->program->enableAttributeArray(d->position);
    d->program->setAttributeBuffer(d->position, GL_FLOAT, 0, 2);
    d->glDrawArrays(GL_TRIANGLE_STRIP, 0, 4);
    d->program->disableAttributeArray(d->position);
    d->glBindBuffer(GL_ARRAY_BUFFER, 0); d->program->release();
    d->glActiveTexture(GL_TEXTURE0); d->glPixelStorei(GL_UNPACK_ALIGNMENT, 4);
    const GLenum status = d->glGetError();
    return status == GL_NO_ERROR || fail(error, QString("GPU panorama draw GL error 0x%1").arg(status, 0, 16));
}

} // namespace surround
