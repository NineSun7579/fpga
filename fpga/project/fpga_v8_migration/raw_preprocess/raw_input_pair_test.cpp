#include "raw_input_reference.h"
#include <fstream>
#include <iostream>
#include <iterator>
#include <string>

static std::vector<std::uint8_t> bytes(const char* path) {
    std::ifstream stream(path, std::ios::binary);
    if (!stream) throw std::runtime_error("cannot read retained pair");
    return {std::istreambuf_iterator<char>(stream), std::istreambuf_iterator<char>()};
}
int main(int argc, char** argv) {
    try {
        if (argc != 4) throw std::invalid_argument("usage: RAW_BANK_COPY PREPARED_INPUT SOURCE_SEQ");
        const auto raw = bytes(argv[1]), prepared = bytes(argv[2]);
        if (raw.size() != fpga_v8_raw::raw_bytes + 16 || prepared.size() != fpga_v8_raw::input_bytes)
            throw std::invalid_argument("invalid retained pair lengths");
        const auto sequence = std::stoull(argv[3]);
        if (!sequence || sequence > 0xffffffffULL) throw std::invalid_argument("invalid expected source sequence");
        std::uint32_t observed = 0;
        for (unsigned i = 0; i < 4; ++i)
            observed |= std::uint32_t(raw[fpga_v8_raw::raw_bytes + i]) << (i * 8);
        if (observed != sequence) throw std::runtime_error("RAW tag/source sequence differs");
        for (std::size_t i = fpga_v8_raw::raw_bytes + 4; i < raw.size(); ++i)
            if (raw[i]) throw std::runtime_error("RAW tag upper bytes differ");
        const auto software = fpga_v8_raw::prepare(raw.data(), fpga_v8_raw::raw_bytes);
        if (software != prepared) throw std::runtime_error("owned RAW/FPGA model-input bytes differ");
        std::cout << "RAW_PAIR_PASS sequence=" << sequence << " bytes=" << software.size() << '\n';
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "RAW_PAIR_FAIL " << error.what() << '\n'; return 1;
    }
}
