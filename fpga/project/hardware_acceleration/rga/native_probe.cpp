// Standalone fixture-only RGA probe. No FPGA/PCIe/DRM/RKNN/viewer access.
#include "reference.hpp"
#include <rga/im2d.h>
#include <rga/rga.h>
#include <cerrno>
#include <cmath>
#include <ctime>
#include <dlfcn.h>
#include <fcntl.h>
#include <fstream>
#include <iostream>
#include <memory>
#include <sys/ioctl.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <unistd.h>

using namespace rga_probe;
static std::string quote(const std::string& value) {
    std::ostringstream s; s << '"';
    for (unsigned char c : value) {
        if (c == '"' || c == '\\') s << '\\' << c;
        else if (c < 32) s << "\\u" << std::hex << std::setw(4) << std::setfill('0') << unsigned(c);
        else s << c;
    }
    s << '"'; return s.str();
}
static void emit(const std::string& line) { std::cout << line << std::endl; }
static void require(bool yes, const std::string& message) {
    if (!yes) throw std::runtime_error(message);
}
static std::string error(const char* action) { return std::string(action) + ": " + std::strerror(errno); }
static double now(clockid_t id) {
    timespec t{}; if (clock_gettime(id, &t)) throw std::runtime_error(error("clock_gettime"));
    return double(t.tv_sec) * 1000.0 + double(t.tv_nsec) / 1e6;
}
struct Stamp {
    double wall = now(CLOCK_MONOTONIC), cpu = now(CLOCK_THREAD_CPUTIME_ID);
};
struct Elapsed { double wall, cpu; };
static Elapsed elapsed(const Stamp& s) {
    return {now(CLOCK_MONOTONIC) - s.wall, now(CLOCK_THREAD_CPUTIME_ID) - s.cpu};
}
struct Samples {
    std::vector<double> wall, cpu;
    void add(Elapsed e) { wall.push_back(e.wall); cpu.push_back(e.cpu); }
    static std::string summary(std::vector<double> v) {
        if (v.empty()) return "null";
        double sum = 0; for (double x : v) sum += x;
        std::sort(v.begin(), v.end());
        auto percentile = [&](double p) { return v[size_t(std::ceil(p * v.size())) - 1]; };
        std::ostringstream s; s << std::fixed << std::setprecision(6)
          << "{\"mean_ms\":" << sum / v.size() << ",\"p50_ms\":" << percentile(.50)
          << ",\"p95_ms\":" << percentile(.95) << ",\"p99_ms\":" << percentile(.99)
          << ",\"min_ms\":" << v.front() << ",\"max_ms\":" << v.back() << '}';
        return s.str();
    }
    std::string json() const { return "{\"wall\":" + summary(wall) + ",\"thread_cpu\":" + summary(cpu) + '}'; }
};
static std::string difference_json(const Difference& d) {
    std::ostringstream s; s << "{\"exact\":" << (d.exact() ? "true" : "false")
        << ",\"different_pixels\":" << d.pixels << ",\"different_bytes_rgb\":["
        << d.bytes[0] << ',' << d.bytes[1] << ',' << d.bytes[2]
        << "],\"max_abs_diff_rgb\":[" << d.max[0] << ',' << d.max[1] << ',' << d.max[2] << "]}";
    return s.str();
}
static void check_status(IM_STATUS status, const char* action, bool check = false) {
    if (status != IM_STATUS_SUCCESS && !(check && status == IM_STATUS_NOERROR))
        throw std::runtime_error(std::string(action) + ": " + imStrError(status));
}

// Linux UAPI, with distinct names to avoid redefining SDK macros. Layout matches
// the old viewer DmaBuffer allocation; this probe adds mandatory cache sync.
struct HeapAllocation { uint64_t len; uint32_t fd, fd_flags; uint64_t heap_flags; };
struct BufferSync { uint64_t flags; };
static_assert(sizeof(HeapAllocation) == 24, "DMA heap UAPI layout");
constexpr uint64_t SYNC_READ = 1, SYNC_WRITE = 2, SYNC_END = 4;
class Buffer {
    bool dma_;
    bool accessing_ = false;
    uint64_t access_flags_ = 0;
    Bytes virtual_;
public:
    int fd = -1;
    uint8_t* data = nullptr;
    size_t size;
    rga_buffer_handle_t handle = 0;
    Buffer(size_t bytes, bool dma, const std::string& heap_path) : dma_(dma), size(bytes) {
        try {
            if (dma_) {
                const int heap = open(heap_path.c_str(), O_RDWR | O_CLOEXEC);
                if (heap < 0) throw std::runtime_error(error("open dma heap"));
                HeapAllocation alloc{}; alloc.len = bytes; alloc.fd_flags = O_RDWR | O_CLOEXEC;
                int result;
                do { result = ioctl(heap, _IOWR('H', 0, HeapAllocation), &alloc); } while (result < 0 && errno == EINTR);
                const int saved = errno; close(heap); errno = saved;
                if (result < 0) throw std::runtime_error(error("DMA_HEAP_IOCTL_ALLOC"));
                fd = int(alloc.fd);
                void* mapped = mmap(nullptr, bytes, PROT_READ | PROT_WRITE, MAP_SHARED, fd, 0);
                if (mapped == MAP_FAILED) throw std::runtime_error(error("mmap dma-buf"));
                data = static_cast<uint8_t*>(mapped);
                handle = importbuffer_fd(fd, int(bytes));
            } else {
                virtual_.resize(bytes); data = virtual_.data();
                handle = importbuffer_virtualaddr(data, int(bytes));
            }
            require(handle != 0, "RGA import failed");
        } catch (...) { release(); throw; }
    }
    Buffer(const Buffer&) = delete;
    Buffer& operator=(const Buffer&) = delete;
    ~Buffer() { release(); }
    void sync(uint64_t flags) {
        if (!dma_) return;
        BufferSync arg{flags}; int result;
        do { result = ioctl(fd, _IOW('b', 0, BufferSync), &arg); } while (result < 0 && errno == EINTR);
        if (result < 0) throw std::runtime_error(error("DMA_BUF_IOCTL_SYNC"));
    }
    void begin(uint64_t flags) {
        require(!accessing_, "nested CPU dma-buf access");
        sync(flags); accessing_ = true; access_flags_ = flags;
    }
    void end() {
        require(accessing_, "unpaired CPU dma-buf access");
        sync(access_flags_ | SYNC_END); accessing_ = false;
    }
    void release() noexcept {
        if (accessing_) { try { end(); } catch (...) {} }
        if (handle) { releasebuffer_handle(handle); handle = 0; }
        if (dma_ && data) { munmap(data, size); data = nullptr; }
        if (fd >= 0) { close(fd); fd = -1; }
    }
    rga_buffer_t wrap(int height, int format) const {
        return wrapbuffer_handle(handle, W, height, format, W, height);
    }
};

struct Measurement {
    Elapsed total{}, upload{}, device{}, access{}, correction{};
};
class Pipeline {
    bool model_, two_stage_;
    int format_;
    Buffer source_, full_, output_;
    rga_buffer_t source_image_, full_image_, output_image_;
public:
    Pipeline(bool model, bool two_stage, int format, bool dma, const std::string& heap)
        : model_(model), two_stage_(two_stage), format_(format),
          source_(RAW_BYTES, dma, heap), full_(RGB_BYTES, dma, heap),
          output_(model ? MODEL_BYTES : RGB_BYTES, dma, heap),
          source_image_(source_.wrap(H, format)), full_image_(full_.wrap(H, RK_FORMAT_RGB_888)),
          output_image_(output_.wrap(model ? MH : H, RK_FORMAT_RGB_888)) {
        output_.begin(SYNC_WRITE); std::memset(output_.data, 114, output_.size); output_.end();
        const im_rect sr{0, 0, W, H}, dr{0, model ? PAD_Y : 0, W, H};
        // imcheck gates every task before it can execute. Sizes are identical:
        // destination ROI changes position only, never crop/scale/full input.
        if (two_stage_) {
            check_status(imcheck(source_image_, full_image_, sr, sr, IM_SYNC), "imcheck conversion", true);
            check_status(imcheck(full_image_, output_image_, sr, dr, IM_SYNC), "imcheck ROI copy", true);
        } else check_status(imcheck(source_image_, output_image_, sr, dr, IM_SYNC), "imcheck direct", true);
        emit("{\"kind\":\"imcheck\",\"model_letterbox\":" + std::string(model ? "true" : "false") +
             ",\"two_stage\":" + (two_stage ? "true" : "false") + ",\"format\":" + std::to_string(format) +
             ",\"passed\":true,\"src_rect\":[0,0,640,480],\"dst_rect\":[0," +
             std::to_string(model ? PAD_Y : 0) + ",640,480]}");
    }
    Measurement run(const Bytes& raw, const Calibration* cal) {
        Measurement m; const Stamp total;
        {
            const Stamp t;
            source_.begin(SYNC_WRITE); std::memcpy(source_.data, raw.data(), RAW_BYTES); source_.end();
            m.upload = elapsed(t);
        }
        {
            const Stamp t;
            if (!model_) {
                check_status(imcvtcolor(source_image_, output_image_, format_, RK_FORMAT_RGB_888), "imcvtcolor");
            } else {
                rga_buffer_t input = source_image_;
                if (two_stage_) {
                    check_status(imcvtcolor(source_image_, full_image_, format_, RK_FORMAT_RGB_888), "imcvtcolor");
                    input = full_image_;
                }
                // Match the 10-argument API used by the captured legacy bridge;
                // IM_SYNC guarantees completion before any CPU access.
                check_status(improcess(input, output_image_, {}, {0,0,W,H}, {0,PAD_Y,W,H}, {},
                                       -1, nullptr, nullptr, IM_SYNC), "improcess ROI");
            }
            m.device = elapsed(t);
        }
        const uint64_t flags = cal && cal->correction != Correction::exact ? SYNC_READ | SYNC_WRITE : SYNC_READ;
        { const Stamp t; output_.begin(flags); m.access = elapsed(t); }
        if (cal) {
            const Stamp t;
            correct(output_.data + (model_ ? size_t(PAD_Y)*W*3 : 0), size_t(W)*H, *cal);
            m.correction = elapsed(t);
        }
        { const Stamp t; output_.end(); const auto e = elapsed(t); m.access.wall += e.wall; m.access.cpu += e.cpu; }
        m.total = elapsed(total);
        return m;
    }
    Bytes snapshot() {
        output_.begin(SYNC_READ);
        Bytes copy(output_.data, output_.data + output_.size);
        output_.end(); return copy;
    }
};

static Bytes load_fixture(const std::string& path) {
    struct stat st{};
    require(stat(path.c_str(), &st) == 0 && S_ISREG(st.st_mode), "input must be a regular fixture file");
    require(st.st_size == off_t(RAW_BYTES), "input fixture must be exactly 614400 bytes");
    std::ifstream f(path, std::ios::binary);
    Bytes raw(RAW_BYTES); f.read(reinterpret_cast<char*>(raw.data()), raw.size());
    require(bool(f), "fixture read failed"); return raw;
}
struct Options {
    bool dma = true;
    int warmup = 30, frames = 500;
    std::string heap = "/dev/dma_heap/system", dump;
    std::vector<std::string> fixtures;
};
static Options options(int argc, char** argv) {
    Options out;
    for (int i = 1; i < argc; ++i) {
        const std::string arg = argv[i];
        auto value = [&]() { require(i+1 < argc, "missing option value"); return std::string(argv[++i]); };
        if (arg == "--memory") { const auto m = value(); require(m == "fd" || m == "virtual", "invalid memory mode"); out.dma = m == "fd"; }
        else if (arg == "--frames") out.frames = std::stoi(value());
        else if (arg == "--warmup") out.warmup = std::stoi(value());
        else if (arg == "--heap") out.heap = value();
        else if (arg == "--dump-dir") out.dump = value();
        else if (arg == "--fixture") out.fixtures.push_back(value());
        else throw std::runtime_error("unknown option: " + arg);
    }
    require(out.frames > 0 && out.frames <= 100000 && out.warmup >= 0 && out.warmup <= 10000, "invalid timing limits");
    require(!out.fixtures.empty(), "at least one --fixture is required");
    return out;
}
static void dump(const std::string& path, const Bytes& bytes) {
    std::ofstream f(path, std::ios::binary); f.write(reinterpret_cast<const char*>(bytes.data()), bytes.size());
    require(bool(f), "output dump failed");
}
static void benchmark_cpu(const Bytes& raw, bool model, bool two_stage, const Options& opt, int fixture) {
    const Bytes ref = golden(raw, model);
    Bytes out(ref.size(), 114), full(RGB_BYTES);
    Samples timing;
    for (int i = -opt.warmup; i < opt.frames; ++i) {
        const Stamp t;
        if (model && two_stage) {
            convert(raw.data(), full.data(), size_t(W)*H);
            for (int y = 0; y < H; ++y)
                std::memcpy(out.data()+size_t(y+PAD_Y)*W*3, full.data()+size_t(y)*W*3, size_t(W)*3);
        } else convert(raw.data(), out.data()+(model ? size_t(PAD_Y)*W*3 : 0), size_t(W)*H);
        const auto e = elapsed(t);
        require(out == ref, "CPU benchmark input changed"); // Outside measured interval.
        if (i >= 0) timing.add(e);
    }
    emit("{\"kind\":\"benchmark\",\"backend\":\"cpu\",\"fixture\":" + std::to_string(fixture) +
         ",\"path\":" + quote(model ? (two_stage ? "model_viewer_two_stage" : "model_fused") : "full_frame") +
         ",\"frames\":" + std::to_string(opt.frames) + ",\"warmup\":" + std::to_string(opt.warmup) +
         ",\"exact_every_frame\":true,\"output_fnv1a64\":" + quote(fnv1a(out)) + ",\"total\":" + timing.json() + '}');
}
static void benchmark_rga(Pipeline& pipeline, const Bytes& raw, bool model, const char* path,
                          const Calibration& cal, const Options& opt, int fixture, bool corrected) {
    const Bytes ref = golden(raw, model);
    Samples total, upload, device, access, correction;
    bool every_exact = true;
    Bytes out;
    Difference last;
    for (int i = -opt.warmup; i < opt.frames; ++i) {
        const auto m = pipeline.run(raw, corrected ? &cal : nullptr);
        out = pipeline.snapshot(); // Validation reads/copies/hashes are outside timing.
        last = compare(out.data(), ref.data(), ref.size()/3);
        every_exact &= last.exact();
        require(!model || padding_ok(out.data()), "RGA changed letterbox padding");
        require(!corrected || last.exact(), "corrected RGA output differs from model input");
        if (i >= 0) {
            total.add(m.total); upload.add(m.upload); device.add(m.device);
            access.add(m.access); correction.add(m.correction);
        }
    }
    emit("{\"kind\":\"benchmark\",\"backend\":\"rga\",\"fixture\":" + std::to_string(fixture) +
         ",\"path\":" + quote(path) + ",\"corrected\":" + (corrected ? "true" : "false") +
         ",\"correction\":" + quote(corrected ? name(cal.correction) : "none") +
         ",\"frames\":" + std::to_string(opt.frames) + ",\"warmup\":" + std::to_string(opt.warmup) +
         ",\"exact_every_frame\":" + (every_exact ? "true" : "false") +
         ",\"eligible_unchanged_input\":" + (every_exact ? "true" : "false") +
         ",\"output_fnv1a64\":" + quote(fnv1a(out)) + ",\"reference_fnv1a64\":" + quote(fnv1a(ref)) +
         ",\"difference\":" + difference_json(last) + ",\"total\":" + total.json() +
         ",\"source_copy_and_sync\":" + upload.json() + ",\"rga_synchronous_call\":" + device.json() +
         ",\"destination_sync\":" + access.json() + ",\"cpu_correction\":" + correction.json() + '}');
    if (!opt.dump.empty()) {
        const auto stem = opt.dump + "/fixture" + std::to_string(fixture) + "_" + path + (corrected ? "_corrected" : "_direct");
        dump(stem + ".rgb888", out);
    }
}
static void versions() {
    // Resolve actual available SDK query symbols; board headers/libraries are
    // captured and hashed by the runner. This never substitutes GPU information.
    using Query = const char* (*)(int);
    const char* symbol = "querystring";
    auto query = reinterpret_cast<Query>(dlsym(RTLD_DEFAULT, symbol));
    if (!query) { symbol = "imquerystring"; query = reinterpret_cast<Query>(dlsym(RTLD_DEFAULT, symbol)); }
    require(query != nullptr, "librga exposes neither querystring nor imquerystring");
    const char* text = query(RGA_ALL);
    emit("{\"kind\":\"rga_runtime\",\"query_symbol\":" + quote(symbol) +
         ",\"query_all\":" + quote(text ? text : "null") + '}');
#ifdef RGA_API_VERSION
    emit("{\"kind\":\"rga_header\",\"api_version\":" + quote(RGA_API_VERSION) + '}');
#endif
}
int main(int argc, char** argv) {
    try {
        const Options opt = options(argc, argv);
        require(__BYTE_ORDER__ == __ORDER_LITTLE_ENDIAN__, "probe requires little-endian RGA host");
        emit("{\"kind\":\"configuration\",\"hardware_requested\":true,\"memory\":" + quote(opt.dma ? "fd" : "virtual") +
             ",\"heap\":" + quote(opt.heap) + ",\"source_format\":\"LE_R5top_RGB565\","
             "\"rgb_stride_bytes\":1920,\"model_size\":[640,640],\"padding\":114,"
             "\"persistent_padding\":true,\"validation_outside_timing\":true,\"input_copy_in_timing\":true}");
        versions();
        const Bytes colors = tiled_colors();
        int selected_format = -1;
        // Report both enum interpretations. Their name alone is not evidence of
        // bit order; full-word test selects a channel-preserving exact/repairable one.
        const std::array<std::pair<int,const char*>,2> formats{{
            {RK_FORMAT_RGB_565,"RK_FORMAT_RGB_565"}, {RK_FORMAT_BGR_565,"RK_FORMAT_BGR_565"}}};
        for (const auto& format : formats) {
            try {
                Pipeline p(false, false, format.first, opt.dma, opt.heap);
                p.run(colors, nullptr); const Bytes actual = p.snapshot();
                const auto cal = calibrate(colors, actual.data());
                emit("{\"kind\":\"format_calibration\",\"enum_name\":" + quote(format.second) +
                     ",\"enum_value\":" + std::to_string(format.first) + ",\"colors\":65536,\"pixels\":307200,"
                     "\"correction\":" + quote(name(cal.correction)) + ",\"reason\":" + quote(cal.reason) +
                     ",\"difference\":" + difference_json(cal.diff) + '}');
                if (cal.correction != Correction::rejected &&
                    (selected_format < 0 || cal.correction == Correction::exact)) {
                    selected_format = format.first;
                }
            } catch (const std::exception& e) {
                emit("{\"kind\":\"format_rejected\",\"enum_name\":" + quote(format.second) + ",\"error\":" + quote(e.what()) + '}');
            }
        }
        require(selected_format >= 0, "neither RGA RGB565 interpretation preserves the CPU color input");
        std::vector<std::string> supported_paths;
        // Validate and calibrate each full-size operation separately; a conversion
        // result does not prove an improcess ROI result on this driver.
        for (int path_id = 0; path_id < 3; ++path_id) {
            const bool model = path_id != 0, two_stage = path_id == 2;
            const char* path = path_id == 0 ? "full_frame" : (path_id == 1 ? "model_direct_roi" : "model_two_stage_roi");
            try {
                Pipeline pipeline(model, two_stage, selected_format, opt.dma, opt.heap);
                pipeline.run(colors, nullptr); Bytes actual = pipeline.snapshot();
                const size_t offset = model ? size_t(PAD_Y)*W*3 : 0;
                const auto cal = calibrate(colors, actual.data()+offset);
                require(cal.correction != Correction::rejected, std::string(path) + " failed exhaustive calibration");
                require(!model || padding_ok(actual.data()), "gradient padding differs");
                pipeline.run(colors, &cal); const auto fixed = pipeline.snapshot();
                require(fixed == golden(colors, model), "gradient correction is not exact");
                emit("{\"kind\":\"path_calibration\",\"path\":" + quote(path) + ",\"selected_format\":" +
                     std::to_string(selected_format) + ",\"correction\":" + quote(name(cal.correction)) +
                     ",\"corrected_exhaustive_exact\":true,\"direct_difference\":" + difference_json(cal.diff) + '}');
                for (size_t i = 0; i < opt.fixtures.size(); ++i) {
                    const auto raw = load_fixture(opt.fixtures[i]);
                    emit("{\"kind\":\"fixture\",\"index\":" + std::to_string(i+1) + ",\"path\":" +
                         quote(opt.fixtures[i]) + ",\"raw_fnv1a64\":" + quote(fnv1a(raw)) + '}');
                    if (path_id == 0) benchmark_cpu(raw, false, false, opt, int(i+1));
                    if (model) {
                        benchmark_cpu(raw, true, true, opt, int(i+1));
                        benchmark_cpu(raw, true, false, opt, int(i+1));
                    }
                    benchmark_rga(pipeline, raw, model, path, cal, opt, int(i+1), false);
                    benchmark_rga(pipeline, raw, model, path, cal, opt, int(i+1), true);
                }
                supported_paths.push_back(path);
            } catch (const std::exception& e) {
                emit("{\"kind\":\"path_rejected\",\"path\":" + quote(path) + ",\"error\":" + quote(e.what()) + '}');
            }
        }
        require(std::find(supported_paths.begin(), supported_paths.end(), "full_frame") != supported_paths.end(),
                "full-frame RGA path is required and did not pass");
        require(supported_paths.size() >= 2, "no complete model-letterbox RGA path passed");
        std::string paths = "[";
        for (size_t i = 0; i < supported_paths.size(); ++i) { if (i) paths += ','; paths += quote(supported_paths[i]); }
        paths += ']';
        emit("{\"kind\":\"complete\",\"passed\":true,\"supported_paths\":" + paths +
             ",\"rkNN_detection_parity_tested\":false,\"viewer_changed\":false}");
        return 0;
    } catch (const std::exception& e) {
        emit("{\"kind\":\"fatal\",\"passed\":false,\"error\":" + quote(e.what()) + '}'); return 1;
    }
}
