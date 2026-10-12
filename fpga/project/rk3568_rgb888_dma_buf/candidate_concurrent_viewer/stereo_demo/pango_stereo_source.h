#pragma once

#include <chrono>
#include <cstdint>
#include <optional>
#include <opencv2/core.hpp>

namespace stereo {

struct StereoPair {
    cv::Mat left;
    cv::Mat right;
    uint32_t leftTag = 0;
    uint32_t rightTag = 0;
    // Host read timestamps describe sequential DMA reads, not exposure timing.
    double hostReadGapMs = 0;
    double acquisitionMs = 0;
};

class PangoStereoSource {
public:
    PangoStereoSource(int leftCamera, int rightCamera, std::optional<int32_t> tagOffset = std::nullopt);
    ~PangoStereoSource();
    PangoStereoSource(const PangoStereoSource&) = delete;
    PangoStereoSource& operator=(const PangoStereoSource&) = delete;
    bool poll(StereoPair& pair);

private:
    struct CameraState {
        int camera = 0;
        uint32_t previous[2] = {};
        uint32_t tags[2] = {};
        bool primed = false;
    };
    void read(uint32_t address, uint32_t length, void* destination);
    void tags(CameraState& state);
    int newestSlot(const CameraState& state) const;
    bool frame(CameraState& state, int slot, cv::Mat& image);
    void close();
    int fd_ = -1;
    int lockFd_ = -1;
    uint8_t* rx_ = nullptr;
    CameraState left_;
    CameraState right_;
    bool faulted_ = false;
    std::optional<int32_t> tagOffset_;
    std::chrono::steady_clock::time_point nextPoll_{};
};

} // namespace stereo
