#pragma once
#ifndef __linux__
#error Linux POSIX adapter requires Linux; transport.hpp is portable for shim tests.
#endif
#include "transport.hpp"
#include <cerrno>
#include <filesystem>
#include <fstream>
#include <functional>
#include <future>
#include <thread>
#include <sstream>
#include <sys/file.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <sys/sysmacros.h>
#include <fcntl.h>
#include <unistd.h>

namespace cooperative_linux {
// Integration must supply an audited bounded ioctl executor. It must invoke the
// callable at most once, synchronously finish OR preserve its outstanding state,
// return errno on interruption/deadline, and never restart EINTR. No global alarm.
// A hung worker must remain alive with pinned fd/maps; killing it is not retirement.
class DeadlineExecutor {
public:
    virtual ~DeadlineExecutor() = default;
    virtual int run(std::function<int()> syscall, Clock::time_point deadline) = 0;
};
// A timed-out ioctl worker continues; its argument and pinned owner survive.
// This bounds the caller's wait without pretending to cancel kernel/FPGA work.
class WorkerDeadlineExecutor final : public DeadlineExecutor {
public:
    int run(std::function<int()> syscall, Clock::time_point deadline) override {
        if (Clock::now() >= deadline) return ETIMEDOUT;
        std::packaged_task<int()> task(std::move(syscall));
        auto future = task.get_future();
        std::thread worker(std::move(task));
        if (future.wait_until(deadline) != std::future_status::ready) {
            worker.detach(); return ETIMEDOUT;
        }
        worker.join();
        try { return future.get(); } catch (...) { return EIO; }
    }
};
class LinuxSyscalls final : public Syscalls {
    std::shared_ptr<DeadlineExecutor> executor_;
public:
    explicit LinuxSyscalls(std::shared_ptr<DeadlineExecutor> executor =
            std::make_shared<WorkerDeadlineExecutor>())
        : executor_(std::move(executor)) {}
    int owner_lock(const std::string& path) override {
        if (!executor_) { errno = ENOTSUP; return -1; }
        const int fd = ::open(path.c_str(), O_RDWR|O_CREAT|O_CLOEXEC|O_NOFOLLOW, 0600);
        if (fd < 0) return -1;
        struct stat info{};
        if (::fstat(fd, &info) || !S_ISREG(info.st_mode) || info.st_nlink != 1 ||
            info.st_uid != ::geteuid() || (info.st_mode & 0777) != 0600 ||
            ::flock(fd, LOCK_EX|LOCK_NB)) { ::close(fd); return -1; }
        // flock is associated with this open file description, not a process-wide
        // fcntl lock. Never unlink the stable file: that would create a second lock.
        return fd;
    }
    bool no_device_owners(const std::string& device) override {
        struct stat target{};
        if (::stat(device.c_str(), &target) || !S_ISCHR(target.st_mode)) return false;
        try {
            for (const auto& process : std::filesystem::directory_iterator("/proc")) {
                const auto pid = process.path().filename().string();
                if (pid.empty() || pid.find_first_not_of("0123456789") != std::string::npos) continue;
                // Permission-denied /proc scopes are not proof of absence.
                for (const auto& fd : std::filesystem::directory_iterator(process.path()/"fd")) {
                    struct stat info{};
                    if (::stat(fd.path().c_str(), &info)) {
                        if (errno == ENOENT) continue; // fd disappeared during snapshot
                        return false;
                    }
                    if (S_ISCHR(info.st_mode) && info.st_rdev == target.st_rdev) return false;
                }
                std::ifstream maps(process.path()/"maps");
                if (!maps) return false;
                std::string line;
                while (std::getline(maps, line)) {
                    std::istringstream fields(line);
                    std::string range, perms, offset, dev; unsigned long long inode = 0;
                    if (!(fields >> range >> perms >> offset >> dev >> inode)) return false;
                    const auto colon = dev.find(':');
                    if (colon == std::string::npos) return false;
                    const auto maj = std::stoul(dev.substr(0, colon), nullptr, 16);
                    const auto min = std::stoul(dev.substr(colon+1), nullptr, 16);
                    // Maps device field names the filesystem, not character rdev.
                    if (maj == major(target.st_dev) && min == minor(target.st_dev) &&
                        inode == target.st_ino) return false;
                }
                if (maps.bad()) return false;
            }
            return true;
        } catch (...) { return false; }
    }
    int open_device(const std::string& path) override {
        return ::open(path.c_str(), O_RDWR|O_SYNC|O_CLOEXEC|O_NOFOLLOW);
    }
    int ioctl_until(int fd, Command cmd, DMA_OPERATION& op, Clock::time_point deadline) override {
        if (!executor_ || Clock::now() >= deadline) return ETIMEDOUT;
        const auto code = cmd == Command::Map ? PCI_MAP_ADDR_CMD :
            cmd == Command::H2F ? PCI_DMA_READ_CMD : PCI_DMA_WRITE_CMD;
        // Heap argument survives a deadline executor retaining its callable.
        auto argument = std::make_shared<DMA_OPERATION>(op);
        const int result = executor_->run([fd, code, argument]() {
            return ::ioctl(fd, code, argument.get()) == 0 ? 0 : errno;
        }, deadline);
        if (result == 0) op = *argument;
        return result;
    }
    std::uint8_t* map(int fd, bool rx, std::size_t bytes) override {
        void* ptr = ::mmap(nullptr, bytes, PROT_READ|PROT_WRITE, MAP_SHARED, fd,
            static_cast<off_t>(rx ? RX_MMAP_OFFSET : 0));
        return ptr == MAP_FAILED ? nullptr : static_cast<std::uint8_t*>(ptr);
    }
    void unmap(std::uint8_t* ptr, std::size_t bytes) noexcept override { ::munmap(ptr, bytes); }
    void close_fd(int fd) noexcept override { ::close(fd); }
};
}
