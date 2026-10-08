#include "capture_source.h"

#include <QMutexLocker>
#include <QPainter>
#include <QFont>
#include <algorithm>
#include <chrono>
#include <cstdio>
#include <cstring>

#ifdef Q_OS_LINUX
#include <cerrno>
#include <csignal>
#include <fcntl.h>
#include <pthread.h>
#include <sys/file.h>
#include <sys/ioctl.h>
#include <sys/mman.h>
#include <sys/syscall.h>
#include <unistd.h>
#endif

namespace surround {
namespace {
constexpr quint32 allocationBytes = 4u * 1024u * 1024u;
constexpr quint32 frameOffset = 0;
constexpr quint32 scratchOffset = 0x3ff000u;
static_assert(captureFrameBytes + 16 < scratchOffset, "Frame must not overlap metadata");
static_assert(scratchOffset + 16 <= allocationBytes, "Metadata must fit RX allocation");

bool newerTag(quint32 a, quint32 b) {
    return a != b && quint32(a - b) < 0x80000000u;
}

QImage syntheticImage(int camera, quint64 sequence) {
    static const QColor colors[6] = {
        QColor(155, 42, 42), QColor(170, 100, 28), QColor(35, 125, 65),
        QColor(30, 115, 155), QColor(80, 60, 165), QColor(150, 50, 125)};
    static const char* positions[6] = {"FRONT 1", "FRONT 2", "LEFT", "RIGHT", "REAR 1", "REAR 2"};
    QImage image(captureWidth, captureHeight, QImage::Format_RGB888);
    image.fill(colors[camera]);
    QPainter painter(&image);
    painter.setPen(QColor(255, 255, 255, 65));
    for (int x = 0; x < captureWidth; x += 40) painter.drawLine(x, 0, x, captureHeight);
    for (int y = 0; y < captureHeight; y += 40) painter.drawLine(0, y, captureWidth, y);
    painter.fillRect(QRect(int((sequence * 9 + camera * 71) % 560),
                           170 + camera * 25, 80, 55), Qt::white);
    painter.setPen(Qt::white);
    QFont font; font.setPixelSize(30); font.setBold(true); painter.setFont(font);
    painter.drawText(20, 48, QStringLiteral("C%1  %2").arg(camera + 1).arg(positions[camera]));
    font.setPixelSize(20); painter.setFont(font);
    painter.drawText(20, 84, QStringLiteral("SYNTHETIC  frame %1").arg(sequence));
    painter.end();
    return image;
}

#ifdef Q_OS_LINUX
constexpr unsigned long mapCommand = 0xC0000000ul | (4ul << 16) | (0x53ul << 8) | 2;
constexpr unsigned long readCommand = 0xC0000000ul | (4ul << 16) | (0x53ul << 8) | 5;
constexpr quint32 cameraBanks[6][2] = {
    {0x00800000u, 0x00A00000u}, {0x00C00000u, 0x00E00000u},
    {0x01000000u, 0x01200000u}, {0x01400000u, 0x01600000u},
    {0x01800000u, 0x01A00000u}, {0x01C00000u, 0x01E00000u}};

// Exact existing driver's native ABI, including its pointer alignment/padding.
struct DmaOp {
    uint32_t current_len, offset_addr, cmd, ddr3_addr, total_length;
    void* read_buf;
    void* write_buf;
};
static_assert(offsetof(DmaOp, total_length) == 16, "Unexpected driver ABI");
static_assert(offsetof(DmaOp, read_buf) == (sizeof(void*) == 8 ? 24 : 20), "Unexpected pointer alignment");
static_assert(sizeof(DmaOp) == (sizeof(void*) == 8 ? 40 : 28), "Unexpected driver ABI size");

volatile sig_atomic_t alarmWorkerTid = 0;
volatile sig_atomic_t alarmHit = 0;

void captureAlarmHandler(int) {
    const int savedErrno = errno;
    const sig_atomic_t tid = alarmWorkerTid;
    if (tid > 0) {
        // alarm() is process-wide and may land on the GUI thread. Forward it to
        // the worker so the blocking ioctl actually receives EINTR.
        if (::syscall(SYS_gettid) == tid) alarmHit = 1;
        else ::syscall(SYS_tgkill, ::getpid(), tid, SIGALRM);
    }
    errno = savedErrno;
}

class BoardReader {
public:
    ~BoardReader() {
        if (signalInstalled_) {
            ::alarm(0);
            alarmWorkerTid = 0;
            ::sigaction(SIGALRM, &oldAction_, nullptr);
            ::pthread_sigmask(SIG_SETMASK, &oldMask_, nullptr);
        }
        if (rx_) ::munmap(rx_, allocationBytes);
        if (tx_) ::munmap(tx_, allocationBytes);
        if (fd_ >= 0) ::close(fd_);
        if (lease_ >= 0) ::close(lease_);
    }

    bool openDevice() {
        lease_ = ::open("/tmp/surround360_capture.lock", O_CREAT | O_RDWR | O_CLOEXEC | O_NOFOLLOW, 0666);
        if (lease_ < 0 || ::flock(lease_, LOCK_EX | LOCK_NB) != 0) {
            error = QStringLiteral("Cannot acquire /tmp/surround360_capture.lock; another capture may be running.");
            return false;
        }
        struct sigaction action{};
        action.sa_handler = captureAlarmHandler;
        ::sigemptyset(&action.sa_mask);
        if (::sigaction(SIGALRM, &action, &oldAction_) != 0) {
            error = QStringLiteral("Cannot install capture ioctl timeout handler.");
            return false;
        }
        sigset_t unblocked; ::sigemptyset(&unblocked); ::sigaddset(&unblocked, SIGALRM);
        ::pthread_sigmask(SIG_UNBLOCK, &unblocked, &oldMask_);
        alarmWorkerTid = static_cast<sig_atomic_t>(::syscall(SYS_gettid));
        signalInstalled_ = true;
        fd_ = ::open("/dev/pango_pci_driver", O_RDWR | O_SYNC | O_CLOEXEC);
        if (fd_ < 0) {
            error = QStringLiteral("Cannot open /dev/pango_pci_driver: %1").arg(QString::fromLocal8Bit(std::strerror(errno)));
            return false;
        }
        for (quint32 command = 0; command < 2; ++command) {
            DmaOp op{}; op.cmd = command; op.total_length = allocationBytes;
            if (!submit(mapCommand, op, 3)) return false;
        }
        void* tx = ::mmap(nullptr, allocationBytes, PROT_READ | PROT_WRITE, MAP_SHARED, fd_, 0);
        if (tx == MAP_FAILED) { error = QStringLiteral("Cannot mmap TX allocation."); return false; }
        tx_ = static_cast<unsigned char*>(tx);
        void* rx = ::mmap(nullptr, allocationBytes, PROT_READ | PROT_WRITE, MAP_SHARED, fd_, 1024 * 1024);
        if (rx == MAP_FAILED) { error = QStringLiteral("Cannot mmap RX allocation."); return false; }
        rx_ = static_cast<unsigned char*>(rx);
        return true;
    }

    // 1 = owned frame; 0 = unchanged; 2 = unstable commit; -1 = DMA failure.
    int readCamera(int camera, bool delivered, quint32 last, QImage& image,
                   quint32& selected, qint64& capturedMs) {
        quint32 a = 0, b = 0;
        if (!readTag(cameraBanks[camera][0] + captureFrameBytes, a) ||
            !readTag(cameraBanks[camera][1] + captureFrameBytes, b)) return -1;
        const int bank = captureNewestBank(a, b, delivered, last);
        if (bank < 0) return 0;
        selected = bank == 0 ? a : b;
        const quint32 address = cameraBanks[camera][bank];
        DmaOp op{}; op.offset_addr = frameOffset; op.ddr3_addr = address;
        op.total_length = captureFrameBytes + 16;
        if (!submit(readCommand, op, 2)) return -1;
        capturedMs = captureMonotonicMs();
        quint32 after = 0;
        if (!readTag(address + captureFrameBytes, after)) return -1;
        if (!captureValidateFrame(rx_ + frameOffset, op.total_length, selected, after)) return 2;
        // convertToFormat allocates independent RGB888 storage before reuse of RX.
        image = captureRgb565Image(rx_ + frameOffset, captureFrameBytes);
        if (image.isNull()) { error = QStringLiteral("Cannot allocate RGB888 capture frame."); return -1; }
        return 1;
    }

    QString error;
    int consecutiveFailures = 0;

private:
    bool readTag(quint32 address, quint32& tag) {
        DmaOp op{}; op.offset_addr = scratchOffset; op.ddr3_addr = address; op.total_length = 16;
        if (!submit(readCommand, op, 2)) return false;
        std::memcpy(&tag, rx_ + scratchOffset, sizeof(tag));
        return true;
    }
    bool submit(unsigned long command, DmaOp& op, unsigned seconds) {
        alarmHit = 0;
        ::alarm(seconds);
        const int result = ::ioctl(fd_, command, &op);
        const int savedErrno = errno;
        ::alarm(0);
        if (result < 0 || alarmHit) {
            ++consecutiveFailures;
            error = alarmHit ? QStringLiteral("Pango DMA ioctl timeout.") :
                QStringLiteral("Pango DMA ioctl failed: %1").arg(QString::fromLocal8Bit(std::strerror(savedErrno)));
            return false;
        }
        consecutiveFailures = 0;
        return true;
    }
    int fd_ = -1, lease_ = -1;
    unsigned char* tx_ = nullptr;
    unsigned char* rx_ = nullptr;
    bool signalInstalled_ = false;
    struct sigaction oldAction_{};
    sigset_t oldMask_{};
};
#endif
} // namespace

qint64 captureMonotonicMs() {
    return std::chrono::duration_cast<std::chrono::milliseconds>(
        std::chrono::steady_clock::now().time_since_epoch()).count();
}

int captureNewestBank(quint32 a, quint32 b, bool delivered, quint32 last) {
    const int bank = newerTag(a, b) ? 0 : 1;
    const quint32 selected = bank == 0 ? a : b;
    if ((!delivered && a == 0 && b == 0) || (delivered && !newerTag(selected, last))) return -1;
    return bank;
}

bool captureValidateFrame(const void* packet, std::size_t bytes,
                          quint32 selectedTag, quint32 tagAfterRead) {
    if (!packet || bytes < captureFrameBytes + 16) return false;
    quint32 embedded = 0;
    std::memcpy(&embedded, static_cast<const unsigned char*>(packet) + captureFrameBytes, sizeof(embedded));
    return embedded == selectedTag && tagAfterRead == selectedTag;
}

QImage captureRgb565Image(const void* pixels, std::size_t bytes) {
    if (!pixels || bytes < captureFrameBytes) return {};
    const QImage wrapped(static_cast<const uchar*>(pixels), captureWidth, captureHeight,
                         captureWidth * 2, QImage::Format_RGB16);
    return wrapped.convertToFormat(QImage::Format_RGB888);
}

CaptureSource::CaptureSource(bool synthetic, QObject* parent)
    : QThread(parent), synthetic_(synthetic) {}

CaptureSource::~CaptureSource() { stop(); }

CaptureSnapshot CaptureSource::snapshot() const {
    QMutexLocker lock(&mutex_);
    return latest_;
}

void CaptureSource::stop() {
    requestInterruption();
    if (QThread::currentThread() != this) wait();
}

void CaptureSource::setError(const QString& error) {
    QMutexLocker lock(&mutex_);
    latest_.error = error;
    latest_.producedMs = captureMonotonicMs();
    std::fprintf(stderr, "[capture] %s\n", qPrintable(error));
}

void CaptureSource::run() {
    {
        QMutexLocker lock(&mutex_);
        latest_ = CaptureSnapshot{};
    }
#ifdef Q_OS_LINUX
    BoardReader board;
    if (!synthetic_ && !board.openDevice()) { setError(board.error); return; }
#else
    if (!synthetic_) { setError(QStringLiteral("Board capture requires Linux; use synthetic mode on this host.")); return; }
#endif
    std::array<quint32, 6> lastTags{};
    std::array<bool, 6> delivered{};
    std::array<quint64, 6> counts{}, intervalCounts{};
    std::array<quint64, 6> errors{};
    qint64 intervalStart = captureMonotonicMs();
    int failedAttempts = 0;
    while (!isInterruptionRequested()) {
        const qint64 roundStart = captureMonotonicMs();
        for (int camera = 0; camera < captureCameraCount && !isInterruptionRequested(); ++camera) {
            QImage image;
            quint32 tag = 0;
            qint64 captured = 0;
            int result = 1;
            if (synthetic_) {
                image = syntheticImage(camera, counts[camera] + 1);
                tag = static_cast<quint32>(counts[camera] + 1);
                captured = captureMonotonicMs();
            } else {
#ifdef Q_OS_LINUX
                result = board.readCamera(camera, delivered[camera], lastTags[camera], image, tag, captured);
                if (result < 0) {
                    ++failedAttempts;
                    std::fprintf(stderr, "[capture] C%d %s\n", camera + 1, qPrintable(board.error));
                } else failedAttempts = 0;
#endif
            }
            if (result < 0 || result == 2) ++errors[camera];
            if (result == 1) {
                delivered[camera] = true;
                lastTags[camera] = tag;
                ++counts[camera]; ++intervalCounts[camera];
            }
            {
                QMutexLocker lock(&mutex_);
                latest_.errors[camera] = errors[camera];
                if (result == 1) {
                    latest_.images[camera] = image;
                    latest_.capturedMs[camera] = captured;
                    latest_.sequences[camera] = counts[camera];
                    latest_.tags[camera] = tag;
                    latest_.producedMs = captured;
                }
            }
#ifdef Q_OS_LINUX
            if (!synthetic_ && (failedAttempts >= 6 || board.consecutiveFailures >= 6)) {
                setError(QStringLiteral("Capture stopped after six consecutive DMA failures: %1").arg(board.error));
                return;
            }
#endif
        }
        const qint64 now = captureMonotonicMs();
        if (now - intervalStart >= 5000) {
            const double seconds = (now - intervalStart) / 1000.0;
            QMutexLocker lock(&mutex_);
            std::fprintf(stderr, "[capture] %s", synthetic_ ? "synthetic" : "board");
            for (int camera = 0; camera < captureCameraCount; ++camera) {
                latest_.fps[camera] = intervalCounts[camera] / seconds;
                std::fprintf(stderr, " C%d=%.1ffps/tag%u/n%llu/err%llu", camera + 1,
                    latest_.fps[camera], unsigned(lastTags[camera]),
                    static_cast<unsigned long long>(counts[camera]),
                    static_cast<unsigned long long>(errors[camera]));
            }
            std::fprintf(stderr, "\n");
            intervalCounts.fill(0); intervalStart = now;
        }
        // One complete round per 34 ms (board) / 40 ms (synthetic). No catch-up
        // bursts if DMA was slow; camera six always gets a turn before sleeping.
        const qint64 deadline = roundStart + (synthetic_ ? 40 : 34);
        while (!isInterruptionRequested()) {
            const qint64 remaining = deadline - captureMonotonicMs();
            if (remaining <= 0) break;
            QThread::msleep(static_cast<unsigned long>(std::min<qint64>(5, remaining)));
        }
    }
}

} // namespace surround
