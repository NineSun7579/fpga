#include "camera_dma.h"
#include <algorithm>
#include <iostream>
#include <stdexcept>
#include <vector>

namespace tdm {
int runCameraDmaSelfTest() {
    try {
        auto check = [](bool ok, const char* reason) { if (!ok) throw std::runtime_error(reason); };
        check(newestCameraBank(0, 0, false, 0) == -1, "uninitialized counters");
        check(newestCameraBank(101, 100, false, 0) == 0, "newest ping");
        check(newestCameraBank(101, 102, true, 101) == 1, "newest pong");
        check(newestCameraBank(101, 102, true, 102) == -1, "no duplicate frames");
        check(newestCameraBank(UINT32_MAX, 0, true, UINT32_MAX) == 1, "counter wrap to zero");
        check(newestCameraBank(0, 1, true, 0) == 1, "counter after wrap");
        check(newestCameraBank(8, 9, true, 100) == -1, "counter reset requires reprime");
        std::vector<uint8_t> rx(cameraAllocationBytes, 0xaa);
        for (int camera = 0; camera < 6; ++camera) {
            auto* pixels = rx.data() + cameraSlotOffset(camera);
            for (size_t i = 0; i < cameraFrameBytes; ++i) pixels[i] = uint8_t(i * 7 + camera);
            const uint32_t tag = 100 + camera;
            std::memcpy(pixels + cameraFrameBytes, &tag, sizeof(tag));
        }
        std::fill_n(rx.data() + cameraScratchOffset, 16, 0xff);
        for (int camera = 0; camera < 6; ++camera) {
            std::vector<uint8_t> output(cameraFrameBytes + 8, 0xab);
            const auto* pixels = rx.data() + cameraSlotOffset(camera);
            copyCameraPixels(output.data(), pixels, cameraFrameBytes);
            check(std::equal(output.begin(), output.begin() + cameraFrameBytes, pixels), "pixel copy mismatch");
            check(std::all_of(output.begin() + cameraFrameBytes, output.end(), [](uint8_t v) { return v == 0xab; }),
                  "tag bytes escaped into pixel output");
            uint32_t tag = 0;
            std::memcpy(&tag, pixels + cameraFrameBytes, sizeof(tag));
            check(tag == uint32_t(100 + camera), "disjoint slots lost their commit tags");
        }
        for (size_t bytes : {size_t(0), size_t(1), size_t(63), size_t(64), size_t(65), size_t(129)}) {
            std::vector<uint8_t> output(bytes + 4, 0xcc);
            copyCameraPixels(output.data() + 1, rx.data() + 3, bytes);
            check(std::equal(output.begin() + 1, output.begin() + 1 + bytes, rx.data() + 3), "unaligned tail copy");
            check(output.front() == 0xcc && output[bytes + 1] == 0xcc, "copy wrote outside requested bytes");
        }
        std::cout << "CAMERA_DMA_SELFTEST_PASS\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "CAMERA_DMA_SELFTEST_FAIL: " << error.what() << '\n';
        return 1;
    }
}
} // namespace tdm
