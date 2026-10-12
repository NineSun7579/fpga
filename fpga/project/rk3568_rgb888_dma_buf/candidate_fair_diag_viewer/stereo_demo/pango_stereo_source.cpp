#include "pango_stereo_source.h"
#include "stereo_pairing.h"

#include <algorithm>
#include <cerrno>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <stdexcept>
#include <string>
#include <utility>
#include <fcntl.h>
#include <sys/file.h>
#include <sys/ioctl.h>
#include <sys/mman.h>
#include <unistd.h>

namespace stereo {
namespace {
constexpr uint32_t width = 640;
constexpr uint32_t height = 480;
constexpr uint32_t frameBytes = width * height * 2;
constexpr size_t allocationBytes = 4 * 1024 * 1024;
constexpr off_t rxOffset = 1024 * 1024;
constexpr unsigned long mapCommand = 0xC0045302UL;
constexpr unsigned long fpgaToHostCommand = 0xC0045305UL;
constexpr uint32_t bases[6][2] = {
    {0x00800000, 0x00A00000}, {0x00C00000, 0x00E00000},
    {0x01000000, 0x01200000}, {0x01400000, 0x01600000},
    {0x01800000, 0x01A00000}, {0x01C00000, 0x01E00000}
};

// Matches the deployed driver's DMA_OPERATION header and pointer alignment.
struct DmaOperation {
    uint32_t currentLength = 0, offset = 0, command = 0, address = 0, length = 0;
    void* readBuffer = nullptr;
    void* writeBuffer = nullptr;
};

std::runtime_error systemError(const std::string& operation) {
    return std::runtime_error(operation + ": " + std::strerror(errno));
}

// Opening the deployed driver resets global state. Check handles AND mappings
// before opening; flock alone cannot exclude legacy detview, which does not flock.
void checkDeviceUsers() {
    namespace fs = std::filesystem;
    const std::string self = std::to_string(::getpid());
    for (const auto& process : fs::directory_iterator("/proc")) {
        const std::string pid = process.path().filename().string();
        if (pid == self || pid.empty() || pid.find_first_not_of("0123456789") != std::string::npos)
            continue;
        std::error_code error;
        fs::directory_iterator handles(process.path() / "fd", error);
        if (error == std::errc::permission_denied)
            throw std::runtime_error("Cannot inspect device users; run the live demo as root");
        if (!error) {
            for (const auto& handle : handles) {
                const auto target = fs::read_symlink(handle.path(), error).string();
                if (!error && target.find("/dev/pango_pci_driver") != std::string::npos)
                    throw std::runtime_error("PCIe device already used by PID " + pid +
                                             "; stop acquisition and its supervisor first");
            }
        }
        std::ifstream maps(process.path() / "maps");
        std::string line;
        while (std::getline(maps, line)) {
            if (line.find("/dev/pango_pci_driver") != std::string::npos)
                throw std::runtime_error("PCIe DMA mapping still used by PID " + pid);
        }
    }
}

bool newer(uint32_t a, uint32_t b) {
    return a != b && uint32_t(a - b) < 0x80000000U;
}

double milliseconds(std::chrono::steady_clock::duration duration) {
    return std::chrono::duration<double, std::milli>(duration).count();
}
} // namespace

PangoStereoSource::PangoStereoSource(int leftCamera, int rightCamera, std::optional<int32_t> tagOffset)
    : tagOffset_(tagOffset) {
    if (leftCamera < 1 || leftCamera > 6 || rightCamera < 1 || rightCamera > 6 || leftCamera == rightCamera)
        throw std::invalid_argument("Select two distinct camera IDs in 1..6");
    if (::geteuid() != 0)
        throw std::runtime_error("The FPGA live source requires root to check existing device users");
    left_.camera = leftCamera;
    right_.camera = rightCamera;
    try {
        // Serialize cooperating demos BEFORE open(), which resets global driver state.
        lockFd_ = ::open("/run/lock/detview-pango-stereo.lock", O_CREAT | O_RDWR | O_CLOEXEC | O_NOFOLLOW, 0600);
        if (lockFd_ < 0) throw systemError("open stereo device lock");
        if (::flock(lockFd_, LOCK_EX | LOCK_NB) < 0) throw systemError("another stereo demo owns PCIe device");
        checkDeviceUsers();
        fd_ = ::open("/dev/pango_pci_driver", O_RDWR | O_SYNC | O_CLOEXEC);
        if (fd_ < 0) throw systemError("open PCIe driver");
        DmaOperation allocation;
        allocation.command = 1;
        allocation.length = allocationBytes;
        if (::ioctl(fd_, mapCommand, &allocation) < 0) throw systemError("allocate RX DMA buffer");
        void* mapping = ::mmap(nullptr, allocationBytes, PROT_READ | PROT_WRITE, MAP_SHARED, fd_, rxOffset);
        if (mapping == MAP_FAILED) throw systemError("map RX DMA buffer");
        rx_ = static_cast<uint8_t*>(mapping);
    } catch (...) {
        close();
        throw;
    }
}

PangoStereoSource::~PangoStereoSource() { close(); }

void PangoStereoSource::close() {
    if (rx_) {
        ::munmap(rx_, allocationBytes);
        rx_ = nullptr;
    }
    // The deployed release() owns coherent-buffer cleanup. Do not issue UMAP
    // after a timeout or clear the driver's ownership flag and retry a DMA.
    if (fd_ >= 0) {
        ::close(fd_);
        fd_ = -1;
    }
    if (lockFd_ >= 0) {
        ::close(lockFd_);
        lockFd_ = -1;
    }
}

void PangoStereoSource::read(uint32_t address, uint32_t length, void* destination) {
    if (faulted_) throw std::runtime_error("DMA source stopped after its first failure");
    DmaOperation operation;
    operation.address = address;
    operation.length = length;
    if (::ioctl(fd_, fpgaToHostCommand, &operation) < 0) {
        faulted_ = true;
        throw systemError("DMA read; source stopped, verify device recovery before restarting");
    }
    std::memcpy(destination, rx_, length);
}

void PangoStereoSource::tags(CameraState& state) {
    for (int slot = 0; slot < 2; ++slot) {
        uint32_t tag[4] = {};
        read(bases[state.camera - 1][slot] + frameBytes, sizeof(tag), tag);
        state.tags[slot] = tag[0];
    }
}

int PangoStereoSource::newestSlot(const CameraState& state) const {
    const bool a = state.tags[0] != state.previous[0];
    const bool b = state.tags[1] != state.previous[1];
    if (!a && !b) return -1;
    if (!a) return 1;
    if (!b) return 0;
    return newer(state.tags[1], state.tags[0]) ? 1 : 0;
}

bool PangoStereoSource::frame(CameraState& state, int slot, cv::Mat& image) {
    cv::Mat raw(height, width, CV_16UC1);
    read(bases[state.camera - 1][slot], frameBytes, raw.data);
    uint32_t tag[4] = {};
    read(bases[state.camera - 1][slot] + frameBytes, sizeof(tag), tag);
    if (tag[0] != state.tags[slot]) return false;
    // Explicit conversion matches detview's packed R5:G6:B5 interpretation.
    image.create(height, width, CV_8UC3);
    for (int y = 0; y < int(height); ++y) {
        const auto* row = raw.ptr<uint16_t>(y);
        auto* out = image.ptr<cv::Vec3b>(y);
        for (int x = 0; x < int(width); ++x) {
            const uint16_t pixel = row[x];
            const uint8_t r = (pixel >> 11) & 31, g = (pixel >> 5) & 63, b = pixel & 31;
            out[x] = cv::Vec3b((b << 3) | (b >> 2), (g << 2) | (g >> 4), (r << 3) | (r >> 2));
        }
    }
    return true;
}

bool PangoStereoSource::poll(StereoPair& pair) {
    const auto start = std::chrono::steady_clock::now();
    if (start < nextPoll_) return false;
    nextPoll_ = start + std::chrono::milliseconds(20);
    tags(left_);
    tags(right_);
    if (!left_.primed || !right_.primed) {
        for (auto* camera : {&left_, &right_}) {
            std::copy(camera->tags, camera->tags + 2, camera->previous);
            camera->primed = true;
        }
        return false;
    }
    int leftSlot = newestSlot(left_), rightSlot = newestSlot(right_);
    if (tagOffset_) {
        // Explicit common-counter relation, modulo uint32 wrap. Never infer it
        // from equal-looking independent counters or host DMA timestamps.
        const auto slots = correspondingSlots({left_.tags[0], left_.tags[1]},
            {left_.previous[0], left_.previous[1]}, {right_.tags[0], right_.tags[1]},
            {right_.previous[0], right_.previous[1]}, *tagOffset_);
        leftSlot = slots.left;
        rightSlot = slots.right;
    }
    if (leftSlot < 0 || rightSlot < 0) return false;
    StereoPair candidate;
    if (!frame(left_, leftSlot, candidate.left)) return false;
    const auto leftDone = std::chrono::steady_clock::now();
    if (!frame(right_, rightSlot, candidate.right)) return false;
    const auto rightDone = std::chrono::steady_clock::now();
    // Recheck both slots after the pair read, avoiding a changed frame tag.
    uint32_t check[4] = {};
    read(bases[left_.camera - 1][leftSlot] + frameBytes, sizeof(check), check);
    if (check[0] != left_.tags[leftSlot]) return false;
    read(bases[right_.camera - 1][rightSlot] + frameBytes, sizeof(check), check);
    if (check[0] != right_.tags[rightSlot]) return false;
    candidate.leftTag = left_.tags[leftSlot];
    candidate.rightTag = right_.tags[rightSlot];
    candidate.hostReadGapMs = milliseconds(rightDone - leftDone);
    candidate.acquisitionMs = milliseconds(std::chrono::steady_clock::now() - start);
    for (auto* camera : {&left_, &right_})
        std::copy(camera->tags, camera->tags + 2, camera->previous);
    pair = std::move(candidate);
    return true;
}
} // namespace stereo
