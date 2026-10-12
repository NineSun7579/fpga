#pragma once
#include <QByteArray>
#include <QDir>
#include <QFile>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QSaveFile>
#include <array>
#include <atomic>
#include <cstdint>
#include <cstdio>
#include <sys/stat.h>
#include <time.h>
#include <unistd.h>

namespace viewer_acceptance {
constexpr size_t Cameras = 6;
inline uint64_t nowNs() {
    timespec ts{};
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return uint64_t(ts.tv_sec) * 1000000000ULL + uint64_t(ts.tv_nsec);
}

// GUI-thread state. IDs are per-camera cumulative successful deliveries, paired
// with pixels under LatestFrames::mutex, so source/model resets cannot make an
// old texture appear new. Only actually drawn, allocated camera textures stage
// an ID. Upload, mailbox take, exposure repaint and settings are not paints.
class PaintIdentities {
public:
    void beginPaint() { m_pending.fill(0); }
    void drawn(size_t camera, uint64_t id, bool allocated) {
        if (camera < Cameras && allocated && id) m_pending[camera] = id;
    }
    unsigned swapped() {
        unsigned fresh = 0;
        for (size_t c = 0; c < Cameras; ++c) {
            // An older or repeated texture cannot count again.
            if (m_pending[c] > m_committed[c]) {
                m_committed[c] = m_pending[c];
                fresh |= 1u << c;
            }
        }
        m_pending.fill(0);
        return fresh;
    }
private:
    std::array<uint64_t, Cameras> m_pending{}, m_committed{};
};

struct Snapshot {
    uint64_t startedNs = 0, beginNs = 0, endNs = 0;
    uint64_t completed = 0, failed = 0, paintNewFrames = 0;
    std::array<uint64_t, Cameras> paints{}, delivered{}, dmaRequests{}, dmaBytes{}, payloadBytes{}, tagBytes{};
};

// No reset, blocking producer locks, per-event timestamps, pixel work or per-frame
// output. Relaxed atomics give exact cumulative increments. A snapshot brackets
// all independent reads; it does not pretend they occurred at one instant.
class Counters {
public:
    explicit Counters(bool enabled) : m_enabled(enabled), m_startedNs(nowNs()) {}
    bool enabled() const { return m_enabled; }
    void inference(bool success) {
        if (m_enabled) (success ? m_completed : m_failed).fetch_add(1, std::memory_order_relaxed);
    }
    uint64_t delivered(size_t camera) {
        if (!m_enabled || camera >= Cameras) return 0;
        return m_delivered[camera].fetch_add(1, std::memory_order_relaxed) + 1;
    }
    void frameRequest(size_t camera, uint64_t bytes, uint64_t payloadBytes) {
        if (!m_enabled || camera >= Cameras) return;
        m_dmaRequests[camera].fetch_add(1, std::memory_order_relaxed);
        m_dmaBytes[camera].fetch_add(bytes, std::memory_order_relaxed);
        m_payloadBytes[camera].fetch_add(payloadBytes, std::memory_order_relaxed);
    }
    void tagRequest(size_t camera, uint64_t bytes) {
        if (m_enabled && camera < Cameras) m_tagBytes[camera].fetch_add(bytes, std::memory_order_relaxed);
    }
    void swapped(PaintIdentities &ids) {
        const unsigned mask = ids.swapped();
        if (!m_enabled || !mask) return;
        for (size_t c = 0; c < Cameras; ++c)
            if (mask & (1u << c)) m_paints[c].fetch_add(1, std::memory_order_relaxed);
        m_paintNewFrames.fetch_add(1, std::memory_order_relaxed);
    }
    Snapshot snapshot() const {
        Snapshot s;
        s.beginNs = nowNs();
        s.startedNs = m_startedNs;
        s.completed = m_completed.load(std::memory_order_relaxed);
        s.failed = m_failed.load(std::memory_order_relaxed);
        s.paintNewFrames = m_paintNewFrames.load(std::memory_order_relaxed);
        for (size_t c = 0; c < Cameras; ++c) {
            s.paints[c] = m_paints[c].load(std::memory_order_relaxed);
            s.delivered[c] = m_delivered[c].load(std::memory_order_relaxed);
            s.dmaRequests[c] = m_dmaRequests[c].load(std::memory_order_relaxed);
            s.dmaBytes[c] = m_dmaBytes[c].load(std::memory_order_relaxed);
            s.payloadBytes[c] = m_payloadBytes[c].load(std::memory_order_relaxed);
            s.tagBytes[c] = m_tagBytes[c].load(std::memory_order_relaxed);
        }
        s.endNs = nowNs();
        return s;
    }
private:
    const bool m_enabled;
    const uint64_t m_startedNs;
    std::atomic<uint64_t> m_completed{0}, m_failed{0}, m_paintNewFrames{0};
    std::array<std::atomic<uint64_t>, Cameras> m_paints{}, m_delivered{}, m_dmaRequests{},
        m_dmaBytes{}, m_payloadBytes{}, m_tagBytes{};
};

class Reporter : public Counters {
public:
    Reporter() : Counters(qEnvironmentVariableIntValue("DETVIEW_ACCEPTANCE") == 1 ||
                          !qgetenv("DETVIEW_ACCEPTANCE_DIR").isEmpty()) {
        if (enabled()) configureDirectory();
    }
    // Called on the GUI thread, at most once every five seconds. It works when
    // DETVIEW_PERF=0 and never requests a paint or sends a signal to the viewer.
    void report() {
        if (!enabled()) return;
        const uint64_t now = nowNs();
        if (m_lastReportNs && now - m_lastReportNs < 5000000000ULL) return;
        m_lastReportNs = now;
        const Snapshot s = snapshot();
        auto number = [](uint64_t n) { return QString::number(qulonglong(n)); };
        auto array = [&](const std::array<uint64_t, Cameras> &values) {
            QJsonArray a; for (uint64_t value : values) a.append(number(value)); return a;
        };
        QJsonObject obj{
            {"schema", 1}, {"pid", int(getpid())},
            {"epoch", QString::number(getpid()) + ":" + number(s.startedNs)},
            {"snapshot", number(++m_serial)}, {"started_ns", number(s.startedNs)}, {"ended_ns", number(s.endNs)},
            {"sample_begin_ns", number(s.beginNs)}, {"sample_end_ns", number(s.endNs)},
            {"sample_span_ns", number(s.endNs - s.beginNs)}, {"counters", "cumulative_no_reset"},
            {"completed", number(s.completed)}, {"failed", number(s.failed)},
            {"paint_new_frames", number(s.paintNewFrames)}, {"per_camera_paints", array(s.paints)},
            {"delivered", array(s.delivered)}, {"dma_frame_requests", array(s.dmaRequests)},
            {"dma_request_bytes", array(s.dmaBytes)}, {"dma_payload_request_bytes", array(s.payloadBytes)},
            {"dma_tag_request_bytes", array(s.tagBytes)},
            {"paint_source", "allocated_camera_texture_draw_then_Qt_frameSwapped"},
            {"scanout_verified", false}, {"sampling", "independent_atomic_reads_bracketed_by_sample_begin_end"}
        };
        const QByteArray json = QJsonDocument(obj).toJson(QJsonDocument::Compact);
        std::fprintf(stderr, "[acceptance] %s\n", json.constData());
        if (!m_directory.isEmpty()) {
            QSaveFile file(m_directory + "/snapshot.json");
            file.setDirectWriteFallback(false);
            if (!file.open(QIODevice::WriteOnly) ||
                !file.setPermissions(QFile::ReadOwner | QFile::WriteOwner) ||
                file.write(json + '\n') != json.size() + 1 || !file.commit()) {
                std::fprintf(stderr, "[acceptance-file] atomic_snapshot_failed; continuing_log_only\n");
                m_directory.clear();
            }
        }
    }
private:
    uint64_t m_lastReportNs = 0, m_serial = 0;
    QString m_directory;
    void configureDirectory() {
        const QString path = qEnvironmentVariable("DETVIEW_ACCEPTANCE_DIR");
        if (path.isEmpty()) return;
        // Parent supplies a unique absolute directory. Never chmod or reuse a
        // shared directory; accept only an owned, non-symlink private 0700 dir.
        const QByteArray encoded = QFile::encodeName(path);
        struct stat st{};
        bool ok = QDir::isAbsolutePath(path);
        if (ok && lstat(encoded.constData(), &st) != 0)
            ok = mkdir(encoded.constData(), 0700) == 0;
        ok = ok && lstat(encoded.constData(), &st) == 0 && S_ISDIR(st.st_mode) &&
             st.st_uid == geteuid() && (st.st_mode & 0777) == 0700;
        if (ok) m_directory = path;
        else std::fprintf(stderr, "[acceptance-file] directory_must_be_owned_private_0700; continuing_log_only\n");
    }
};
} // namespace viewer_acceptance

inline viewer_acceptance::Reporter &viewerAcceptance() {
    static viewer_acceptance::Reporter reporter;
    return reporter;
}
