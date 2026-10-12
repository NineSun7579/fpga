#include "pcie_session.hpp"
#include <array>
#include <algorithm>
#include <iomanip>
#include <memory>
#include <cstdlib>

int main(int argc, char** argv) {
    // Parse before constructing a session: --help never opens a device.
    unsigned frames=10;
    std::vector<unsigned> cameras{0,1,2,3,4,5};
    if (argc==2 && std::string(argv[1])=="--help") {
        std::cout<<"Usage: thumbnail_six_parity [frames-per-camera-per-output-bank >= 10]\n"
                    "Requires exclusive root device ownership; tests 6 cameras x 2 output banks.\n"
                    "OFFLOAD_PARITY_CAMERAS selects physical cameras, e.g. 1,2,3,4.\n";
        return 0;
    }
    try {
        if (const char* selection=std::getenv("OFFLOAD_PARITY_CAMERAS")) {
            const std::string text=selection;
            cameras.clear();
            offload::require(!text.empty() && text.size()%2==1,"Invalid camera list");
            for (size_t index=0;index<text.size();index+=2) {
                offload::require(text[index]>='1' && text[index]<='6' &&
                                 (index==0 || text[index-1]==','),"Invalid camera list");
                const unsigned camera=unsigned(text[index]-'1');
                offload::require(std::find(cameras.begin(),cameras.end(),camera)==cameras.end(),
                                 "Duplicate camera");
                cameras.push_back(camera);
            }
        }
        offload::require(argc<=2,"Usage: thumbnail_six_parity [frames >= 10]");
        if (argc==2) {
            const std::string text=argv[1];
            offload::require(!text.empty() && text.find_first_not_of("0123456789")==std::string::npos,
                             "Frames must be an integer >= 10");
            const auto value=std::stoul(text);
            offload::require(value>=10 && value<=100000,"Frames must be in [10,100000]");
            frames=static_cast<unsigned>(value);
        }
    } catch (const std::exception& e) { std::cerr<<e.what()<<'\n'; return 2; }

    std::unique_ptr<offload::PcieSession> session;
    try {
        session=std::make_unique<offload::PcieSession>();
        offload::require((session->reg(0xa0)&7)==7 && session->reg(0xf0)==0x3f,
                          "Integrated six-camera contract required");
        const bool snapshots=std::getenv("OFFLOAD_VERIFY_SNAPSHOTS")!=nullptr;
        auto verify_snapshot=[&]() {
            if (!snapshots) return;
            const auto before=session->register_snapshot();
            for (size_t index=0;index<before.size();++index)
                offload::require(before[index]==session->reg(uint32_t(index*16)),
                                 "Snapshot/scalar register mismatch");
            offload::require(session->register_snapshot()==before,"Frozen snapshot changed");
        };
        std::array<uint32_t,6> last{};
        std::array<bool,6> seen{};
        auto generation=session->reg(0x50);
        unsigned passed=0;
        for (unsigned camera:cameras) for (unsigned bank=0;bank<2;++bank) {
            auto freshness_deadline=offload::Clock::now()+std::chrono::seconds(3);
            for (unsigned frame=0;frame<frames;) {
                const auto lease=session->claim_rgb(1,camera,bank);
                offload::require(lease.published && lease.generation==uint32_t(generation+1),
                                 "Publication/generation mismatch");
                generation=lease.generation;
                const auto delta=uint32_t(lease.sequence-last[camera]);
                if (seen[camera] && delta==0) {
                    session->release();
                    offload::require(offload::Clock::now()<freshness_deadline,
                                     "No fresh published frame within three seconds");
                    std::this_thread::sleep_for(std::chrono::milliseconds(5));
                    continue;
                }
                offload::require(!seen[camera] || delta<0x80000000u,"Source sequence moved backwards");
                verify_snapshot();
                const auto raw=session->raw();
                const auto start=offload::Clock::now();
                const auto thumbnail=session->thumbnail();
                const auto ms=offload::elapsed(start,offload::Clock::now());
                offload::require(raw.size()==640*480*2 && thumbnail.size()==320*240*2,
                                 "Payload size mismatch");
                for (size_t y=0;y<240;++y) for (size_t x=0;x<320;++x) {
                    const auto source=(2*y*640+2*x)*2, destination=(y*320+x)*2;
                    if (raw[source]!=thumbnail[destination] || raw[source+1]!=thumbnail[destination+1])
                        throw std::runtime_error("Thumbnail byte mismatch camera="+std::to_string(camera)+
                            " bank="+std::to_string(bank)+" x="+std::to_string(x)+" y="+std::to_string(y));
                }
                // Recheck RAW payload and metadata after thumbnail DMA, while still frozen.
                offload::require(session->raw()==raw,"Frozen RAW payload changed during thumbnail delivery");
                verify_snapshot();
                session->release();
                seen[camera]=true; last[camera]=lease.sequence; ++passed;
                std::cout<<std::setprecision(9)<<"{\"camera\":"<<camera<<",\"output_bank\":"<<bank
                         <<",\"frame\":"<<frame<<",\"generation\":"<<lease.generation
                         <<",\"sequence\":"<<lease.sequence<<",\"published\":true,\"source\":"<<lease.source
                         <<",\"destination\":"<<lease.destination<<",\"bytes_compared\":"<<thumbnail.size()
                         <<",\"thumbnail_delivery_ms\":"<<ms<<",\"snapshot_parity\":"<<(snapshots?"true":"null")<<",\"pass\":true}"<<std::endl;
                ++frame;
                freshness_deadline=offload::Clock::now()+std::chrono::seconds(3);
            }
        }
        session->finish(); session.reset();
        std::cout<<"{\"summary\":true,\"cameras\":"<<cameras.size()<<",\"output_banks\":2,\"frames_per_camera_per_bank\":"
                 <<frames<<",\"frames_passed\":"<<passed<<",\"pass\":true}"<<std::endl;
        return 0;
    } catch (const std::exception& e) {
        std::cerr<<"Parity failed: "<<e.what()<<std::endl;
        if (session && !session->close_if_safe()) session->quarantine();
        return 2;
    }
}
