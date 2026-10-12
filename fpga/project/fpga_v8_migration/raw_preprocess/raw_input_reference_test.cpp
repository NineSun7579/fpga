#include "raw_input_reference.h"
#include <fstream>
#include <iostream>
#include <string>

namespace {
void require(bool success, const char* message) {
    if (!success) throw std::runtime_error(message);
}
std::vector<std::uint8_t> read_raw_hex(const char* path) {
    std::ifstream stream(path);
    require(bool(stream), "cannot open existing RAW fixture");
    std::vector<std::uint8_t> bytes;
    unsigned pixel;
    while (stream >> std::hex >> pixel) {
        require(pixel <= 65535, "RAW fixture has an invalid pixel");
        bytes.push_back(std::uint8_t(pixel)); bytes.push_back(std::uint8_t(pixel >> 8));
    }
    require(stream.eof(), "malformed RAW hex fixture");
    return bytes;
}
}

int main(int argc, char** argv) {
    try {
        require(argc == 4, "usage: raw_input_reference_test SOURCE_HEX EXPECTED_RGB_PIXELS_HEX ACTUAL_RTL_WORDS");
        const auto raw = read_raw_hex(argv[1]);
        require(!raw.empty() && raw.size() % fpga_v8_raw::raw_bytes == 0, "incomplete RAW frame fixture");
        std::vector<std::uint8_t> prepared;
        for (std::size_t offset = 0; offset < raw.size(); offset += fpga_v8_raw::raw_bytes) {
            const auto frame = fpga_v8_raw::prepare(raw.data() + offset, fpga_v8_raw::raw_bytes);
            prepared.insert(prepared.end(), frame.begin(), frame.end());
        }
        std::ifstream expected(argv[2]);
        require(bool(expected), "cannot open independently generated RGB fixture");
        std::size_t pixels = 0;
        unsigned pixel;
        while (expected >> std::hex >> pixel) {
            require(pixels < prepared.size() / 3 && pixel <= 0xffffff,
                    "RGB fixture has too many or invalid pixels");
            require(prepared[pixels * 3] == (pixel & 255) &&
                    prepared[pixels * 3 + 1] == ((pixel >> 8) & 255) &&
                    prepared[pixels * 3 + 2] == (pixel >> 16), "software/FPGA golden RGB mismatch");
            ++pixels;
        }
        require(expected.eof() && pixels * 3 == prepared.size(), "incomplete RGB fixture");

        std::ifstream actual(argv[3]);
        require(bool(actual), "cannot open retained actual RTL trace");
        std::string word;
        unsigned keep, last;
        unsigned long long cycle;
        std::size_t bytes_compared = 0, frames_compared = 0;
        while (actual >> word >> std::hex >> keep >> std::dec >> last >> cycle) {
            require(!word.empty() && word.size() <= 32 && keep == 65535 && last <= 1,
                    "invalid full-frame RTL word/KEEP/LAST");
            require(word.find_first_not_of("0123456789abcdefABCDEF") == std::string::npos,
                    "unknown or malformed actual RTL data");
            word.insert(0, 32 - word.size(), '0');
            require(bytes_compared + 16 <= prepared.size(), "too many actual RTL bytes");
            for (unsigned lane = 0; lane < 16; ++lane) {
                const auto byte = unsigned(std::stoul(word.substr(30 - lane * 2, 2), nullptr, 16));
                require(prepared[bytes_compared + lane] == byte, "software/actual RTL byte mismatch");
            }
            bytes_compared += 16;
            const bool at_frame_end = bytes_compared % fpga_v8_raw::input_bytes == 0;
            require(last == unsigned(at_frame_end), "software/actual RTL frame boundary mismatch");
            if (last) ++frames_compared;
        }
        require(actual.eof() && bytes_compared == prepared.size(), "incomplete actual RTL trace");
        require(frames_compared == raw.size() / fpga_v8_raw::raw_bytes, "RTL frame count mismatch");

        // Exhaust every source code. Expected component values use an explicit
        // finite codebook, independent of the bit-shift implementation.
        std::vector<std::uint8_t> exhaustive(fpga_v8_raw::raw_bytes);
        for (std::size_t i = 0; i < exhaustive.size() / 2; ++i) {
            exhaustive[i * 2] = std::uint8_t(i); exhaustive[i * 2 + 1] = std::uint8_t(i >> 8);
        }
        const auto result = fpga_v8_raw::prepare(exhaustive.data(), exhaustive.size());
        const std::uint8_t five_bits[32] = {0,8,16,24,33,41,49,57,66,74,82,90,99,107,115,123,
                                          132,140,148,156,165,173,181,189,198,206,214,222,231,239,247,255};
        const std::uint8_t six_bits[64] = {0,4,8,12,16,20,24,28,32,36,40,44,48,52,56,60,
            65,69,73,77,81,85,89,93,97,101,105,109,113,117,121,125,
            130,134,138,142,146,150,154,158,162,166,170,174,178,182,186,190,
            195,199,203,207,211,215,219,223,227,231,235,239,243,247,251,255};
        const auto base = fpga_v8_raw::pad_top * fpga_v8_raw::width * 3;
        for (std::size_t i = 0; i < exhaustive.size() / 2; ++i) {
            const auto q = unsigned(i & 65535);
            require(result[base + i * 3] == five_bits[q / 2048] &&
                    result[base + i * 3 + 1] == six_bits[(q / 32) % 64] &&
                    result[base + i * 3 + 2] == five_bits[q % 32], "exhaustive source code mismatch");
        }
        for (std::size_t i = 0; i < base; ++i) {
            require(result[i] == 114 && result[result.size() - i - 1] == 114, "padding mismatch");
        }
        unsigned invalid = 0;
        for (const auto size : {std::size_t(0), fpga_v8_raw::raw_bytes - 1, fpga_v8_raw::raw_bytes + 1}) {
            try { (void)fpga_v8_raw::prepare(exhaustive.data(), size); }
            catch (const std::invalid_argument&) { ++invalid; }
        }
        try { (void)fpga_v8_raw::prepare(nullptr, fpga_v8_raw::raw_bytes); }
        catch (const std::invalid_argument&) { ++invalid; }
        require(invalid == 4, "invalid RAW input accepted");
        std::cout << "RAW_INPUT_REFERENCE_PASS fixture_rgb_bytes=" << prepared.size()
                  << " actual_rtl_bytes=" << bytes_compared << " frames=" << frames_compared
                  << " exhaustive_codes=65536 invalid_inputs=" << invalid << '\n';
        return 0;
    } catch (const std::exception& e) {
        std::cerr << "RAW_INPUT_REFERENCE_FAIL " << e.what() << '\n'; return 1;
    }
}
