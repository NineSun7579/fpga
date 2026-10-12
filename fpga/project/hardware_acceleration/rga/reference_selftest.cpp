#include "reference.hpp"
#include <fstream>
#include <iostream>

using namespace rga_probe;
static void require(bool value, const char* message) {
    if (!value) throw std::runtime_error(message);
}
int main(int argc, char** argv) {
    try {
        const Bytes raw = tiled_colors();
        Bytes ref = golden(raw, false);
        for (unsigned v = 0; v < 65536; ++v) {
            // Independent division-based expansion, including endpoint values.
            const unsigned r = v / 2048, g = (v / 32) % 64, b = v % 32;
            require(ref[3*v] == r*8+r/4 && ref[3*v+1] == g*4+g/16 && ref[3*v+2] == b*8+b/4,
                    "CPU expansion mismatch");
        }
        require(word_le(raw.data()+2*0xf800) == 0xf800 && ref[3*0xf800] == 255 &&
                ref[3*0xf800+2] == 0, "endianness/R5top mismatch");
        require(calibrate(raw, ref.data()).correction == Correction::exact, "exact calibration");
        Bytes shifted(ref.size());
        for (size_t i = 0; i < raw.size()/2; ++i) {
            const uint16_t v = word_le(raw.data()+2*i);
            shifted[3*i] = uint8_t((v >> 11) << 3);
            shifted[3*i+1] = uint8_t(((v >> 5) & 63) << 2);
            shifted[3*i+2] = uint8_t((v & 31) << 3);
        }
        const auto shift_cal = calibrate(raw, shifted.data());
        require(shift_cal.correction == Correction::replicate_or, "left-shift gate");
        Bytes shift_tail(shifted.begin(), shifted.begin()+31*3);
        correct(shift_tail.data(), 31, shift_cal);
        require(std::equal(shift_tail.begin(), shift_tail.end(), ref.begin()), "OR vector/scalar tail");
        correct(shifted.data(), raw.size()/2, shift_cal);
        require(shifted == ref, "OR correction mismatch");
        Bytes rounded(ref.size());
        for (size_t i = 0; i < raw.size()/2; ++i) {
            const uint16_t v = word_le(raw.data()+2*i);
            rounded[3*i] = uint8_t(((v >> 11) * 255 + 15) / 31);
            rounded[3*i+1] = uint8_t((((v >> 5) & 63) * 255 + 31) / 63);
            rounded[3*i+2] = uint8_t(((v & 31) * 255 + 15) / 31);
        }
        const auto round_cal = calibrate(raw, rounded.data());
        require(round_cal.correction == Correction::lut, "bounded LUT gate");
        Bytes lut_tail(rounded.begin(), rounded.begin()+31*3);
        correct(lut_tail.data(), 31, round_cal);
        require(std::equal(lut_tail.begin(), lut_tail.end(), ref.begin()), "LUT vector/scalar tail");
        Bytes unseen(rounded.begin(), rounded.begin()+31*3); unseen[0] = 1;
        bool unseen_rejected = false;
        try { correct(unseen.data(), 31, round_cal); }
        catch (const std::runtime_error&) { unseen_rejected = true; }
        require(unseen_rejected, "unknown LUT byte accepted");
        correct(rounded.data(), raw.size()/2, round_cal);
        require(rounded == ref, "LUT correction mismatch");
        Bytes wrong = ref;
        for (size_t i = 0; i < raw.size()/2; ++i) std::swap(wrong[3*i], wrong[3*i+2]);
        require(calibrate(raw, wrong.data()).correction == Correction::rejected, "R/B swap accepted");
        wrong = ref; wrong[3*65536+1] ^= 1;
        require(calibrate(raw, wrong.data()).correction == Correction::rejected,
                "spatially inconsistent expansion accepted");
        wrong = ref;
        for (size_t i = 0; i < raw.size()/2; ++i) {
            const unsigned red = word_le(raw.data()+2*i) >> 11;
            if (red == 15 || red == 16) wrong[3*i] = 128;
        }
        require(calibrate(raw, wrong.data()).correction == Correction::rejected,
                "bounded but lossy channel mapping accepted");
        const Bytes missing(RAW_BYTES, 0), black(RGB_BYTES, 0);
        require(calibrate(missing, black.data()).correction == Correction::rejected,
                "incomplete color calibration accepted");
        Bytes model = golden(raw, true);
        require(padding_ok(model.data()), "letterbox padding");
        require(std::memcmp(model.data()+size_t(PAD_Y)*W*3, ref.data(), RGB_BYTES) == 0,
                "letterbox changed full frame");
        model[0] = 113; require(!padding_ok(model.data()), "padding corruption accepted");
        // Odd pixel count and unaligned byte addresses exercise scalar tails.
        Bytes unaligned(raw.size()+1); std::copy(raw.begin(), raw.end(), unaligned.begin()+1);
        Bytes tail(31*3); convert(unaligned.data()+1, tail.data(), 31);
        require(std::equal(tail.begin(), tail.end(), ref.begin()), "unaligned/tail conversion");
        std::cout << "{\"kind\":\"cpu_reference_selftest\",\"passed\":true,"
                  << "\"hardware_executed\":false,\"exhaustive_colors\":65536,"
                  << "\"raw_fnv1a64\":\"" << fnv1a(raw) << "\",\"rgb_fnv1a64\":\""
                  << fnv1a(ref) << "\",\"model_fnv1a64\":\"" << fnv1a(golden(raw,true)) << "\"}\n";
        // Optional real fixtures are read as regular files only.
        for (int i = 1; i < argc; ++i) {
            std::ifstream f(argv[i], std::ios::binary);
            if (!f) throw std::runtime_error("fixture open failed");
            Bytes bytes((std::istreambuf_iterator<char>(f)), {});
            const auto rgb = golden(bytes, false), boxed = golden(bytes, true);
            require(padding_ok(boxed.data()), "fixture padding");
            require(std::memcmp(boxed.data()+size_t(PAD_Y)*W*3, rgb.data(), RGB_BYTES) == 0,
                    "fixture full image changed");
            std::cout << "{\"kind\":\"cpu_fixture\",\"index\":" << i
                      << ",\"raw_fnv1a64\":\"" << fnv1a(bytes)
                      << "\",\"rgb_fnv1a64\":\"" << fnv1a(rgb)
                      << "\",\"model_fnv1a64\":\"" << fnv1a(boxed) << "\"}\n";
        }
        return 0;
    } catch (const std::exception& e) { std::cerr << e.what() << '\n'; return 1; }
}
