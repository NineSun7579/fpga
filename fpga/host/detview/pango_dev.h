// pango_dev.h -- PCIe DMA device abstraction for the Pango FPGA driver.
// Extracted verbatim in spirit from host/camview/main.cpp (39.8fps-proven):
//   open /dev/pango_pci_driver -> ioctl MAP x2 -> mmap tx/rx windows
//   H2F (op 4) = host->FPGA write, F2H (op 5) = FPGA->host read
// Every ioctl is wrapped in a SIGALRM watchdog: the M01 register window can
// wedge and an ioctl would otherwise never return.
#ifndef PANGO_DEV_H
#define PANGO_DEV_H

#include <cstdio>
#include <cstring>
#include <cstdint>
#include <fcntl.h>
#include <unistd.h>
#include <sys/ioctl.h>
#include <sys/mman.h>
#include <csignal>
#include <cerrno>

struct DmaOp {
    uint32_t current_len, offset_addr, cmd, ddr3_addr, total_length;
    void *read_buf, *write_buf;
};
static const unsigned long MAP_CMD = 0xC0000000u | (4u << 16) | (0x53u << 8) | 2;
static const unsigned long H2F_CMD = 0xC0000000u | (4u << 16) | (0x53u << 8) | 4; // host->FPGA write
static const unsigned long F2H_CMD = 0xC0000000u | (4u << 16) | (0x53u << 8) | 5; // FPGA->host read

class PangoDev {
public:
    bool open() {
        fd_ = ::open("/dev/pango_pci_driver", O_RDWR | O_SYNC);
        if (fd_ < 0) { err_ = "open driver failed"; return false; }
        DmaOp a{}; a.cmd = 0; a.total_length = 4 * 1024 * 1024;
        if (ioctl(fd_, MAP_CMD, &a) < 0) { err_ = "map tx failed"; return false; }
        DmaOp b{}; b.cmd = 1; b.total_length = 4 * 1024 * 1024;
        if (ioctl(fd_, MAP_CMD, &b) < 0) { err_ = "map rx failed"; return false; }
        tx_ = (uint8_t *)mmap(nullptr, 4 * 1024 * 1024, PROT_READ | PROT_WRITE, MAP_SHARED, fd_, 0);
        rx_ = (uint8_t *)mmap(nullptr, 4 * 1024 * 1024, PROT_READ | PROT_WRITE, MAP_SHARED, fd_, 1024 * 1024);
        if (tx_ == MAP_FAILED || rx_ == MAP_FAILED) { err_ = "mmap failed"; return false; }
        return true;
    }

    static void alarmHandler(int) { timeoutHit_ = true; }
    static volatile sig_atomic_t timeoutHit_;

    bool ioctlTmo(int cmd, DmaOp *op, unsigned sec) {
        timeoutHit_ = false;
        struct sigaction sa{}, old{};
        sa.sa_handler = &PangoDev::alarmHandler;
        sigaction(SIGALRM, &sa, &old);
        alarm(sec);
        int r = ioctl(fd_, cmd, op);
        alarm(0);
        sigaction(SIGALRM, &old, nullptr);
        if (timeoutHit_) { err_ = "ioctl timeout"; return false; }
        return r == 0;
    }

    // Register write via the proven 16B DMA path (value in byte0..3, little-endian)
    bool regWrite(uint32_t addr, uint32_t val) {
        memcpy(tx_, &val, 4);
        DmaOp op{}; op.offset_addr = 0; op.ddr3_addr = addr; op.total_length = 16;
        return ioctlTmo(H2F_CMD, &op, 3);
    }
    bool regRead(uint32_t addr, uint32_t &val) {
        DmaOp op{}; op.offset_addr = 0; op.ddr3_addr = addr; op.total_length = 16;
        if (!ioctlTmo(F2H_CMD, &op, 3)) return false;
        memcpy(&val, rx_, 4);
        return true;
    }
    // DDR block read through the M00 data path (the reliable one)
    bool ddrRead(uint32_t addr, uint32_t len, void *out) {
        DmaOp op{}; op.offset_addr = 0; op.ddr3_addr = addr; op.total_length = len;
        if (!ioctlTmo(F2H_CMD, &op, 4)) return false;
        memcpy(out, rx_, len);
        return true;
    }
    const char *lastErr() const { return err_; }

private:
    const char *err_ = "ok";
    int fd_ = -1;
    uint8_t *tx_ = nullptr, *rx_ = nullptr;
};

#endif // PANGO_DEV_H
