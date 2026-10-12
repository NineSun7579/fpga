
#include <QMutex>
#include <QElapsedTimer>
#include <QThread>
#include <algorithm>
#include <atomic>
#include <cerrno>
#include <csignal>
#include <cstring>
#include <cstddef>
#include <cstdio>
#include <memory>
#include <fcntl.h>
#include <sys/ioctl.h>
#include <sys/mman.h>
#include <sys/syscall.h>
#include <unistd.h>
#include "camera_dma.h"
#include "fair_dma.h"
#include "fpga_infer_input.h"
#include "scheme2_uapi.h"
#include "scheme2_verify.h"

namespace tdm { void fixtureCopyCameraPixels(void*, const void*, size_t); }
#define copyCameraPixels fixtureCopyCameraPixels
[[noreturn]] static void scheme2Quarantine(const char* reason) {
    fprintf(stderr, "[scheme2] QUARANTINE pid=%d: %s; parent must quiesce hardware\n", int(getpid()), reason);
    fflush(stderr);
    raise(SIGSTOP);
    for (;;) pause();
}

struct Scheme2Transport {
    int fd = -1, sharedFd = -1;
    uint8_t* tx = nullptr;
    uint8_t* rx = nullptr;
    size_t txBytes = 0x1000, rxBytes = scheme2::Window;
    std::shared_ptr<tdm::FairDmaMutex> mutex;
    bool consumerHeld = false;
    ~Scheme2Transport() {
        if (consumerHeld) scheme2Quarantine("transport teardown with active consumer");
        if (sharedFd >= 0) ::close(sharedFd);
        if (tx && tx != MAP_FAILED) munmap(tx, txBytes);
        if (rx && rx != MAP_FAILED) munmap(rx, rxBytes);
        if (fd >= 0) ::close(fd);
    }
};

static const int IMG_W = 640;
static const int IMG_H = 480;
static const size_t FRAME_BYTES = (size_t)IMG_W * IMG_H * 2;
/* 六路相机 DDR 乒乓缓冲（与运行版 camview 6 路版一致）；帧标签在 base + FRAME_BYTES */
static const int CAM_COUNT = 6;
static const int GRID_COLS = 3;
static const int GRID_ROWS = 2;
static const uint32_t CAM_BASE[CAM_COUNT][2] = {
    {0x00800000u, 0x00A00000u}, {0x00C00000u, 0x00E00000u}, {0x01000000u, 0x01200000u},
    {0x01400000u, 0x01600000u}, {0x01800000u, 0x01A00000u}, {0x01C00000u, 0x01E00000u}};
static const uint32_t REG_BASE = 0x20000000u;
static const uint32_t R_ACK = REG_BASE + 0x00;
static const uint32_t R_I2C_ID = REG_BASE + 0x3C;
static const uint32_t R_CAM_EN = REG_BASE + 0x40;
static const uint32_t R_ADDR1 = REG_BASE + 0x80;
static const uint32_t R_ADDR2 = REG_BASE + 0xC0;

static const unsigned long MAP_CMD = 0xC0000000ul | (4ul << 16) | (0x53ul << 8) | 2;
static const unsigned long UNMAP_CMD = 0xC0000000ul | (4ul << 16) | (0x53ul << 8) | 7;
static const unsigned long H2F_CMD = 0xC0000000ul | (4ul << 16) | (0x53ul << 8) | 4;
static const unsigned long F2H_CMD = 0xC0000000ul | (4ul << 16) | (0x53ul << 8) | 5;

static const int MODEL_W = 640;
static const int MODEL_H = 640;
static const float CONF_THRESH = 0.25f;
static const float IOU_THRESH = 0.45f;

static qint64 monotonicMs() {
    timespec stamp{};
    clock_gettime(CLOCK_MONOTONIC, &stamp);
    return stamp.tv_sec * 1000LL + stamp.tv_nsec / 1000000;
}

struct DmaOp {
    uint32_t current_len, offset_addr, cmd, ddr3_addr, total_length;
    void *read_buf, *write_buf;
};
// Legacy ioctl encodes sizeof(int), but copies exactly this 20-byte prefix.
static_assert(offsetof(DmaOp, current_len) == 0 && offsetof(DmaOp, offset_addr) == 4 &&
              offsetof(DmaOp, cmd) == 8 && offsetof(DmaOp, ddr3_addr) == 12 &&
              offsetof(DmaOp, total_length) == 16, "driver 20-byte DMA prefix ABI");

class PangoDev {
public:
    ~PangoDev() { close(); }

    bool openDev() {
        struct sigaction sa{};
        sa.sa_handler = &PangoDev::alarmHandler;
        sigaction(SIGALRM, &sa, nullptr);  // 只装一次，避免每次 ioctl 的 sigaction 开销
        fd_ = ::open("/dev/pango_pci_driver", O_RDWR | O_SYNC);
        if (fd_ < 0) {
            err_ = "open driver failed";
            return false;
        }
        if (scheme2::enabled()) {
            shared_ = std::make_shared<Scheme2Transport>();
            shared_->fd = fd_;
            shared_->mutex = dmaMutex_;
        }
        DmaOp a{};
        a.cmd = 0;
        a.total_length = txWindowBytes();
        if (ioctlTmo(MAP_CMD, &a, 3) != 0) {
            err_ = "map tx failed";
            return failOpen();
        }
        DmaOp b{};
        b.cmd = 1;
        b.total_length = windowBytes();
        if (ioctlTmo(MAP_CMD, &b, 3) != 0) {
            err_ = "map rx failed";
            return failOpen();
        }
        tx_ = (uint8_t *)mmap(nullptr, txWindowBytes(), PROT_READ | PROT_WRITE, MAP_SHARED, fd_, 0);
        rx_ = (uint8_t *)mmap(nullptr, windowBytes(), PROT_READ | PROT_WRITE, MAP_SHARED, fd_,
                              1024 * 1024);
        if (shared_) { shared_->tx = tx_; shared_->rx = rx_; }
        if (tx_ == MAP_FAILED || rx_ == MAP_FAILED) {
            err_ = "mmap failed";
            return false;
        }
        if (shared_) {
            pz_export_rx request{}; request.version = 1;
            shared_->sharedFd = ::ioctl(fd_, PZ_EXPORT_RX, &request);
            if (shared_->sharedFd < 0) { err_ = "8MiB RX DMA-BUF export required"; return false; }
        }
        return true;
    }

    static void alarmHandler(int) { timeoutHit_ = true; }
    static volatile sig_atomic_t timeoutHit_;

    bool regWrite(uint32_t addr, uint32_t val) {
        tdm::FairDmaGuard dmaLock(dmaMutex_.get());
        if (!tx_)
            return false;
        memcpy(tx_, &val, 4);
        DmaOp op{};
        op.offset_addr = 0;
        op.ddr3_addr = addr;
        op.total_length = 16;
        return ioctlTmo(H2F_CMD, &op, 3) == 0;
    }

    bool regRead(uint32_t addr, uint32_t &val) {
        tdm::FairDmaGuard dmaLock(dmaMutex_.get());
        DmaOp op{};
        op.offset_addr = tdm::cameraScratchOffset;
        op.ddr3_addr = addr;
        op.total_length = 16;
        if (ioctlTmo(F2H_CMD, &op, 3) != 0)
            return false;
        memcpy(&val, rx_ + op.offset_addr, 4);
        return true;
    }

    /* 六路采集线程共用一条 DMA 通道与同一对 tx/rx 缓冲，必须串行化。
       单次等待上限取 2s（与 camview 一致）：丢 MSI 时不能让整块卡住几十秒，
       上层线程会保留上一帧并在下一次帧标签变化时重试。 */
    bool ddrRead(uint32_t addr, uint32_t len, void *out) {
        if (len > tdm::cameraAllocationBytes || (!out && len)) return false;
        tdm::FairDmaGuard dmaLock(dmaMutex_.get());
        uint8_t* destination = static_cast<uint8_t*>(out);
        for (uint32_t copied = 0; copied < len;) {
            const uint32_t bytes = std::min(len - copied,
                tdm::cameraAllocationBytes - tdm::cameraScratchOffset);
            DmaOp op{};
            op.offset_addr = tdm::cameraScratchOffset;
            op.ddr3_addr = addr + copied;
            op.total_length = std::max(16u, bytes);
            if (ioctlTmo(F2H_CMD, &op, 2) != 0) return false;
            memcpy(destination + copied, rx_ + op.offset_addr, bytes);
            copied += bytes;
        }
        return true;
    }

    /* 帧标签：FPGA 每写完一帧就把 tag 递增，据此判断乒乓缓冲是否更新（参考 camview） */
    bool readTag(uint32_t addr, uint32_t &val) {
        uint8_t raw[16] = {0};
        if (!ddrRead(addr, sizeof(raw), raw))
            return false;
        memcpy(&val, raw, sizeof(val));
        return true;
    }

    // One worker per camera owns its RX slot until the CPU copy is complete.
    // All DMA submissions remain serialized; metadata uses a separate scratch.
    int cameraRead(int camera, uint32_t ping, uint32_t pong, bool delivered, uint32_t last,
                   void* output, uint32_t& selected, qint64& dmaNs, qint64& copyNs,
                   qint64& capturedMs) {
        if (camera < 0 || camera >= CAM_COUNT) return -1;
        tdm::FairDmaGuard lock(dmaMutex_.get());
        uint32_t a = 0, b = 0;
        if (!cameraTagLocked(ping + FRAME_BYTES, a) || !cameraTagLocked(pong + FRAME_BYTES, b)) return -1;
        const int bank = tdm::newestCameraBank(a, b, delivered, last);
        if (bank < 0) return 0;
        selected = bank == 0 ? a : b;
        DmaOp op{};
        op.offset_addr = tdm::cameraSlotOffset(camera);
        op.ddr3_addr = bank == 0 ? ping : pong;
        op.total_length = FRAME_BYTES + 16;
        QElapsedTimer timer; timer.start();
        if (ioctlTmo(F2H_CMD, &op, 2) != 0) return -1;
        dmaNs = timer.nsecsElapsed();
        capturedMs = monotonicMs();
        const uint8_t* pixels = rx_ + op.offset_addr;
        uint32_t actual = 0;
        memcpy(&actual, pixels + FRAME_BYTES, sizeof(actual));
        if (actual != selected) return 2;
        lock.unlock();
        timer.restart();
        tdm::copyCameraPixels(output, pixels, FRAME_BYTES);
        copyNs = timer.nsecsElapsed();
        return 1;
    }

    int cameraReadFpga(int camera, int generation, int height, bool delivered, uint32_t last,
                       void* output, uint32_t& selected, qint64& dmaNs, qint64& copyNs,
                       qint64& capturedMs, std::shared_ptr<scheme2::Input>& input,
                       scheme2::PrefetchTiming* timing = nullptr) {
        tdm::FairDmaGuard lock(dmaMutex_.get());
        if (!shared_ || shared_->consumerHeld) scheme2Quarantine("admission/transport mismatch");
        constexpr uint32_t base = 0x40020000;
        auto check = [](bool ok, const char* why) { if (!ok) scheme2Quarantine(why); };
        auto read = [&](uint32_t address, uint32_t size, uint32_t offset) {
            DmaOp op{}; op.ddr3_addr = address; op.total_length = size; op.offset_addr = offset;
            check(ioctlTmo(F2H_CMD, &op, 3) == 0, "F2H failed");
            std::atomic_thread_fence(std::memory_order_seq_cst);
        };
        auto reg = [&](uint32_t offset) { uint32_t value = 0;
            check(cameraTagLocked(base + offset, value), "register read failed"); return value; };
        auto write = [&](uint32_t offset, uint32_t value) {
            memset(tx_, 0, 16); memcpy(tx_, &value, 4);
            DmaOp op{}; op.ddr3_addr = base + offset; op.total_length = 16;
            check(ioctlTmo(H2F_CMD, &op, 3) == 0, "register write failed");
        };
        auto poll = [&](bool converted, uint32_t jobs) {
            QElapsedTimer deadline; deadline.start();
            for (;;) {
                const uint32_t status = reg(0x10);
                check(!(status & 0x70), "FPGA error/config/quarantine");
                if (converted ? ((status & 0x7f) == 0x0b && reg(0x90) >= uint32_t(jobs + 1)) :
                    ((status & 0x77) == 3)) return true;
                if (deadline.elapsed() >= 3000) {
                    if (!converted && status == 1 && reg(0x120) == 2) {
                        write(0x20, 0);
                        check((reg(0x10) & 0x7f) == 0 && reg(0x120) == 0,
                              "unpublished hold release failed");
                        write(0xc0, 4); write(0xd0, 0);
                        check(reg(0xc0) == 4 && reg(0xd0) == 0 && reg(0xb0) == 0,
                              "unpublished selector restore failed");
                        return false;
                    }
                    scheme2Quarantine("uncertain FPGA admission/conversion deadline");
                }
                // Admission still owns the converter and its destination. Only
                // disjoint RAW/tag traffic can run while the FPGA drains.
                lock.unlock();
                QThread::msleep(1);
                lock.relock();
            }
        };
        check(reg(0) == 0x444c5632 && (reg(0xa0) & 7) == 7 && reg(0xf0) == 0x3f &&
              reg(0x80) == FRAME_BYTES && (reg(0x10) & 0x77) == 0 && reg(0xb0) == 0 &&
              reg(0xc0) == 4 && reg(0xd0) == 0 && reg(0x120) == 0, "six-camera idle contract mismatch");
        write(0xc0, camera); write(0xd0, 0);
        const uint32_t destination = camera == 4 ? 0x0a000000 : 0x0b000000 + camera * 0x400000;
        check(reg(0x40) == destination && reg(0x60) == scheme2::SquareBytes &&
              reg(0x100) == 0x00800000u + camera * 0x400000u &&
              reg(0x110) == 0x00a00000u + camera * 0x400000u, "mode0 selector readback mismatch");
        // Audit the writable physical camera-bank configuration as the validated host does.
        for (uint32_t c = 0; c < 4; ++c) for (uint32_t offset : {0x80u, 0xc0u}) {
            uint32_t address = 0;
            check(cameraTagLocked(0x20000000 + c * 0x200 + offset, address), "bank audit failed");
            const uint64_t end = uint64_t(address) + 0x200000;
            check(end <= 0x10000000 && (end <= destination || address >= destination + scheme2::SquareBytes),
                  "RGB destination overlaps writable camera bank");
        }
        const uint32_t epoch = reg(0x50);
        if (timing) timing->holdCommand = monotonicMs();
        write(0x20, 1);
        if (!poll(false, 0)) { scheme2::admission().retire(); return 0; }
        const uint32_t source = reg(0x30), sequence = reg(0xe0);
        auto validate = [&] {
            uint32_t tag = 0;
            check((reg(0x10) & 0x77) == 3 && reg(0x30) == source && reg(0x50) == uint32_t(epoch + 1) &&
                  reg(0xe0) == sequence && reg(0xc0) == uint32_t(camera) && reg(0xd0) == 0 &&
                  reg(0xb0) == 0 && reg(0x40) == destination && reg(0x60) == scheme2::SquareBytes &&
                  reg(0x120) == 4 && (source == 0x00800000u + camera * 0x400000u ||
                  source == 0x00a00000u + camera * 0x400000u) &&
                  cameraTagLocked(source + FRAME_BYTES, tag) && tag == sequence,
                  "same-frame lease identity changed");
        };
        validate();
        if (timing) timing->holdValidated = monotonicMs();
        if (delivered && !tdm::newerCameraTag(sequence, last)) {
            write(0x20, 0); write(0xc0, 4); write(0xd0, 0);
            scheme2::admission().retire(); return 0;
        }
        // The frozen source commit tag has passed full identity validation.
        // Keep the hold asserted while conversion overlaps the complete RAW F2H.
        const uint32_t jobs = reg(0x90);
        write(0x20, 3);
        QElapsedTimer timer; timer.start();
        read(source, FRAME_BYTES + 16, tdm::cameraSlotOffset(camera));
        dmaNs = timer.nsecsElapsed(); capturedMs = monotonicMs();
        uint32_t rawTag = 0;
        memcpy(&rawTag, rx_ + tdm::cameraSlotOffset(camera) + FRAME_BYTES, 4);
        check(rawTag == sequence, "RAW commit tag differs from RGB lease");
        poll(true, jobs); validate();
        // RGB destination is now immutable under this sole converter owner.
        // Retire the camera hold before BEGIN and restore converter defaults.
        // Single admission keeps this RGB destination immutable until retirement;
        // camera/scratch DMA may continue outside the reserved host RX slot.
        write(0x20, 0);
        check((reg(0x10) & 7) == 0, "camera release failed");
        write(0xc0, 4); write(0xd0, 0);
        check(reg(0xc0) == 4 && reg(0xd0) == 0 && reg(0x120) == 0 &&
               reg(0x40) == 0x0a000000, "camera defaults restore failed");
        if (timing) timing->release = monotonicMs();
        lock.unlock();
        // RAW F2H and its commit-tag check already completed under the hold.
        // This worker owns its host RX slot until this call returns; register
        // scratch, other cameras and RGB use disjoint slots. Copy the exact
        // captured RAW after verified conversion/release, before publishing or
        // constructing its same-frame golden RGB. Admission remains occupied.
        timer.restart();
        tdm::copyCameraPixels(output, rx_ + tdm::cameraSlotOffset(camera), FRAME_BYTES);
        copyNs = timer.nsecsElapsed();
        input = std::make_shared<scheme2::Input>();
        if (timing) input->timing = *timing;
        input->fd = shared_->sharedFd; input->base = rx_; input->height = height;
        if (scheme2::verify()) input->goldenRgb = scheme2::golden(output, height);
        input->camera = camera; input->sourceGeneration = generation; input->tag = sequence;
        input->epoch = epoch + 1; input->source = source; input->backing = shared_;
        input->uncertain = [] { scheme2Quarantine("consumer unwound without verified completion"); };
        auto transport = shared_;
        auto lease = std::make_shared<pz_lease>();
        auto beganMs = std::make_shared<qint64>(0);
        std::weak_ptr<scheme2::Input> weak = input;
        input->begin = [transport, lease, beganMs, weak, destination, height, camera, sequence, epoch] {
            tdm::FairDmaGuard guard(transport->mutex.get());
            if (transport->consumerHeld) scheme2Quarantine("overlapping synchronous consumer");
            DmaOp op{}; op.ddr3_addr = destination + scheme2::crop(height);
            op.total_length = scheme2::bytes(height); op.offset_addr = scheme2::Offset;
            if (::ioctl(transport->fd, F2H_CMD, &op) != 0) scheme2Quarantine("deferred RGB F2H failed");
            std::atomic_thread_fence(std::memory_order_seq_cst);
            if (scheme2::verify()) {
            auto owner = weak.lock();
            if (!owner) scheme2Quarantine("input owner lost before consumption");
            const auto& goldenRgb = owner->goldenRgb;
            const size_t bad = scheme2::mismatch(goldenRgb.data(), transport->rx + scheme2::Offset, goldenRgb.size());
            if (bad != goldenRgb.size()) {
                fprintf(stderr, "[scheme2-verify-input] FAIL camera=%d tag=%u height=%d byte=%zu expected=%u actual=%u\n",
                    camera + 1, sequence, height, bad, goldenRgb[bad], transport->rx[scheme2::Offset + bad]);
                scheme2Quarantine("same-frame RGB input byte parity failed");
            }
            static std::atomic<unsigned> count{0};
            const unsigned passed = ++count;
            fprintf(stderr, "[scheme2-verify-input] PASS camera=%d tag=%u epoch=%u height=%d bytes=%zu count=%u performance_sample=0\n",
                    camera + 1, sequence, epoch + 1, height, goldenRgb.size(), passed);
            if (passed == scheme2::verifyCount())
                fprintf(stderr, "[scheme2-verify] INPUT_COUNT_REACHED count=%u required=%u output_parity_pending=1 performance_sample=0\n", passed, scheme2::verifyCount());
            }
            lease->version = 1; lease->offset = scheme2::Offset; lease->length = scheme2::SquareBytes;
            if (::ioctl(transport->fd, PZ_BEGIN, lease.get()) != 0 || !lease->token)
                scheme2Quarantine("deferred PZ_BEGIN failed");
            transport->consumerHeld = true; *beganMs = monotonicMs();
        };
        input->end = [transport, lease, beganMs, camera, sequence, epoch, height]() mutable {
            // Priority retirement waits only for the active transport section.
            // No queued userspace transfer can enter the driver's lock first.
            tdm::FairDmaGuard guard(transport->mutex.get(), true);
            if (::ioctl(transport->fd, PZ_END, lease.get()) != 0) scheme2Quarantine("PZ_END failed");
            transport->consumerHeld = false;
            if (!scheme2::verify()) fprintf(stderr, "[scheme2] camera=%d tag=%u epoch=%u height=%d payload_bytes=%u lease_hold_ms=%lld\n",
                    camera + 1, sequence, epoch + 1, height, scheme2::bytes(height),
                    static_cast<long long>(monotonicMs() - *beganMs));
        };
        selected = sequence;
        return 1;
    }

    const char *lastErr() const { return err_; }

private:
    bool failOpen() {
        if (!shared_) return false;
        // MAP performs allocation only: no H2F/F2H or consumer has started.
        // Explicit UNMAP confirms the driver is idle and frees any earlier MAP.
        DmaOp release{}; release.cmd = 3;
        if (ioctlTmo(UNMAP_CMD, &release, 3) != 0)
            scheme2Quarantine("preflight UNMAP could not confirm idle cleanup");
        fprintf(stderr, "[scheme2-preflight] FATAL %s; tx_bytes=%u rx_bytes=%u; idle UNMAP confirmed, quitting; allocation failure: inspect CMA free/fragmentation and DMA mask (no DMA submitted)\n",
                err_, txWindowBytes(), windowBytes());
        fflush(stderr);
        close();
        return false;
    }
    bool cameraTagLocked(uint32_t address, uint32_t& tag) {
        DmaOp op{};
        op.offset_addr = tdm::cameraScratchOffset;
        op.ddr3_addr = address;
        op.total_length = 16;
        if (ioctlTmo(F2H_CMD, &op, 2) != 0) return false;
        memcpy(&tag, rx_ + op.offset_addr, sizeof(tag));
        return true;
    }
    int ioctlTmo(unsigned long cmd, DmaOp *op, unsigned sec) {
        timeoutHit_ = false;
        struct timespec ts0{}, ts1{};
        clock_gettime(CLOCK_MONOTONIC, &ts0);
        alarm(sec);
        int r = ::ioctl(fd_, cmd, op);
        const int ioctlErrno = errno;
        alarm(0);
        clock_gettime(CLOCK_MONOTONIC, &ts1);
        const double ms = (ts1.tv_sec - ts0.tv_sec) * 1000.0 +
                          (ts1.tv_nsec - ts0.tv_nsec) / 1e6;
        if (r < 0 || timeoutHit_ || ms >= 30.0) {
            fprintf(stderr, "[diag] t=%lld.%03ld pango_ioctl tid=%ld cmd=%lx selector=%u offset=0x%08x addr=0x%08x len=%u ms=%.3f rc=%d errno=%d (%s) alarm=%d\n",
                    (long long)ts1.tv_sec, ts1.tv_nsec / 1000000, long(syscall(SYS_gettid)), cmd,
                    op ? op->cmd : 0, op ? op->offset_addr : 0,
                    op ? op->ddr3_addr : 0, op ? op->total_length : 0,
                    ms, r, r < 0 ? ioctlErrno : 0, r < 0 ? strerror(ioctlErrno) : "success", (int)timeoutHit_);
            fflush(stderr);
        }
        if (timeoutHit_) {
            err_ = "ioctl timeout";
            if (!shared_ || (cmd != MAP_CMD && cmd != UNMAP_CMD)) noteFailure();
            return -1;
        }
        if (r < 0) {
            if (!shared_ || (cmd != MAP_CMD && cmd != UNMAP_CMD)) noteFailure();
            return r;
        }
        failures_ = 0;
        return r;
    }
    /* 连续失败自愈：驱动的 pango_cdev_open 每次打开设备都会把 g_dma_flag 等状态清零，
       所以"退出进程 + 重新打开"本身就等于恢复，不需要 rmmod/insmod。连续失败到阈值就
       主动退出（硬退出，避免卡住的线程拖延），交给守护脚本 run_detview.sh 重启。 */
    void noteFailure() {
        if (scheme2::enabled()) scheme2Quarantine("DMA ioctl failed; automatic reopen prohibited");
        const int n = ++failures_;
        if (n < kRecoverAfterFailures)
            return;
        fprintf(stderr, "[recover] %d consecutive pango ioctl failures -> exit(3) for supervisor restart\n", n);
        fflush(stderr);
        ::_exit(3);
    }
    void close() {
        if (shared_) shared_.reset();
        else if (fd_ >= 0)
            ::close(fd_);
        fd_ = -1;
    }
    const char *err_ = "ok";
    int fd_ = -1;
    uint8_t *tx_ = nullptr;
    uint8_t *rx_ = nullptr;
    std::shared_ptr<tdm::FairDmaMutex> dmaMutex_ = std::make_shared<tdm::FairDmaMutex>();
    std::shared_ptr<Scheme2Transport> shared_;
    uint32_t windowBytes() const { return scheme2::enabled() ? scheme2::Window : 0x400000; }
    uint32_t txWindowBytes() const { return scheme2::enabled() ? 0x1000 : 0x400000; }
    static const int kRecoverAfterFailures = 6;   // 连续失败几次就退出，让守护脚本重启
    std::atomic<int> failures_{0};
};

volatile sig_atomic_t PangoDev::timeoutHit_ = 0;


#include "scheme2_protocol_test_body.h"
