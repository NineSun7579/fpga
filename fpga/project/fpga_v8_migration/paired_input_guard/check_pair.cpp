#include "paired_input_guard.hpp"
#include <fstream>
#include <iterator>
#include <iostream>
#include <stdexcept>
#include <string>
static std::vector<std::uint8_t> load(const char* path) {
    std::ifstream file(path,std::ios::binary);
    if (!file) throw std::runtime_error("fixture unavailable");
    return {std::istreambuf_iterator<char>(file),std::istreambuf_iterator<char>()};
}
static void require(bool condition) { if (!condition) throw std::runtime_error("pair guard failed"); }
int main(int argc,char** argv) {
    try {
        require(argc==9);
        capture_host::OwnedRawFrame raw;
        coop_host::OwnedFrame output;
        raw.bytes=load(argv[1]); output.bytes=load(argv[2]);
        require(raw.bytes.size()==614416);
        raw.bytes.resize(614400); raw.complete=output.complete=true;
        auto& r=raw.descriptor; auto& p=output.descriptor;
        r.sequence=static_cast<std::uint32_t>(std::stoul(argv[3]));
        r.generation=static_cast<std::uint32_t>(std::stoul(argv[4]));
        r.bank=static_cast<std::uint32_t>(std::stoul(argv[5]));
        r.token=std::stoull(argv[6],nullptr,16);
        p.bank=static_cast<std::uint32_t>(std::stoul(argv[7]));
        r.camera=static_cast<std::uint32_t>(std::stoul(argv[8]));
        r.address=r.bank ? 0x01a00000u : 0x01800000u; r.length=614400;
        p.address=p.bank ? 0x08200000u : 0x08000000u; p.length=1228800;
        p.sequence=r.sequence; p.generation=r.generation; p.camera=r.camera;
        p.source_bank=r.bank; p.source_address=r.address; p.token=r.token;
        const auto generation=r.generation;
        require(paired_input::certify(raw,output,generation).error==paired_input::Error::None);
        unsigned rejected=0;
        const auto bad=[&](const capture_host::OwnedRawFrame& a,const coop_host::OwnedFrame& b,
                           std::uint32_t g) {
            require(paired_input::certify(a,b,g).error==paired_input::Error::Identity); ++rejected;
        };
        bad(raw,output,0); bad(raw,output,generation+1);
        auto changed=output;
        ++changed.descriptor.sequence; bad(raw,changed,generation);
        changed=output; ++changed.descriptor.generation; bad(raw,changed,generation);
        changed=output; ++changed.descriptor.camera; bad(raw,changed,generation);
        changed=output; changed.descriptor.source_bank^=1; bad(raw,changed,generation);
        changed=output; changed.descriptor.source_address+=16; bad(raw,changed,generation);
        changed=output; changed.descriptor.token^=0x100000000ULL; bad(raw,changed,generation);
        changed=output; changed.complete=false; bad(raw,changed,generation);
        changed=output; changed.bytes.pop_back(); bad(raw,changed,generation);
        changed=output; changed.descriptor.address+=16; bad(raw,changed,generation);
        auto changed_raw=raw;
        changed_raw.complete=false; bad(changed_raw,output,generation);
        changed_raw=raw; changed_raw.descriptor.token=0;
        changed=output; changed.descriptor.token=0; bad(changed_raw,changed,generation);
        for (const std::size_t offset : {std::size_t(0),std::size_t(153600),std::size_t(1228799)}) {
            changed=output; changed.bytes[offset]^=1;
            const auto check=paired_input::certify(raw,changed,generation);
            require(check.error==paired_input::Error::Bytes && check.mismatch_offset==offset); ++rejected;
        }
        require(paired_input::certify(raw,output,generation).error==paired_input::Error::None);
        std::cout<<"PAIR_GUARD_PASS bytes=1228800 rejected="<<rejected<<'\n'; return 0;
    } catch(const std::exception& e) { std::cerr<<e.what()<<'\n'; return 1; }
}
