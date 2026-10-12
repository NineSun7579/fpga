#include "pcie_session.hpp"
#include <iomanip>
#include <memory>
int main() {
    std::unique_ptr<offload::PcieSession> session;
    try {
        session=std::make_unique<offload::PcieSession>();
        for (unsigned frame=0;frame<10;++frame) {
            const auto lease=session->claim_rgb(1);
            const auto raw=session->raw();
            const auto start=offload::Clock::now();
            const auto thumbnail=session->thumbnail();
            const auto ms=offload::elapsed(start,offload::Clock::now());
            for (size_t y=0;y<240;++y) for (size_t x=0;x<320;++x) {
                const auto source=(2*y*640+2*x)*2,destination=(y*320+x)*2;
                offload::require(raw[source]==thumbnail[destination] && raw[source+1]==thumbnail[destination+1],"Hardware thumbnail pixel mismatch");
            }
            session->release();
            std::cout<<std::setprecision(9)<<"{\"frame\":"<<frame<<",\"sequence\":"<<lease.sequence
                     <<",\"bytes_compared\":"<<thumbnail.size()<<",\"thumbnail_delivery_ms\":"<<ms<<",\"pass\":true}\n";
        }
        session->finish(); session.reset();
        return 0;
    } catch (const std::exception& e) {
        std::cerr<<e.what()<<std::endl;
        if (session) session->quarantine();
        return 2;
    }
}
