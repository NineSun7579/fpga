
#include "scheme2_verify.h"
#include "rknn_api.h"
#include <cstdio>
#include <cassert>
#include <stdexcept>
[[noreturn]] void scheme2Quarantine(const char* why) { throw std::runtime_error(why); }
struct ActualHelper {
    static std::vector<std::vector<uint8_t>> verifyNativeOutputs(rknn_context context,
                                                               const std::vector<rknn_tensor_attr>& attrs) {
        std::vector<rknn_output> outputs(attrs.size());
        for (size_t i = 0; i < outputs.size(); ++i) outputs[i].index = uint32_t(i);
        // want_float=0: exact allocated native bytes, no float tolerance.
        if (rknn_outputs_get(context, uint32_t(outputs.size()), outputs.data(), nullptr) != 0)
            scheme2Quarantine("native parity outputs_get failed");
        std::vector<std::vector<uint8_t>> result;
        for (size_t i = 0; i < outputs.size(); ++i) {
            if (!outputs[i].buf || !outputs[i].size || outputs[i].size != attrs[i].size) {
                fprintf(stderr, "[scheme2-verify-output] UNSUPPORTED output=%zu returned_bytes=%u attr_bytes=%u\n",
                        i, outputs[i].size, attrs[i].size);
                scheme2Quarantine("native packed output size unsupported; parity not passed");
            }
            const auto* data = static_cast<const uint8_t*>(outputs[i].buf);
            result.emplace_back(data, data + outputs[i].size);
        }
        if (rknn_outputs_release(context, uint32_t(outputs.size()), outputs.data()) != 0)
            scheme2Quarantine("native parity outputs_release failed");
        return result;
    }

};

std::vector<std::vector<uint8_t>> payloads;
int gets = 0, releases = 0;
bool wrongSize = false;
extern "C" int rknn_outputs_get(rknn_context, uint32_t count, rknn_output* outputs, rknn_output_extend*) {
    assert(count == payloads.size()); ++gets;
    for (size_t i=0;i<count;++i) {
        assert(outputs[i].index == i && outputs[i].want_float == 0 && outputs[i].is_prealloc == 0);
        outputs[i].buf = payloads[i].data();
        outputs[i].size = uint32_t(payloads[i].size()) + (wrongSize ? 1 : 0);
    }
    return 0;
}
extern "C" int rknn_outputs_release(rknn_context, uint32_t count, rknn_output* outputs) {
    assert(count == payloads.size()); ++releases;
    for (size_t i=0;i<count;++i) assert(outputs[i].buf == payloads[i].data());
    return 0;
}
int main() {
    for (unsigned count : {4,6,10}) {
        std::vector<rknn_tensor_attr> attrs(count); payloads.clear();
        for (unsigned i=0;i<count;++i) {
            attrs[i].size = 17+i*31; payloads.emplace_back(attrs[i].size, uint8_t(i+1));
        }
        const auto reference = ActualHelper::verifyNativeOutputs(1, attrs);
        assert(reference == payloads);
        payloads.back().back() ^= 1;
        const auto changed = ActualHelper::verifyNativeOutputs(2, attrs);
        assert(scheme2::mismatch(reference.back().data(), changed.back().data(), changed.back().size()) == changed.back().size()-1);
        wrongSize = true;
        bool rejected = false;
        try { ActualHelper::verifyNativeOutputs(2, attrs); }
        catch (const std::runtime_error&) { rejected = true; }
        assert(rejected); wrongSize = false;
    }
    assert(gets == 9 && releases == 6);
    std::puts("actual native helper: raw4/raw6/raw10 full-byte capture, final-byte corruption, unsupported sizes PASS");
}
