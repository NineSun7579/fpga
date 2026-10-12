#include "stereo_depth.h"
#include "stereo_pairing.h"

#include <opencv2/imgproc.hpp>

#include <cmath>
#include <cstdio>
#include <exception>
#include <iostream>
#include <limits>
#include <stdexcept>
#include <string>
#include <utility>
#include <unistd.h>

namespace stereo {
namespace {

void check(bool condition, const std::string& message) {
    if (!condition) {
        throw std::runtime_error(message);
    }
}

void near(double actual, double expected, double tolerance, const std::string& message) {
    check(std::isfinite(actual) && std::abs(actual - expected) <= tolerance,
          message + ": actual=" + std::to_string(actual) +
              ", expected=" + std::to_string(expected));
}

template <typename Function>
void rejects(Function&& function, const std::string& message) {
    try {
        function();
    } catch (const std::invalid_argument&) {
        return;
    }
    throw std::runtime_error("expected std::invalid_argument: " + message);
}

// Entirely fictional simulation fixture, never a board/camera calibration.
Calibration fixture(cv::Size size = cv::Size(640, 320)) {
    Calibration c;
    c.imageSize = size;
    c.K1 = (cv::Mat_<double>(3, 3) << 400.0, 0.0, size.width / 2.0,
             0.0, 400.0, size.height / 2.0, 0.0, 0.0, 1.0);
    c.K2 = c.K1.clone();
    c.D1 = cv::Mat::zeros(5, 1, CV_64F);
    c.D2 = c.D1.clone();
    c.R = cv::Mat::eye(3, 3, CV_64F);
    // X_right = R * X_left + T. Negative T.x gives positive left disparity.
    c.T = (cv::Mat_<double>(3, 1) << -0.1, 0.0, 0.0);
    return c;
}

std::pair<cv::Mat, cv::Mat> shiftedTexture(cv::Size size, int shift) {
    cv::RNG rng(0x3568);
    cv::Mat left(size, CV_8U), right(size, CV_8U);
    rng.fill(left, cv::RNG::UNIFORM, 0, 256);
    cv::GaussianBlur(left, left, cv::Size(3, 3), 0.6);
    rng.fill(right, cv::RNG::UNIFORM, 0, 256);
    // An object at x_left is seen at x_right = x_left - shift.
    left(cv::Rect(shift, 0, size.width - shift, size.height))
        .copyTo(right(cv::Rect(0, 0, size.width - shift, size.height)));
    return {left, right};
}

void verifyMask(const DepthResult& result) {
    check(result.disparity.type() == CV_32FC1 && result.validMask.type() == CV_8UC1,
          "result disparity/mask types");
    for (int y = 0; y < result.disparity.rows; ++y) {
        for (int x = 0; x < result.disparity.cols; ++x) {
            const float d = result.disparity.at<float>(y, x);
            if (result.validMask.at<unsigned char>(y, x)) {
                check(std::isfinite(d), "valid mask must not accept non-finite disparity");
                if (result.calibrated) {
                    const double z = result.fxPixels * result.baselineMeters /
                                     (d - result.cxOffsetPixels);
                    check(std::isfinite(z) && z > 0, "accepted depth must be positive and finite");
                }
            } else {
                check(std::isnan(d), "rejected disparity must be NaN");
            }
        }
    }
}

void verifyCalibrationFile() {
    char path[] = "/tmp/detview-stereo-calibration-XXXXXX";
    const int fd = ::mkstemp(path);
    check(fd >= 0, "create temporary calibration fixture");
    ::close(fd);
    struct Cleanup {
        const char* path;
        ~Cleanup() { std::remove(path); }
    } cleanup{path};
    const Calibration c = fixture();
    auto write = [&](const char* unit) {
        cv::FileStorage file(path, cv::FileStorage::WRITE | cv::FileStorage::FORMAT_YAML);
        check(file.isOpened(), "write calibration fixture");
        file << "image_width" << c.imageSize.width << "image_height" << c.imageSize.height;
        if (unit) file << "length_unit" << unit;
        file << "K1" << c.K1 << "D1" << c.D1 << "K2" << c.K2 << "D2" << c.D2
             << "R" << c.R << "T" << c.T;
    };
    write("m");
    const Calibration loaded = Calibration::load(path);
    near(cv::norm(loaded.T), 0.1, 1e-9, "YAML calibration baseline in meters");
    check(loaded.imageSize == c.imageSize, "YAML calibration image size");
    write("mm");
    rejects([&] { (void)Calibration::load(path); }, "millimeter calibration must not be mistaken for meters");
    write(nullptr);
    rejects([&] { (void)Calibration::load(path); }, "calibration must explicitly specify units");
}

void verifyFramePairing() {
    const auto crossed = correspondingSlots({100, 101}, {98, 99}, {99, 100}, {97, 98}, 0);
    check(crossed.left == 0 && crossed.right == 1,
          "trigger between tag reads must pair exposure 100, not newest 101/100");
    const auto absent = correspondingSlots({100, 101}, {98, 99}, {102, 103}, {96, 97}, 0);
    check(absent.left < 0 && absent.right < 0, "mismatched exposure counters must not pair");
    const auto wrapped = correspondingSlots({UINT32_MAX, 0}, {UINT32_MAX - 2, UINT32_MAX - 1},
                                            {UINT32_MAX, 0}, {UINT32_MAX - 2, UINT32_MAX - 1}, 0);
    check(wrapped.left == 1 && wrapped.right == 1, "common frame counters must support wraparound");
    const auto offset = correspondingSlots({10, 11}, {8, 9}, {5, 6}, {3, 4}, 5);
    check(offset.left == 1 && offset.right == 1, "explicit left-minus-right counter offset");
    const auto consumed = correspondingSlots({10, 11}, {10, 11}, {10, 11}, {8, 9}, 0);
    check(consumed.left < 0, "do not reuse an already consumed exposure");
}

} // namespace

int runSelfTest() {
    try {
        std::cout << "[simulation] stereo self-test: synthetic fixtures only\n";
        verifyCalibrationFile();
        verifyFramePairing();
        constexpr int shift = 20;
        constexpr double expectedDepth = 2.0; // 400 pixels * 0.1 meters / 20 pixels.
        const Calibration c = fixture();
        const auto pair = shiftedTexture(c.imageSize, shift);
        const cv::Rect fullRoi(160, 64, 320, 192);
        const cv::Rect halfRoi(80, 32, 160, 96);
        MatcherOptions options;
        options.scale = 1.0;

        DepthEngine uncalibrated(options);
        const DepthResult raw = uncalibrated.compute(pair.first, pair.second);
        verifyMask(raw);
        check(!raw.calibrated && raw.fxPixels == 0 && raw.baselineMeters == 0,
              "uncalibrated result must not carry metric geometry");
        cv::Mat expectedShiftMask;
        cv::inRange(raw.disparity(fullRoi), shift - 0.5, shift + 0.5, expectedShiftMask);
        check(cv::countNonZero(expectedShiftMask) > fullRoi.area() * 0.8,
              "actual uncalibrated SGBM must recover the known pixel shift");
        const RangeEstimate noMetric = DepthEngine::estimate(raw, fullRoi);
        check(!noMetric.valid && noMetric.meters == 0 && !noMetric.reason.empty(),
              "uncalibrated matching must never return meters");

        DepthEngine fullEngine(options, &c);
        const DepthResult full = fullEngine.compute(pair.first, pair.second);
        verifyMask(full);
        const RangeEstimate fullRange = DepthEngine::estimate(full, fullRoi, 20, 0.8);
        check(fullRange.valid, "full-resolution known depth: " + fullRange.reason);
        near(fullRange.medianDisparity, shift, 0.3, "actual full-resolution matched disparity");
        near(full.fxPixels, 400, 1e-5, "rectified full-resolution focal length");
        near(full.baselineMeters, 0.1, 1e-9, "baseline from rectified P2");
        near(fullRange.meters, expectedDepth, 0.04, "known full-resolution depth");
        check(cv::countNonZero(full.validMask(cv::Rect(0, 0, 32, full.validMask.rows))) == 0,
              "left invalid sentinel/search border must be rejected");
        check(cv::countNonZero(full.validMask(cv::Rect(608, 0, 32, full.validMask.rows))) == 0,
              "right matcher invalid sentinel must reject the far-right border");
        std::cout << "[PASS] real SGBM shift=" << fullRange.medianDisparity
                  << " px, depth=" << fullRange.meters << " m\n";

        options.scale = 0.5;
        DepthEngine halfEngine(options, &c);
        const DepthResult half = halfEngine.compute(pair.first, pair.second);
        verifyMask(half);
        check(half.left.size() == cv::Size(320, 160), "half-resolution output size");
        const RangeEstimate halfRange = DepthEngine::estimate(half, halfRoi, 20, 0.8);
        check(halfRange.valid, "half-resolution known depth: " + halfRange.reason);
        near(halfRange.medianDisparity, shift * 0.5, 0.3, "actual half-resolution matched disparity");
        near(half.fxPixels, full.fxPixels * 0.5, 1e-5, "scaled focal length");
        near(halfRange.meters, expectedDepth, 0.04, "known half-resolution depth");
        near(halfRange.meters, fullRange.meters, 0.04, "depth must survive resizing");

        // Rounding changes the actual resize ratios: derive K from output size.
        const Calibration odd = fixture(cv::Size(641, 321));
        const auto oddPair = shiftedTexture(odd.imageSize, shift);
        DepthEngine oddEngine(options, &odd);
        const DepthResult oddResult = oddEngine.compute(oddPair.first, oddPair.second);
        const RangeEstimate oddRange = DepthEngine::estimate(oddResult, halfRoi, 20, 0.8);
        check(oddRange.valid, "odd-size scaled fixture: " + oddRange.reason);
        near(oddRange.meters, expectedDepth, 0.05, "rounded resize must preserve depth");

        // Unequal principal points give a nonzero rectified disparity offset.
        Calibration offset = fixture();
        offset.K2.at<double>(0, 2) += 8.0;
        options.scale = 1.0;
        DepthEngine offsetEngine(options, &offset);
        const DepthResult offsetResult = offsetEngine.compute(pair.first, pair.second);
        const RangeEstimate offsetRange = DepthEngine::estimate(offsetResult, fullRoi, 20, 0.8);
        check(offsetRange.valid && std::abs(offsetResult.cxOffsetPixels) > 1,
              "principal-point offset fixture must yield a measurable offset");
        near(offsetRange.meters, 40.0 / 28.0, 0.04, "cxOffset correction using actual matching");
        std::cout << "[PASS] half/rounded scaling and nonzero principal-point offset\n";

        cv::Mat blank(c.imageSize, CV_8U, cv::Scalar(127));
        const DepthResult blankResult = fullEngine.compute(blank, blank);
        check(cv::countNonZero(blankResult.validMask) == 0, "blank pairs must have no accepted disparity");
        const RangeEstimate blankRange = DepthEngine::estimate(blankResult, fullRoi);
        check(!blankRange.valid && blankRange.meters == 0 && !blankRange.reason.empty(),
              "blank ROI must reject metric depth");
        for (const cv::Rect& roi : {cv::Rect(), cv::Rect(-1, 10, 20, 20),
                                    cv::Rect(630, 0, 20, 20), cv::Rect(0, 319, 20, 20)}) {
            const RangeEstimate invalid = DepthEngine::estimate(full, roi);
            check(!invalid.valid && invalid.meters == 0 && !invalid.reason.empty(),
                  "empty/outside ROI must be rejected");
        }
        check(!DepthEngine::estimate(full, cv::Rect(0, 0, 32, 32)).valid,
              "SGBM search border must not produce a range");

        DepthResult sparse = full;
        sparse.validMask = cv::Mat::zeros(full.validMask.size(), CV_8U);
        sparse.validMask(cv::Rect(200, 100, 4, 6)).setTo(255);
        const cv::Rect sparseRoi(200, 100, 10, 10);
        const RangeEstimate countFailure = DepthEngine::estimate(sparse, sparseRoi, 25, 0.1);
        const RangeEstimate fractionFailure = DepthEngine::estimate(sparse, sparseRoi, 20, 0.3);
        check(!countFailure.valid && countFailure.validPixels == 24 && countFailure.totalPixels == 100,
              "minimum valid count must reject sparse ROI");
        check(!fractionFailure.valid && fractionFailure.validPixels == 24 &&
                  fractionFailure.reason.find("fraction") != std::string::npos,
              "minimum valid fraction must reject sparse ROI");

        // Check non-finite/nonpositive filtering and median of depths (even N).
        DepthResult numeric;
        numeric.calibrated = true;
        numeric.fxPixels = 400;
        numeric.baselineMeters = 0.1;
        numeric.cxOffsetPixels = 2;
        numeric.disparity = (cv::Mat_<float>(2, 2) << 10, 20, 2,
                             std::numeric_limits<float>::infinity());
        numeric.validMask = cv::Mat(2, 2, CV_8U, cv::Scalar(255));
        const RangeEstimate numericRange = DepthEngine::estimate(numeric, cv::Rect(0, 0, 2, 2), 1, 0.5);
        check(numericRange.valid && numericRange.validPixels == 2 && numericRange.totalPixels == 4,
              "estimator must recheck non-finite/nonpositive depth");
        near(numericRange.medianDisparity, 15, 1e-9, "even-count median disparity");
        near(numericRange.meters, (40.0 / 8.0 + 40.0 / 18.0) / 2, 1e-9,
             "even-count median must operate on depth samples");
        std::cout << "[PASS] uncalibrated/blank/invalid ROI and count/fraction rejection\n";

        auto badCalibration = [&](auto mutate, const std::string& label) {
            Calibration bad = fixture();
            mutate(bad);
            rejects([&] { DepthEngine engine(options, &bad); }, label);
        };
        badCalibration([](Calibration& b) { b.imageSize.width = 0; }, "zero image width");
        badCalibration([](Calibration& b) { b.K1.at<double>(0, 0) = 0; }, "zero focal length");
        badCalibration([](Calibration& b) { b.K2.at<double>(1, 1) = -1; }, "negative focal length");
        badCalibration([](Calibration& b) { b.K1 = cv::Mat::eye(2, 2, CV_64F); }, "bad K shape");
        badCalibration([](Calibration& b) { b.K1.at<double>(0, 1) = 1; }, "unsupported skew");
        badCalibration([](Calibration& b) { b.D1 = cv::Mat::zeros(2, 2, CV_64F); }, "bad D shape");
        badCalibration([](Calibration& b) { b.D1 = cv::Mat::zeros(6, 1, CV_64F); }, "bad D length");
        badCalibration([](Calibration& b) { b.D1 = cv::Mat(); }, "missing distortion vector");
        badCalibration([](Calibration& b) { b.R.at<double>(0, 0) = 2; }, "nonorthogonal rotation");
        badCalibration([](Calibration& b) { b.R.at<double>(0, 0) = -1; }, "reflection rotation");
        badCalibration([](Calibration& b) { b.T.setTo(0); }, "zero baseline");
        badCalibration([](Calibration& b) { b.T = cv::Mat::zeros(2, 1, CV_64F); }, "bad T shape");
        badCalibration([](Calibration& b) {
            b.K1.at<double>(0, 0) = std::numeric_limits<double>::quiet_NaN();
        }, "NaN intrinsics");
        badCalibration([](Calibration& b) {
            b.T.at<double>(0) = -std::numeric_limits<double>::infinity();
        }, "infinite translation");
        badCalibration([](Calibration& b) { b.T = (cv::Mat_<double>(3, 1) << 0, -0.1, 0); },
                       "vertical stereo");
        badCalibration([](Calibration& b) { b.T.at<double>(0) = 0.1; }, "reversed camera order");

        auto badOptions = [&](auto mutate, const std::string& label) {
            MatcherOptions bad;
            mutate(bad);
            rejects([&] { DepthEngine engine(bad); }, label);
        };
        badOptions([](MatcherOptions& b) { b.numDisparities = 63; }, "nonmultiple disparity count");
        badOptions([](MatcherOptions& b) { b.numDisparities = 2048; }, "fixed-point sentinel overflow");
        badOptions([](MatcherOptions& b) { b.blockSize = 4; }, "even block size");
        badOptions([](MatcherOptions& b) { b.scale = 0; }, "zero scale");
        badOptions([](MatcherOptions& b) { b.scale = std::numeric_limits<double>::quiet_NaN(); }, "NaN scale");
        badOptions([](MatcherOptions& b) { b.lrMaxDiff = -1; }, "negative consistency threshold");
        rejects([&] { fullEngine.compute(cv::Mat(), pair.second); }, "empty input");
        rejects([&] { fullEngine.compute(pair.first, cv::Mat(20, 20, CV_8U)); }, "mismatched input size");
        rejects([&] { fullEngine.compute(pair.first, cv::Mat(c.imageSize, CV_8UC3)); }, "mismatched input type");
        rejects([&] { fullEngine.compute(cv::Mat(c.imageSize, CV_16U), cv::Mat(c.imageSize, CV_16U)); },
                "unsupported input depth");
        rejects([&] { fullEngine.compute(cv::Mat(160, 320, CV_8U), cv::Mat(160, 320, CV_8U)); },
                "calibration/input size mismatch");
        rejects([&] { DepthEngine::estimate(full, fullRoi, 0); }, "invalid minimum valid count");
        rejects([&] { DepthEngine::estimate(full, fullRoi, 20, 1.1); }, "invalid minimum valid fraction");

        cv::Mat bgrLeft, bgrRight;
        cv::cvtColor(pair.first, bgrLeft, cv::COLOR_GRAY2BGR);
        cv::cvtColor(pair.second, bgrRight, cv::COLOR_GRAY2BGR);
        const DepthResult color = fullEngine.compute(bgrLeft, bgrRight);
        check(color.left.type() == CV_8UC3 && DepthEngine::estimate(color, fullRoi).valid,
              "BGR inputs must preserve display type and support matching");
        std::cout << "[PASS] invalid calibration/options/input rejection and BGR input\n"
                     "[PASS] all offline stereo self-tests\n";
        return 0;
    } catch (const std::exception& e) {
        std::cerr << "[FAIL] stereo self-test: " << e.what() << '\n';
        return 1;
    }
}

} // namespace stereo
