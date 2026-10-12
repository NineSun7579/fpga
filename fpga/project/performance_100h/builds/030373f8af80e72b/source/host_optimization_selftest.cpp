// Standalone, no Qt/board dependencies: clang++ -O3 -std=c++17 this.cpp -o host_optimization_selftest
#include "rgb565_convert.h"
#include "per_camera_capture.h"
#include "capture_pacing.h"
#include <vector>
#include <cstdio>
#include <chrono>
#include <string>

static void baseline(const uint8_t* src, int count, uint8_t* dst) {
    for (int i = 0; i < count; ++i) {
        uint16_t v;
        std::memcpy(&v, src + 2 * i, 2);
        const uint8_t r5 = (v >> 11) & 31, g6 = (v >> 5) & 63, b5 = v & 31;
        dst[3*i] = (r5 << 3) | (r5 >> 2);
        dst[3*i+1] = (g6 << 2) | (g6 >> 4);
        dst[3*i+2] = (b5 << 3) | (b5 >> 2);
    }
}
int main(int argc, char** argv) {
    int checks = 0;
    auto check = [&](bool good, const char* name) {
        ++checks;
        if (!good) { std::fprintf(stderr, "FAIL: %s\n", name); std::exit(1); }
    };
    std::array<double, 6> rates{};
    check(tdm::parseCameraCaptureFps("40,40,30,30,40,40", rates) &&
          rates == std::array<double, 6>{{40,40,30,30,40,40}}, "camera mapping");
    check(tdm::parseCameraCaptureFps(" 10,60,30.5,4e1,40,40 \t", rates), "finite decimal rates");
    for (const char* bad : {"", "40,40,30,30,40", "40,40,30,30,40,40,40", "40,40,30,30,40,40,",
             "40,40,30,30,40,40junk", "40,,30,30,40,40", "nan,40,30,30,40,40", "inf,40,30,30,40,40",
             "9.99,40,30,30,40,40", "60.01,40,30,30,40,40", "0x28,40,30,30,40,40", "1e999,40,30,30,40,40"}) {
        rates.fill(27);
        check(!tdm::parseCameraCaptureFps(bad, rates) && rates == std::array<double,6>{{27,27,27,27,27,27}},
              "invalid list leaves global fallback intact");
    }
    tdm::CapturePacing pacing(40);
    check(pacing.waitNs(0) == 0, "initial capture immediate");
    pacing.delivered(100);
    check(pacing.waitNs(100) == 25000000 && pacing.waitNs(25000100) == 0, "40 fps cap");
    pacing.reset(); check(pacing.waitNs(0) == 0, "resume reset");
    tdm::CapturePacing fractional(30.5); fractional.delivered(0);
    check(fractional.waitNs(0) == 32786886, "fractional cap rounds up");
    tdm::CapturePacing unlimited; unlimited.delivered(100);
    check(unlimited.waitNs(0) == 0, "legacy unlimited cap");
    // Exhaustive colors, unaligned source/destination, SIMD boundaries, odd tails.
    for (int alignment : {0, 1, 3}) {
        std::vector<uint8_t> source(65536 * 2 + 8, 0xCC);
        for (int i = 0; i < 65536; ++i) {
            const uint16_t value = uint16_t(i);
            std::memcpy(source.data() + alignment + 2*i, &value, 2);
        }
        for (int count : {0, 1, 7, 8, 9, 15, 16, 17, 639, 640, 641, 65535, 65536}) {
            std::vector<uint8_t> expected(count*3 + 8, 0xA5), actual = expected;
            baseline(source.data()+alignment, count, expected.data()+alignment);
            tdm::rgb565ToRgb888Line(source.data()+alignment, count, actual.data()+alignment);
            check(actual == expected, "byte-exact colors and untouched destination guards");
        }
    }
    // Multiple padded rows: padding must never become a pixel or be overwritten.
    for (int width : {1, 7, 9, 639, 640}) {
        const int srcStride = width*2 + 5, dstStride = width*3 + 7;
        std::vector<uint8_t> src(srcStride*3, 0x69), expected(dstStride*3, 0xA5), actual = expected;
        for (int y = 0; y < 3; ++y) {
            baseline(src.data()+srcStride*y, width, expected.data()+dstStride*y);
            tdm::rgb565ToRgb888Line(src.data()+srcStride*y, width, actual.data()+dstStride*y);
        }
        check(actual == expected, "padded rows");
    }
    std::printf("PASS %d checks; conversion backend=%s\n", checks,
#if defined(__aarch64__)
                "AArch64 NEON"
#else
                "portable"
#endif
    );
    if (argc > 1 && std::string(argv[1]) == "--benchmark") {
        std::vector<uint8_t> src(640*480*2, 0x69), dst(640*480*3);
        for (auto convert : {baseline, tdm::rgb565ToRgb888Line}) {
            std::fill(src.begin(), src.end(), uint8_t(0x69));
            const auto begin = std::chrono::steady_clock::now();
            unsigned checksum = 0;
            for (int n = 0; n < 200; ++n) {
                src[n] = uint8_t(n);
                convert(src.data(), 640*480, dst.data());
                checksum += dst[n];
            }
            const double ms = std::chrono::duration<double, std::milli>(std::chrono::steady_clock::now()-begin).count()/200;
            std::printf("%s 640x480 ms/frame=%.3f checksum=%u\n", convert == baseline ? "baseline" : "candidate", ms, checksum);
        }
    }
}
