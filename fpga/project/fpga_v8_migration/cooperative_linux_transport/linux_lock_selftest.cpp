#include "linux_syscalls.hpp"
#include <sys/wait.h>
#include <iostream>

using namespace cooperative_linux;
// This executor is used only to allow TEMP FILE lock tests. No device open/ioctl.
class TempOnlyExecutor final : public DeadlineExecutor {
public:
    int run(std::function<int()>, Clock::time_point) override { return ENOTSUP; }
};
int main() {
    static_assert(PCI_MAP_ADDR_CMD == 0xc0045302UL, "retained ioctl ABI");
    static_assert(PCI_DMA_READ_CMD == 0xc0045304UL, "retained ioctl ABI");
    static_assert(PCI_DMA_WRITE_CMD == 0xc0045305UL, "retained ioctl ABI");
    static_assert(RX_MMAP_OFFSET == 1048576, "RX mmap selector");
    WorkerDeadlineExecutor executor;
    int calls = 0;
    if (executor.run([&calls] { ++calls; return 0; }, Clock::now()) != ETIMEDOUT || calls) return 9;
    if (executor.run([&calls] { ++calls; return 0; }, Clock::now()+std::chrono::seconds(1)) ||
        calls != 1) return 10;
    auto release = std::make_shared<std::promise<void>>();
    auto gate = release->get_future().share();
    auto finished = std::make_shared<std::promise<void>>();
    auto done = finished->get_future();
    const int timeout = executor.run([gate, finished] {
        gate.wait(); finished->set_value(); return 0;
    }, Clock::now()+std::chrono::milliseconds(20));
    if (timeout != ETIMEDOUT) return 11;
    release->set_value();
    if (done.wait_for(std::chrono::seconds(1)) != std::future_status::ready) return 12;
    char directory[] = "/tmp/cooperative-lock-XXXXXX";
    if (!::mkdtemp(directory)) return 1;
    const std::string path = std::string(directory)+"/physical-domain.lock";
    LinuxSyscalls sys(std::make_shared<TempOnlyExecutor>());
    const int fd = sys.owner_lock(path);
    if (fd < 0) return 2;
    const pid_t child = ::fork();
    if (child < 0) return 3;
    if (child == 0) {
        ::close(fd); // inherited OFD still held by parent
        const int second = sys.owner_lock(path);
        ::_exit(second < 0 ? 0 : 4);
    }
    int status = 0;
    if (::waitpid(child, &status, 0) != child || !WIFEXITED(status) || WEXITSTATUS(status)) return 5;
    sys.close_fd(fd);
    const int next = sys.owner_lock(path);
    if (next < 0) return 6;
    sys.close_fd(next);
    const std::string link = std::string(directory)+"/symlink.lock";
    if (::symlink(path.c_str(), link.c_str()) || sys.owner_lock(link) >= 0) return 7;
    if (::chmod(path.c_str(), 0644) || sys.owner_lock(path) >= 0) return 8;
    ::unlink(link.c_str()); ::unlink(path.c_str()); ::rmdir(directory);
    std::cout << "PASS Linux retained ABI and cross-process flock/0600/NOFOLLOW temp-file tests\n";
}
