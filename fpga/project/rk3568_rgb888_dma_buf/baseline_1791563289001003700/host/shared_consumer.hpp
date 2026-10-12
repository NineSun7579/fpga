#pragma once
#include "pcie_session.hpp"
#include "pango_zc_uapi.h"
#include <memory>

namespace offload {
class SharedConsumer {
    PcieSession& session_;
    int shared_fd_=-1;
    std::unique_ptr<BoundRknn> npu_;
    pz_lease lease_{};
public:
    SharedConsumer(const SharedConsumer&)=delete;
    SharedConsumer& operator=(const SharedConsumer&)=delete;
    SharedConsumer(PcieSession& session,const char* model) : session_(session) {
        pz_export_rx request{}; request.version=PZ_VERSION;
        shared_fd_=::ioctl(session_.fd(),PZ_EXPORT_RX,&request);
        require(shared_fd_>=0,"RX DMA-BUF export failed");
        try {
            npu_=std::make_unique<BoundRknn>(model,true);
            npu_->bind(shared_fd_,session_.mapping(),PZ_INPUT_OFFSET);
        } catch (...) {
            npu_.reset(); ::close(shared_fd_); shared_fd_=-1;
            throw;
        }
    }
    ~SharedConsumer() {
        // Do not falsely END an uncertain inference. Parent must reboot or
        // independently prove both producer and consumer retirement on faults.
        if (lease_.token) {
            std::cerr<<"Active NPU lease at teardown; retaining process resources\n";
            session_.quarantine();
        }
        npu_.reset();
        if (shared_fd_>=0) ::close(shared_fd_);
    }
    NativeResult complete() {
        require(!lease_.token,"NPU input slot still leased");
        lease_={}; lease_.version=PZ_VERSION;
        lease_.offset=PZ_INPUT_OFFSET; lease_.length=PZ_INPUT_BYTES;
        const auto start=Clock::now();
        require(::ioctl(session_.fd(),PZ_BEGIN,&lease_)==0 && lease_.token,"Cannot lease completed input slot");
        const auto began=Clock::now();
        auto result=npu_->bound();
        const auto end_start=Clock::now();
        require(::ioctl(session_.fd(),PZ_END,&lease_)==0,"Cannot retire NPU input slot");
        lease_.token=0;
        result.stages[0]+=elapsed(start,began)+elapsed(end_start,Clock::now());
        return result;
    }
};
} // namespace offload
