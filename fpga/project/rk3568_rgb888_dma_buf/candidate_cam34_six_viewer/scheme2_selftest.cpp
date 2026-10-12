#include "fpga_infer_input.h"
#include "scheme2_verify.h"
#include "scheme2_contract.h"
#include "scheme2_uapi.h"
#include "camera_dma.h"
#include "inference_geometry.h"
#include "mvp_decode.h"
#include <cassert>
#include <cstdio>
#include <thread>
#include <vector>

int main() {
    static_assert(tdm::cameraScratchOffset + 4096 <= scheme2::Offset, "scratch below input");
    static_assert(scheme2::Offset + scheme2::SquareBytes <= scheme2::Window, "input fits RX");
    static_assert((scheme2::Offset & 4095) == 0, "RKNN import remains page aligned");
    assert(scheme2::enabled() == (std::getenv("EXPECT_SCHEME2_ON") != nullptr));
    assert(scheme2::verify() == (std::getenv("EXPECT_VERIFY_ON") != nullptr));
    assert(scheme2::verifyCount() >= 1 && scheme2::verifyCount() <= 10000);
    std::vector<uint8_t> raw565(scheme2::RawBytes);
    for (size_t i = 0; i < 640*480; ++i) {
        raw565[2*i] = uint8_t(i); raw565[2*i+1] = uint8_t(i >> 8);
    }
    const auto rectangle = scheme2::golden(raw565.data(), 480);
    const auto square = scheme2::golden(raw565.data(), 640);
    assert(rectangle.size() == 921600 && square.size() == 1228800);
    assert(std::all_of(square.begin(), square.begin()+153600, [](uint8_t b){return b==114;}));
    assert(std::all_of(square.end()-153600, square.end(), [](uint8_t b){return b==114;}));
    assert(scheme2::mismatch(rectangle.data(), square.data()+153600, rectangle.size()) == rectangle.size());
    // Cover every possible RGB565 value against independent integer expansion.
    for (size_t i = 0; i < 65536; ++i) {
        const unsigned r = i >> 11;
        assert(rectangle[3*i] == uint8_t(r * 8 + r / 4));
        const unsigned g = (i >> 5) & 63;
        // Bit replication intentionally differs from rounded linear scaling.
        assert(rectangle[3*i+1] == uint8_t(g * 4 + g / 16));
        const unsigned b = i & 31;
        assert(rectangle[3*i+2] == uint8_t(b * 8 + b / 4));
    }
    auto corrupt = rectangle; corrupt.back() ^= 1;
    assert(scheme2::mismatch(rectangle.data(), corrupt.data(), corrupt.size()) == corrupt.size()-1);
    corrupt = rectangle; corrupt[0] ^= 1;
    assert(scheme2::mismatch(rectangle.data(), corrupt.data(), corrupt.size()) == 0);
    scheme2::Admission gate;
    gate.arm(4, 7); assert(!gate.claim(4, 7)); // contexts not ready
    gate.publish({480,"raw6",1});
    gate.arm(4, 7);
    assert(!gate.claim(3, 7) && !gate.claim(4, 6));
    const auto firstSelection = gate.claim(4, 7);
    assert(firstSelection.height == 480 && firstSelection.model == "raw6" && firstSelection.revision == 1);
    gate.publish({480,"raw10",2}); // same height, new model revision while occupied
    gate.arm(4, 7); assert(!gate.claim(4, 7)); // slot cannot overwrite
    gate.retire(scheme2::Selection{640,"stale",1});
    gate.arm(4,8); const auto fresh = gate.claim(4,8);
    assert(fresh.model == "raw10" && fresh.revision == 2);
    gate.retire(); gate.arm(4, 8); gate.disarm(); assert(!gate.claim(4, 8));
    for (int round=0; round<100; ++round) {
        gate.arm(4,8); assert(gate.claim(4,8));
        std::atomic<bool> retired{false};
        std::thread rotation([&] { gate.retire(scheme2::Selection{640,"square",2}); retired=true; });
        std::thread capture([&] {
            while (!retired) gate.arm(4,8);
            gate.arm(4,8);
            const auto chosen=gate.claim(4,8);
            assert(chosen.height==640 && chosen.model=="square" && chosen.revision==2);
        });
        rotation.join(); capture.join();
        gate.retire(scheme2::Selection{480,"raw10",2});
    }
    for (int round = 0; round < 100; ++round) {
        gate.arm(2, round);
        std::atomic<int> winners{0};
        std::vector<std::thread> threads;
        for (int i = 0; i < 8; ++i) threads.emplace_back([&] { if (gate.claim(2, round)) ++winners; });
        for (auto& thread : threads) thread.join();
        assert(winners == 1); gate.retire();
    }
    int ends = 0;
    auto owner = std::make_shared<int>(123);
    std::weak_ptr<int> lifetime = owner;
    auto token = std::make_shared<scheme2::Input>();
    token->backing = owner; token->end = [&] { ++ends; };
    int begins = 0; token->begin = [&] { ++begins; };
    auto queued = token; owner.reset(); token.reset();
    assert(!lifetime.expired() && ends == 0); // bounded mailbox owns slot
    queued->consume(); queued->start(); assert(begins == 1);
    std::thread first([&] { queued->complete(); });
    std::thread second([&] { queued->complete(); });
    first.join(); second.join(); assert(ends == 1);
    queued.reset(); assert(lifetime.expired() && ends == 1);
    { scheme2::Input cancelled; cancelled.end = [&] { ++ends; }; }
    assert(ends == 1); // queue cancellation emits neither BEGIN nor END
    rknn_tensor_attr contract{};
    contract.n_dims=4; contract.dims[0]=1; contract.dims[1]=480; contract.dims[2]=640; contract.dims[3]=3;
    contract.size=contract.n_elems=921600; contract.type=RKNN_TENSOR_UINT8; contract.fmt=RKNN_TENSOR_NHWC;
    assert(scheme2::packedInput(contract,480));
    auto bad=contract; bad.type=RKNN_TENSOR_INT8; assert(scheme2::packedInput(bad,480));
    const auto unsignedUser=scheme2::userInput(bad);
    assert(unsignedUser.type==RKNN_TENSOR_UINT8 && unsignedUser.fmt==RKNN_TENSOR_NHWC && unsignedUser.pass_through==0);
    assert(bad.type==RKNN_TENSOR_INT8); // queried native attrs were not relabeled
    bad=contract; bad.type=RKNN_TENSOR_FLOAT16; assert(!scheme2::packedInput(bad,480));
    bad=contract; bad.w_stride=656; assert(!scheme2::packedInput(bad,480));
    bad=contract; bad.size_with_stride=contract.size+16; assert(!scheme2::packedInput(bad,480));
    bad=contract; bad.fmt=RKNN_TENSOR_NCHW; assert(!scheme2::packedInput(bad,480));
    bad=contract; bad.scale=0.5f; assert(!scheme2::sameTensor(contract,bad));

    QImage canonical(640, 640, QImage::Format_RGB888);
    canonical.fill(QColor(114, 114, 114));
    for (int y = 80; y < 560; ++y) for (int x = 0; x < 1920; ++x)
        canonical.scanLine(y)[x] = uint8_t(y * 7 + x * 3);
    for (int height : {480, 640}) {
        tdm::InferenceGeometry geometry; geometry.width = 640; geometry.height = height;
        const QImage expected = tdm::networkRgbFrame(canonical, geometry);
        assert(scheme2::bytes(height) == uint32_t(expected.sizeInBytes()));
        assert(std::memcmp(expected.constBits(), canonical.constBits() + scheme2::crop(height),
                           scheme2::bytes(height)) == 0);
        assert((scheme2::crop(height) & 15) == 0 && (scheme2::bytes(height) & 15) == 0);
    }
    assert(tdm::runCameraDmaSelfTest() == 0);
    assert(tdm::runInferenceGeometrySelfTest() == 0);
    assert(mvp::runSelfTest() == 0);
    std::puts("scheme2 ownership/cadence, crop DMA contract, baseline camera/geometry/MVP tests PASS");
}
