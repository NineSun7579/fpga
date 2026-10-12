#include "stereo_depth.h"
#include "pango_stereo_source.h"

#include <opencv2/calib3d.hpp>
#include <opencv2/highgui.hpp>
#include <opencv2/imgcodecs.hpp>
#include <opencv2/imgproc.hpp>
#include <algorithm>
#include <chrono>
#include <csignal>
#include <cstdlib>
#include <filesystem>
#include <iomanip>
#include <iostream>
#include <memory>
#include <mutex>
#include <optional>
#include <atomic>
#include <sstream>
#include <stdexcept>
#include <string>
#include <thread>
#include <vector>

namespace {
constexpr int headerHeight = 104;
constexpr const char* windowName = "detview stereo demo";
volatile std::sig_atomic_t stopRequested = 0;
void onSignal(int) { stopRequested = 1; }

struct Options {
    bool synthetic = false, live = false, headless = false, selfTest = false;
    bool assumeSynchronized = false;
    int leftCamera = 0, rightCamera = 0;
    int threads = 2;
    int benchmark = 1;
    std::optional<int32_t> tagOffset;
    std::string leftImage, rightImage, calibration, output;
    stereo::MatcherOptions matcher;
    cv::Rect roi;
};

void usage() {
    std::cout <<
        "detview_stereo_demo [--synthetic | --left-image L --right-image R | --live]\n"
        "  --calibration stereo.yml         Full stereo calibration; T must be in meters\n"
        "  --left-camera N --right-camera N  Explicit FPGA cameras, distinct IDs 1..6\n"
        "  --assume-synchronized --tag-offset N   Verified exposure sync and common frame-counter relation\n"
        "  --scale 0.5 --num-disparities 64 --block-size 5 --threads 2\n"
        "  --roi x,y,w,h                     ROI in processed/rectified left-image pixels\n"
        "  --headless --output DIR           Offline single pair, save results without a display\n"
        "  --benchmark N                     Headless offline repeated matching, no camera access\n"
        "  --self-test                      Geometry and synthetic matching tests, no hardware\n"
        "No source arguments: synthetic demo. Drag ROI on left/disparity; Q or Escape quits.\n";
}

int integer(const std::string& value) {
    size_t used = 0;
    const int result = std::stoi(value, &used);
    if (used != value.size()) throw std::invalid_argument("Invalid integer: " + value);
    return result;
}

Options parse(int argc, char** argv) {
    Options options;
    for (int i = 1; i < argc; ++i) {
        const std::string argument = argv[i];
        auto value = [&]() -> std::string {
            if (++i >= argc) throw std::invalid_argument("Missing value for " + argument);
            return argv[i];
        };
        if (argument == "--help" || argument == "-h") { usage(); std::exit(0); }
        else if (argument == "--synthetic") options.synthetic = true;
        else if (argument == "--live") options.live = true;
        else if (argument == "--headless") options.headless = true;
        else if (argument == "--self-test") options.selfTest = true;
        else if (argument == "--assume-synchronized") options.assumeSynchronized = true;
        else if (argument == "--left-camera") options.leftCamera = integer(value());
        else if (argument == "--right-camera") options.rightCamera = integer(value());
        else if (argument == "--left-image") options.leftImage = value();
        else if (argument == "--right-image") options.rightImage = value();
        else if (argument == "--calibration") options.calibration = value();
        else if (argument == "--output") options.output = value();
        else if (argument == "--num-disparities") options.matcher.numDisparities = integer(value());
        else if (argument == "--block-size") options.matcher.blockSize = integer(value());
        else if (argument == "--threads") options.threads = integer(value());
        else if (argument == "--benchmark") options.benchmark = integer(value());
        else if (argument == "--tag-offset") options.tagOffset = integer(value());
        else if (argument == "--scale") {
            const std::string text = value();
            size_t used = 0;
            options.matcher.scale = std::stod(text, &used);
            if (used != text.size()) throw std::invalid_argument("Invalid scale");
        } else if (argument == "--roi") {
            std::string text = value();
            for (char& c : text) if (c == ',') c = ' ';
            std::istringstream input(text);
            if (!(input >> options.roi.x >> options.roi.y >> options.roi.width >> options.roi.height))
                throw std::invalid_argument("ROI must be x,y,w,h");
            std::string extra;
            if (input >> extra || options.roi.x < 0 || options.roi.y < 0 ||
                options.roi.width <= 0 || options.roi.height <= 0)
                throw std::invalid_argument("Invalid ROI");
        } else throw std::invalid_argument("Unknown argument: " + argument);
    }
    if (options.selfTest) {
        if (argc != 2) throw std::invalid_argument("Use --self-test by itself");
        return options;
    }
    if (options.threads < 1 || options.threads > 64)
        throw std::invalid_argument("Threads must be in 1..64");
    if (options.benchmark < 1 || options.benchmark > 1000 ||
        (options.benchmark > 1 && !options.headless))
        throw std::invalid_argument("Benchmark must be 1..1000 and repeated matching requires --headless");
    const bool images = !options.leftImage.empty() || !options.rightImage.empty();
    if (images && (options.leftImage.empty() || options.rightImage.empty()))
        throw std::invalid_argument("Provide both left and right images");
    const int sources = int(options.synthetic) + int(options.live) + int(images);
    if (sources > 1) throw std::invalid_argument("Select exactly one image source");
    if (sources == 0) options.synthetic = true;
    if (options.synthetic && !options.calibration.empty())
        throw std::invalid_argument("Synthetic mode uses its own simulation calibration");
    if (options.live && (options.leftCamera < 1 || options.leftCamera > 6 ||
        options.rightCamera < 1 || options.rightCamera > 6 || options.leftCamera == options.rightCamera))
        throw std::invalid_argument("Live mode needs two distinct --left-camera/--right-camera IDs in 1..6");
    if (!options.live && (options.leftCamera || options.rightCamera || options.assumeSynchronized || options.tagOffset))
        throw std::invalid_argument("Camera IDs, synchronization and tag offset are only for --live");
    if (options.headless && options.live)
        throw std::invalid_argument("Headless mode currently accepts synthetic or saved image pairs");
    if (options.headless && options.output.empty())
        throw std::invalid_argument("Headless mode requires --output DIR");
    return options;
}

stereo::Calibration syntheticCalibration() {
    stereo::Calibration calibration;
    calibration.imageSize = cv::Size(640, 480);
    calibration.K1 = (cv::Mat_<double>(3, 3) << 400, 0, 320, 0, 400, 240, 0, 0, 1);
    calibration.K2 = calibration.K1.clone();
    calibration.D1 = cv::Mat::zeros(1, 5, CV_64F);
    calibration.D2 = calibration.D1.clone();
    calibration.R = cv::Mat::eye(3, 3, CV_64F);
    calibration.T = (cv::Mat_<double>(3, 1) << -0.1, 0, 0);
    return calibration;
}

stereo::StereoPair syntheticPair() {
    stereo::StereoPair pair;
    cv::Mat gray(480, 640, CV_8UC1);
    cv::RNG random(20261002);
    random.fill(gray, cv::RNG::UNIFORM, 0, 256);
    cv::GaussianBlur(gray, gray, cv::Size(3, 3), 0.7);
    cv::Mat right(gray.size(), gray.type());
    random.fill(right, cv::RNG::UNIFORM, 0, 256);
    gray(cv::Rect(20, 0, gray.cols - 20, gray.rows)).copyTo(
        right(cv::Rect(0, 0, gray.cols - 20, gray.rows)));
    cv::cvtColor(gray, pair.left, cv::COLOR_GRAY2BGR);
    cv::cvtColor(right, pair.right, cv::COLOR_GRAY2BGR);
    return pair;
}

struct RoiControl {
    cv::Rect roi;
    cv::Size size;
    cv::Point anchor;
    bool dragging = false;
    int dragPanel = 0;
};

void mouse(int event, int x, int y, int, void* context) {
    auto& control = *static_cast<RoiControl*>(context);
    if (control.size.width <= 0) return;
    const int panel = x / control.size.width;
    if (event == cv::EVENT_LBUTTONDOWN) {
        if ((panel != 0 && panel != 2) || y < headerHeight || y >= headerHeight + control.size.height)
            return;
        control.dragging = true;
        control.dragPanel = panel;
        control.anchor = cv::Point(x - panel * control.size.width, y - headerHeight);
    }
    if (control.dragging && (event == cv::EVENT_MOUSEMOVE || event == cv::EVENT_LBUTTONUP)) {
        const cv::Point position(std::clamp(x - control.dragPanel * control.size.width, 0, control.size.width - 1),
                                 std::clamp(y - headerHeight, 0, control.size.height - 1));
        control.roi = cv::Rect(cv::Point(std::min(control.anchor.x, position.x), std::min(control.anchor.y, position.y)),
                              cv::Point(std::max(control.anchor.x, position.x) + 1, std::max(control.anchor.y, position.y) + 1));
        if (event == cv::EVENT_LBUTTONUP) control.dragging = false;
    }
}

std::string fixed(double value, int precision = 2) {
    std::ostringstream text;
    text << std::fixed << std::setprecision(precision) << value;
    return text.str();
}

stereo::RangeEstimate measurement(const stereo::DepthResult& result, const cv::Rect& roi, const Options& options) {
    auto range = stereo::DepthEngine::estimate(result, roi);
    if (options.live && (!options.assumeSynchronized || !options.tagOffset)) {
        range.valid = false;
        range.meters = 0;
        range.reason = "Exposure sync / frame-counter pairing not confirmed";
    }
    return range;
}

cv::Mat colorDisparity(const stereo::DepthResult& result, int disparities) {
    cv::Mat gray, color;
    result.disparity.convertTo(gray, CV_8U, 255.0 / disparities);
    cv::applyColorMap(gray, color, cv::COLORMAP_TURBO);
    color.setTo(cv::Scalar::all(0), result.validMask == 0);
    return color;
}

cv::Mat render(const stereo::DepthResult& result, const stereo::StereoPair& pair,
               const Options& options, const RoiControl& control, double matchingMs) {
    cv::Mat panels, left, right;
    if (result.left.channels() == 1) cv::cvtColor(result.left, left, cv::COLOR_GRAY2BGR);
    else left = result.left.clone();
    if (result.right.channels() == 1) cv::cvtColor(result.right, right, cv::COLOR_GRAY2BGR);
    else right = result.right.clone();
    cv::Mat disparity = colorDisparity(result, options.matcher.numDisparities);
    cv::rectangle(left, control.roi, cv::Scalar(0, 255, 0), 1);
    cv::rectangle(disparity, control.roi, cv::Scalar(0, 255, 0), 1);
    cv::hconcat(std::vector<cv::Mat>{left, right, disparity}, panels);
    cv::Mat canvas(panels.rows + headerHeight + 30, panels.cols, CV_8UC3, cv::Scalar(25, 25, 25));
    panels.copyTo(canvas(cv::Rect(0, headerHeight, panels.cols, panels.rows)));
    auto line = [&](const std::string& text, int y, cv::Scalar color = cv::Scalar(220, 220, 220)) {
        cv::putText(canvas, text, cv::Point(8, y), cv::FONT_HERSHEY_SIMPLEX, 0.45, color, 1, cv::LINE_AA);
    };
    const std::string source = options.synthetic ? "SIMULATION (expected Z=2.00m)" :
        options.live ? "FPGA C" + std::to_string(options.leftCamera) + "/C" + std::to_string(options.rightCamera) : "OFFLINE IMAGE PAIR";
    line(source + " | match " + fixed(matchingMs, 1) + "ms", 18);
    const auto range = measurement(result, control.roi, options);
    line(range.valid ? (options.synthetic ? "SIMULATED ROI Z: " : "ROI optical-axis Z: ") +
            fixed(range.meters, 3) + " m | valid " + std::to_string(range.validPixels) + "/" + std::to_string(range.totalPixels)
            : "Depth unavailable: " + range.reason, 40, range.valid ? cv::Scalar(0, 255, 100) : cv::Scalar(0, 180, 255));
    if (options.live) {
        line("Tags L/R: " + std::to_string(pair.leftTag) + "/" + std::to_string(pair.rightTag) +
             " | host read gap " + fixed(pair.hostReadGapMs) + "ms (NOT exposure skew)", 62);
        line(options.assumeSynchronized && options.tagOffset ? "Sync assumed; matching common frame IDs, offset=" + std::to_string(*options.tagOffset) :
             "Sync or frame-counter relation unverified; metric ranging disabled", 82);
    } else {
        line(options.synthetic ? "Synthetic focal length/baseline are test fixtures, not board calibration" :
             "Saved pair must be simultaneous; Z is axial depth, not Euclidean range", 65);
    }
    for (int panel = 0; panel < 3; ++panel)
        cv::putText(canvas, panel == 0 ? (result.calibrated ? "LEFT RECTIFIED" : "LEFT UNRECTIFIED") :
                    panel == 1 ? (result.calibrated ? "RIGHT RECTIFIED" : "RIGHT UNRECTIFIED") : "DISPARITY",
                    cv::Point(panel * panels.cols / 3 + 8, headerHeight - 6), cv::FONT_HERSHEY_SIMPLEX, 0.4,
                    cv::Scalar(180, 180, 180), 1, cv::LINE_AA);
    line("Drag ROI on left/disparity | Q/Esc quit | S save snapshot", canvas.rows - 9);
    return canvas;
}

void save(const std::string& directory, const stereo::DepthResult& result, const cv::Mat& canvas,
          const cv::Rect& roi, const Options& options, const stereo::StereoPair& pair, double matchingMs) {
    namespace fs = std::filesystem;
    fs::create_directories(directory);
    auto image = [&](const char* name, const cv::Mat& data) {
        if (!cv::imwrite((fs::path(directory) / name).string(), data))
            throw std::runtime_error(std::string("Cannot save ") + name);
    };
    image("preview.png", canvas);
    image("left_raw.png", pair.left);
    image("right_raw.png", pair.right);
    image("left_rectified.png", result.left);
    image("right_rectified.png", result.right);
    image("disparity_color.png", colorDisparity(result, options.matcher.numDisparities));
    image("valid_mask.png", result.validMask);
    cv::FileStorage record((fs::path(directory) / "measurement.yml").string(), cv::FileStorage::WRITE);
    if (!record.isOpened()) throw std::runtime_error("Cannot save measurement.yml");
    const auto range = measurement(result, roi, options);
    record << "source" << (options.synthetic ? "simulation" : options.live ? "fpga" : "offline")
           << "calibrated" << int(result.calibrated) << "metric_valid" << int(range.valid)
           << "live_sync_assumed" << int(options.assumeSynchronized)
           << "left_camera" << options.leftCamera << "right_camera" << options.rightCamera
           << "scale" << options.matcher.scale
           << "num_disparities" << options.matcher.numDisparities
           << "block_size" << options.matcher.blockSize
           << "reason" << range.reason << "roi" << roi
           << "valid_pixels" << range.validPixels << "total_pixels" << range.totalPixels
           << "matching_ms" << matchingMs << "acquisition_ms" << pair.acquisitionMs
           << "host_read_gap_ms" << pair.hostReadGapMs
           << "left_tag" << double(pair.leftTag) << "right_tag" << double(pair.rightTag)
           << "fx_pixels" << result.fxPixels << "baseline_meters" << result.baselineMeters
           << "cx_offset_pixels" << result.cxOffsetPixels << "disparity_pixels" << result.disparity;
    if (range.valid) record << "axial_depth_meters" << range.meters;
    if (options.tagOffset) record << "left_minus_right_tag_offset" << *options.tagOffset;
    std::cout << "Saved " << directory << ": " << (range.valid ? fixed(range.meters, 3) + " m" : range.reason) << '\n';
}

struct LiveSnapshot {
    stereo::StereoPair pair;
    stereo::DepthResult result;
    double matchingMs = 0;
    std::chrono::steady_clock::time_point acquiredAt{};
    uint64_t generation = 0;
    std::string error;
};

class LiveWorker {
public:
    LiveWorker(stereo::PangoStereoSource& source, stereo::DepthEngine& engine)
        : thread_([this, &source, &engine] {
            try {
                while (!stop_) {
                    stereo::StereoPair pair;
                    if (!source.poll(pair)) {
                        std::this_thread::sleep_for(std::chrono::milliseconds(5));
                        continue;
                    }
                    const auto acquiredAt = std::chrono::steady_clock::now();
                    auto result = engine.compute(pair.left, pair.right);
                    const double matchingMs = std::chrono::duration<double, std::milli>(
                        std::chrono::steady_clock::now() - acquiredAt).count();
                    std::lock_guard<std::mutex> guard(mutex_);
                    latest_.pair = std::move(pair);
                    latest_.result = std::move(result);
                    latest_.matchingMs = matchingMs;
                    latest_.acquiredAt = acquiredAt;
                    ++latest_.generation;
                }
            } catch (const std::exception& error) {
                std::lock_guard<std::mutex> guard(mutex_);
                latest_.error = error.what();
            }
        }) {}
    ~LiveWorker() {
        stop_ = true;
        if (thread_.joinable()) thread_.join();
    }
    LiveSnapshot snapshot() {
        std::lock_guard<std::mutex> guard(mutex_);
        return latest_;
    }
private:
    std::atomic<bool> stop_{false};
    std::mutex mutex_;
    LiveSnapshot latest_;
    std::thread thread_;
};
} // namespace

int main(int argc, char** argv) {
    try {
        const Options options = parse(argc, argv);
        cv::setNumThreads(options.threads);
        if (options.selfTest) return stereo::runSelfTest();
        std::signal(SIGINT, onSignal);
        std::signal(SIGTERM, onSignal);
        stereo::Calibration calibration;
        const stereo::Calibration* calibrationPointer = nullptr;
        if (options.synthetic) { calibration = syntheticCalibration(); calibrationPointer = &calibration; }
        else if (!options.calibration.empty()) {
            calibration = stereo::Calibration::load(options.calibration);
            calibrationPointer = &calibration;
        }
        stereo::DepthEngine engine(options.matcher, calibrationPointer);
        stereo::StereoPair pair;
        std::unique_ptr<stereo::PangoStereoSource> source;
        if (options.live) source = std::make_unique<stereo::PangoStereoSource>(
            options.leftCamera, options.rightCamera, options.tagOffset);
        else if (options.synthetic) pair = syntheticPair();
        else {
            pair.left = cv::imread(options.leftImage, cv::IMREAD_COLOR | cv::IMREAD_IGNORE_ORIENTATION);
            pair.right = cv::imread(options.rightImage, cv::IMREAD_COLOR | cv::IMREAD_IGNORE_ORIENTATION);
            if (pair.left.empty() || pair.right.empty()) throw std::runtime_error("Cannot read stereo input images");
        }
        RoiControl control;
        control.roi = options.roi;
        stereo::DepthResult result;
        cv::Mat canvas;
        double matchingMs = 0;
        const auto started = std::chrono::steady_clock::now();
        auto lastPair = started;
        bool waitingReported = false;
        uint64_t liveGeneration = 0;
        // Destroy/join the worker before source or engine are released.
        std::unique_ptr<LiveWorker> worker;
        if (!options.headless) {
            cv::namedWindow(windowName, cv::WINDOW_AUTOSIZE);
            cv::setMouseCallback(windowName, mouse, &control);
        }
        if (source) worker = std::make_unique<LiveWorker>(*source, engine);
        while (!stopRequested) {
            bool ready = false;
            if (worker) {
                const auto snapshot = worker->snapshot();
                if (!snapshot.error.empty()) throw std::runtime_error(snapshot.error);
                if (snapshot.generation != liveGeneration) {
                    liveGeneration = snapshot.generation;
                    pair = snapshot.pair;
                    result = snapshot.result;
                    matchingMs = snapshot.matchingMs;
                    lastPair = snapshot.acquiredAt;
                    ready = true;
                }
            } else if (result.left.empty()) {
                double sumMs = 0, warmSumMs = 0;
                for (int iteration = 0; iteration < options.benchmark; ++iteration) {
                    const auto before = std::chrono::steady_clock::now();
                    result = engine.compute(pair.left, pair.right);
                    matchingMs = std::chrono::duration<double, std::milli>(std::chrono::steady_clock::now() - before).count();
                    sumMs += matchingMs;
                    if (iteration) warmSumMs += matchingMs;
                }
                if (options.benchmark > 1)
                    std::cout << "Offline benchmark " << options.benchmark << " pairs: mean "
                              << fixed(sumMs / options.benchmark) << " ms; excluding first "
                              << fixed(warmSumMs / (options.benchmark - 1)) << " ms\n";
                lastPair = std::chrono::steady_clock::now();
                ready = true;
            }
            if (ready) {
                control.size = result.left.size();
                if (control.roi.empty())
                    control.roi = cv::Rect(control.size.width / 3, control.size.height / 3,
                                           control.size.width / 3, control.size.height / 3);
                if ((control.roi & cv::Rect(cv::Point(), control.size)) != control.roi)
                    throw std::invalid_argument("ROI extends outside the processed image");
                waitingReported = false;
            }
            const bool stale = source && std::chrono::steady_clock::now() - lastPair > std::chrono::seconds(2);
            if (!result.left.empty()) {
                canvas = render(result, pair, options, control, matchingMs);
                if (stale) {
                    // Cover the previous numeric result so an old measurement is not shown as live.
                    canvas(cv::Rect(0, 22, canvas.cols, 25)).setTo(cv::Scalar(25, 25, 25));
                    cv::putText(canvas, "STALE: no fresh stereo pair; distance unavailable", cv::Point(8, 40),
                                cv::FONT_HERSHEY_SIMPLEX, 0.45, cv::Scalar(0, 180, 255), 1);
                }
                if (options.headless) {
                    save(options.output, result, canvas, control.roi, options, pair, matchingMs);
                    return 0;
                }
            } else {
                canvas = cv::Mat(180, 960, CV_8UC3, cv::Scalar(25, 25, 25));
                cv::putText(canvas, "Waiting for new frames on BOTH selected cameras. Q/Esc to quit.",
                            cv::Point(12, 50), cv::FONT_HERSHEY_SIMPLEX, 0.5, cv::Scalar(200, 200, 200), 1);
            }
            if (stale && !waitingReported) {
                std::cerr << "No fresh stereo pair for 2s; check camera selection and frame tags\n";
                waitingReported = true;
            }
            cv::imshow(windowName, canvas);
            const int key = cv::waitKey(10) & 255;
            if (key == 27 || key == 'q' || key == 'Q' || cv::getWindowProperty(windowName, cv::WND_PROP_VISIBLE) < 1) break;
            if ((key == 's' || key == 'S') && !result.left.empty() && !stale) {
                if (options.output.empty()) std::cerr << "Use --output DIR to enable snapshots\n";
                else save(options.output, result, canvas, control.roi, options, pair, matchingMs);
            }
        }
        if (!options.headless) cv::destroyAllWindows();
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "stereo demo: " << error.what() << '\n';
        return 1;
    }
}
