// Heap-only exact byte/copy-cost probe. Never opens PCIe, RKNN, camera or viewer.
#include "same_format_copy.h"
#include <dlfcn.h>
#include <algorithm>
#include <array>
#include <cmath>
#include <iomanip>
#include <iostream>
#include <sstream>

using namespace rga_copy;
static std::string quote(const std::string &text) {
    std::ostringstream out; out << '"';
    for (unsigned char c : text) {
        if (c == '"' || c == '\\') out << '\\' << char(c);
        else if (c < 32) out << "\\u" << std::hex << std::setw(4) << std::setfill('0') << unsigned(c);
        else out << char(c);
    }
    out << '"'; return out.str();
}
static void emit(const std::string &json) { std::cout << json << std::endl; }
static std::string timing(Duration d) {
    std::ostringstream out; out << std::setprecision(12) << "{\"wall_ms\":" << d.wall_ms
        << ",\"thread_cpu_ms\":" << d.thread_cpu_ms << '}'; return out.str();
}
static std::string measurement(const Measurement &m) {
    return "{\"total\":" + timing(m.total) + ",\"rga_copy\":" + timing(m.rga_copy) +
           ",\"cpu_begin_read\":" + timing(m.cpu_begin_read) + ",\"snapshot_memcpy\":" + timing(m.snapshot_memcpy) +
           ",\"cpu_end_read\":" + timing(m.cpu_end_read) + ",\"cpu_access_and_snapshot\":" + timing(m.cpu_access_and_snapshot) + '}';
}
static void pattern(std::vector<uint8_t> &out, unsigned kind, unsigned frame) {
    require(out.size() == FrameBytes && kind < 4, "invalid generated pattern");
    for (size_t pixel = 0; pixel < FrameBytes / 2; ++pixel) {
        uint16_t value;
        switch (kind) {
        case 0: value = uint16_t(pixel + frame * 7919); break; // all65536 words every frame
        case 1: value = uint16_t(((pixel / Width + pixel % Width + frame) & 1) ? 0xffff : 0); break;
        case 2: value = uint16_t(((pixel * 13 + frame * 71) & 255) | (((pixel * 29 + frame * 47) & 255) << 8)); break;
        default: value = uint16_t((pixel % Width < (frame * 37) % Width) ? 0x07e0 : (0xf800 ^ frame)); break;
        }
        out[2 * pixel] = uint8_t(value); out[2 * pixel + 1] = uint8_t(value >> 8);
    }
}
static void upload(HeapSlot &source, const std::vector<uint8_t> &bytes) {
    CpuAccess write(source.fd(), DMA_BUF_SYNC_WRITE);
    std::memcpy(source.data(), bytes.data(), FrameBytes); write.finish();
}
static void checkSource(HeapSlot &source, const std::vector<uint8_t> &bytes) {
    CpuAccess read(source.fd(), DMA_BUF_SYNC_READ);
    const bool equal = std::memcmp(source.data(), bytes.data(), FrameBytes) == 0;
    read.finish(); require(equal, "RGA or CPU copy modified source heap bytes");
}
struct Snapshot {
    static constexpr size_t Guard = 32;
    std::vector<uint8_t> storage = std::vector<uint8_t>(FrameBytes + 2 * Guard, 0xa5);
    uint8_t *data() { return storage.data() + Guard; }
    void validate(const std::vector<uint8_t> &expected) {
        require(std::memcmp(data(), expected.data(), FrameBytes) == 0, "full RGB565 snapshot byte mismatch");
        require(std::all_of(storage.begin(), storage.begin() + Guard, [](uint8_t b) { return b == 0xa5; }) &&
                std::all_of(storage.end() - Guard, storage.end(), [](uint8_t b) { return b == 0xa5; }), "snapshot canary overwrite");
    }
};
static Duration cpuCopy(HeapSlot &source, Snapshot &out) {
    const Stamp total;
    CpuAccess read(source.fd(), DMA_BUF_SYNC_READ);
    std::memcpy(out.data(), source.data(), FrameBytes);
    read.finish(); return elapsed(total);
}
struct Options { int frames = 25, rounds = 4, warmup = 3; };
static Options options(int argc, char **argv) {
    Options opt;
    for (int i = 1; i < argc; ++i) {
        const std::string key = argv[i];
        require(i + 1 < argc, "missing option value");
        const std::string value = argv[++i]; size_t used = 0;
        const int number = std::stoi(value, &used); require(used == value.size(), "invalid numeric option");
        if (key == "--frames") opt.frames = number;
        else if (key == "--rounds") opt.rounds = number;
        else if (key == "--warmup") opt.warmup = number;
        else throw std::runtime_error("unknown option: " + key);
    }
    require(opt.frames >= 1 && opt.frames <= 100 && opt.rounds >= 2 && opt.rounds <= 4 && opt.warmup >= 0 && opt.warmup <= 5,
            "bounded quick probe requires frames1..100 rounds2..4 warmup0..5");
    return opt;
}
static void runtime() {
    const char *version = querystring(RGA_ALL); // actual declaration in matching SDK
    Dl_info library{};
    require(dladdr(reinterpret_cast<void *>(&querystring), &library) && library.dli_fname, "cannot resolve actual librga path");
    emit("{\"event\":\"runtime\",\"query_symbol\":\"querystring\",\"library_path\":" + quote(library.dli_fname) +
         ",\"query_all\":" + quote(version ? version : "unavailable") + '}');
#ifdef RGA_API_VERSION
    emit("{\"event\":\"header\",\"RGA_API_VERSION\":" + quote(RGA_API_VERSION) + '}');
#endif
}
int main(int argc, char **argv) {
    bool copySucceeded = false;
    int rgaCompletions = 0, cpuCompletions = 0;
    try {
        const Options opt = options(argc, argv);
        const Stamp wholeProbe;
        auto budget = [&] { require(elapsed(wholeProbe).wall_ms < 8000, "8-second probe budget exceeded; partial evidence only"); };
        emit("{\"event\":\"configuration\",\"scope\":\"cached_system_heap_copy_calibration_only\",\"heap\":" + quote(SystemHeap) +
             ",\"bytes\":614400,\"width\":640,\"height\":480,\"row_bytes\":1280,\"format\":\"RGB565_to_RGB565\","
             "\"PCIe_access\":false,\"NPU_access\":false,\"live_fps_claim\":false,\"cacheability_proven\":false,"
             "\"source_fill_and_validation_timed\":false,\"snapshot_copy_and_sync_timed\":true,\"frames\":" + std::to_string(opt.frames) +
             ",\"rounds\":" + std::to_string(opt.rounds) + ",\"warmup\":" + std::to_string(opt.warmup) + '}');
        runtime();
        HeapSlot source;
        SameFormatCopy rga(source.fd(), source.size());
        emit("{\"event\":\"setup\",\"page_size\":" + std::to_string(source.pageSize()) +
             ",\"destination_page_size\":" + std::to_string(rga.destinationPageSize()) +
             ",\"persistent_imports\":true,\"imcheck_passed\":true,\"source_size\":" + std::to_string(source.size()) + '}');
        std::vector<uint8_t> expected(FrameBytes);
        Snapshot cpu, gpu;
        const std::array<const char *, 4> names{{"all_65536_words", "zero_ff_checkerboard", "changing_byte_ramps", "moving_word_split"}};
        for (unsigned kind = 0; kind < names.size(); ++kind) {
            for (unsigned frame = 0; frame < 3; ++frame) {
                budget(); pattern(expected, kind, frame); upload(source, expected);
                const auto m = rga.copy(gpu.data(), FrameBytes); copySucceeded = true; ++rgaCompletions;
                gpu.validate(expected); checkSource(source, expected);
                emit("{\"event\":\"correctness\",\"pattern\":" + quote(names[kind]) + ",\"frame\":" + std::to_string(frame) +
                     ",\"bytes_compared\":614400,\"exact\":true,\"source_unchanged\":true,\"snapshot_canaries\":true,"
                     "\"all65536_words_present\":" + (kind == 0 ? "true" : "false") + ",\"stages\":" + measurement(m) + '}');
            }
        }
        for (int round = 0; round < opt.rounds; ++round) {
            for (int frame = -opt.warmup; frame < opt.frames; ++frame) {
                budget();
                const unsigned sequence = unsigned(1000 + round * (opt.frames + opt.warmup) + frame + opt.warmup);
                pattern(expected, sequence % names.size(), sequence); upload(source, expected);
                Duration cpuTime; Measurement rgaTime;
                auto runCpu = [&] { cpuTime = cpuCopy(source, cpu); ++cpuCompletions; cpu.validate(expected); };
                auto runRga = [&] { rgaTime = rga.copy(gpu.data(), FrameBytes); copySucceeded = true; ++rgaCompletions; gpu.validate(expected); };
                if (round % 2 == 0) { runCpu(); runRga(); } else { runRga(); runCpu(); }
                checkSource(source, expected); // all comparison/source reads outside measured copy intervals
                if (frame >= 0)
                    emit("{\"event\":\"pair\",\"round\":" + std::to_string(round) + ",\"frame\":" + std::to_string(frame + 1) +
                         ",\"order\":" + quote(round % 2 == 0 ? "cpu_cached_heap_then_rga" : "rga_then_cpu_cached_heap") +
                         ",\"source_sequence\":" + std::to_string(sequence) + ",\"exact\":true,\"bytes_compared_each\":614400,"
                         "\"cpu_cached_heap_copy\":" + timing(cpuTime) + ",\"rga_heap_copy_to_owned_snapshot\":" + measurement(rgaTime) + '}');
            }
        }
        budget();
        emit("{\"event\":\"complete\",\"passed\":true,\"hardware_copy_executed\":true,\"correctness_frames\":12,\"paired_frames\":" +
             std::to_string(opt.frames * opt.rounds) + ",\"rga_completed_including_correctness_and_warmups\":" + std::to_string(rgaCompletions) +
             ",\"cpu_completed_including_warmups\":" + std::to_string(cpuCompletions) +
             ",\"live_throughput_measured\":false,\"uncached_PCIe_cost_measured\":false,\"scope\":\"cached_heap_calibration_only\"}");
        return 0;
    } catch (const std::exception &error) {
        emit("{\"event\":\"failed\",\"error\":" + quote(error.what()) + ",\"passed\":false,\"hardware_copy_executed\":" +
             (copySucceeded ? "true" : "false") + ",\"rga_completed\":" + std::to_string(rgaCompletions) +
             ",\"cpu_completed\":" + std::to_string(cpuCompletions) + ",\"performance_claim\":false}");
        return 1;
    }
}
