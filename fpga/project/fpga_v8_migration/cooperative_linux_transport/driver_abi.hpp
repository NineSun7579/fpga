#pragma once
#include <cstddef>
#include <cstdint>
#include <type_traits>
#ifdef __linux__
#include <sys/ioctl.h>
#endif

namespace cooperative_linux {
// Userspace projection of retained 001_pango_pci_driver.h:223-239.
// Natural alignment is intentional: old packed forward declarations are WRONG.
struct DMA_DATA { void* read_buf; void* write_buf; };
struct DMA_OPERATION {
    unsigned int current_len, offset_addr, cmd, ddr3_addr, total_length;
    DMA_DATA data;
};
static_assert(sizeof(void*) == 8 && sizeof(unsigned int) == 4, "64-bit ABI required");
static_assert(std::is_standard_layout<DMA_OPERATION>::value, "ABI layout");
static_assert(offsetof(DMA_OPERATION, current_len) == 0, "ABI");
static_assert(offsetof(DMA_OPERATION, offset_addr) == 4, "ABI");
static_assert(offsetof(DMA_OPERATION, cmd) == 8, "ABI");
static_assert(offsetof(DMA_OPERATION, ddr3_addr) == 12, "ABI");
static_assert(offsetof(DMA_OPERATION, total_length) == 16, "ABI");
static_assert(offsetof(DMA_OPERATION, data) == 24 && sizeof(DMA_OPERATION) == 40, "ABI");
static_assert(sizeof(DMA_DATA) == 16 && offsetof(DMA_DATA, write_buf) == 8, "ABI");
#ifdef __linux__
// Exact retained header macro expressions; ioctl size is int, NOT DMA_OPERATION.
inline constexpr auto PCI_MAP_ADDR_CMD = _IOWR('S', 2, int);
inline constexpr auto PCI_DMA_READ_CMD = _IOWR('S', 4, int); // H2F
inline constexpr auto PCI_DMA_WRITE_CMD = _IOWR('S', 5, int); // F2H
inline constexpr std::uint64_t RX_MMAP_OFFSET = 1 * 1024 * 1024UL;
#endif
enum class Command { Map, H2F, F2H }; // Shim trace; Linux translates via macros above.
}
