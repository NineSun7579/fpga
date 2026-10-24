#include "integrated_motion.h"
#include "startup_camera_geometry.h"
#include <cassert>
#include <cstdio>
#include <map>

namespace {
struct StartupDevice {
    std::array<runtime_camera::Geometry,runtime_camera::count> bound{};
    int calls=0, fail=-1;
    bool configureCameraGeometry(const runtime_camera::Geometry& geometry) {
        ++calls;
        if (!geometry.valid() || geometry.camera==fail) return false;
        bound[geometry.camera]=geometry;
        return true;
    }
};
void startupBindingRegression() {
    StartupDevice device;
    std::array<runtime_camera::Geometry,runtime_camera::count> geometries;
    for (int c=0;c<runtime_camera::count;++c) geometries[c]=runtime_camera::geometry(c);
    integrated_motion::Record record;
    record.hint.seq=10; record.hint.generation=1;
    record.hint.referenceValid=true;
    record.transportGeometry=640u<<16|480u; record.pixelBytes=614400;
    record.capabilities=CAM134_MOTION_AVAILABLE;
    integrated_motion::Observer observer;
    assert(!integrated_motion::usable(record,device.bound[0]));
    assert(!motion::fresh(observer.observe(record,device.bound[0],100,7),100,7));
    assert(runtime_camera::bindStartupGeometries(device,geometries)==runtime_camera::count);
    assert(device.calls==runtime_camera::count);
    for (int c=0;c<runtime_camera::count;++c) {
        assert(device.bound[c].valid() && device.bound[c].camera==c);
        assert(device.bound[c].generation==geometries[c].generation);
        if (c==2 || c==3) {
            assert(device.bound[c].width==320 && device.bound[c].height==240);
            assert(device.bound[c].pixelBytes==153600);
            auto thumbnail=record;
            thumbnail.transportGeometry=320u<<16|240u; thumbnail.pixelBytes=153600;
            assert(integrated_motion::usable(thumbnail,device.bound[c]));
        }
    }
    assert(integrated_motion::usable(record,device.bound[0]));
    assert(!motion::fresh(observer.observe(record,device.bound[0],200,7),200,7));
    ++record.hint.seq;
    auto evidence=observer.observe(record,device.bound[0],210,7);
    assert(motion::fresh(evidence,210,7));
    ++record.hint.seq;
    evidence=observer.observe(record,device.bound[0],220,7);
    assert(motion::fresh(evidence,220,7) && evidence.record.seq==record.hint.seq);
    assert(evidence.advancedMs==220 && observer.legacy.gaps==0);
    const auto decision=motion::decide(true,false,false,0,7,evidence,225,100,false);
    assert(!decision.request && decision.reason==motion::Reason::StaticDeferred);
    auto fallback=[&](const integrated_motion::Record& rejected,const runtime_camera::Geometry& geometry) {
        assert(!integrated_motion::usable(rejected,geometry));
        auto unavailable=observer.observe(rejected,geometry,230,7);
        assert(!motion::fresh(unavailable,230,7));
        const auto early=motion::decide(true,false,false,0,7,unavailable,230,200,false);
        assert(!early.request && early.reason==motion::Reason::Minimum);
        const auto due=motion::decide(true,false,false,0,7,unavailable,300,200,false);
        assert(due.request && due.reason==motion::Reason::Fallback);
    };
    fallback(record,runtime_camera::geometry(0,runtime_camera::Mode::Hd720,2));
    auto parked=record; parked.capabilities=8; fallback(parked,device.bound[0]);
    auto mismatch=record; mismatch.transportGeometry^=1; fallback(mismatch,device.bound[0]);
    mismatch=record; ++mismatch.pixelBytes; fallback(mismatch,device.bound[0]);
    for (int fail=0;fail<runtime_camera::count;++fail) {
        StartupDevice rejected; rejected.fail=fail;
        assert(runtime_camera::bindStartupGeometries(rejected,geometries)==fail);
        assert(rejected.calls==fail+1);
        assert(!rejected.bound[fail].valid());
    }
    StartupDevice invalid;
    geometries[3]=runtime_camera::Geometry{};
    assert(runtime_camera::bindStartupGeometries(invalid,geometries)==3 && invalid.calls==3);
    puts("STARTUP_GEOMETRY_BINDING_SELFTEST_PASS: unbound rejection, all six bindings, sequential C1 evidence, HD/park/mismatch fallback, fail closed");
}
}

int main() {
    startupBindingRegression();
    const std::map<uint32_t,uint32_t> identity{
        {CAM134_MOTION_MAGIC_ADDR,CAM134_MOTION_MAGIC},
        {CAM134_MOTION_GEOMETRY_ADDR,CAM134_MOTION_GEOMETRY},
        {CAM134_MOTION_CONFIG_ADDR,CAM134_MOTION_CONFIG},
        {CAM134_MOTION_EXTENSION_ADDR,CAM134_MOTION_EXTENSION}};
    auto readIdentity=[&](uint32_t address,uint32_t& value){value=identity.at(address);return true;};
    assert(integrated_motion::probe(readIdentity));
    for (const auto& field:identity) {
        assert(!integrated_motion::probe([&](uint32_t address,uint32_t& value){
            value=identity.at(address)^(address==field.first?1u:0u);return true;}));
        assert(!integrated_motion::probe([&](uint32_t address,uint32_t& value){
            value=identity.at(address);return address!=field.first;}));
    }
    // Values correspond to actual tb_metadata.sv assertions: separate source
    // sequences and retired RAW tags; C3 compressed descriptor, HD flags=4.
    for (unsigned mask=0;mask<8;++mask) for (int camera=0;camera<6;++camera) {
        const int bit=camera==0?0:camera==2?1:camera==3?2:-1;
        const bool hd=bit>=0 && (mask&(1u<<bit));
        const auto geometry=runtime_camera::geometry(camera,hd?runtime_camera::Mode::Hd720:runtime_camera::Mode::Default);
        std::array<uint32_t,16> words{};
        words[0]=camera<4?3:0; words[1]=camera<4&&!hd?1:0;
        words[10]=camera==0?88:camera==1?31:camera==2?44:camera==3?51:camera==4?72:91;
        words[11]=geometry.width<<16|geometry.height; words[12]=geometry.pixelBytes;
        words[13]=hd?4:camera<4?1:0; words[14]=3; words[15]=hd?1:0;
        unsigned selected=0,writes=0,reads=0;
        auto write=[&](uint32_t address,uint32_t selector) {
            assert(address==0x20000b00u); assert((selector>>8&7u)==unsigned(camera));
            selected=selector&15; ++writes; return true;
        };
        auto read=[&](uint32_t address,uint32_t& value) {
            ++reads; assert(address==0x20000b10u || address==0x20000b20u);
            value=address==CAM134_MOTION_GENERATION?17:words[selected];return true;
        };
        integrated_motion::Record record;
        assert(integrated_motion::capture(camera,record,write,read));
        assert(writes==17 && reads==18 && record.hint.generation==17);
        assert(record.rawTag==words[10] && record.rawTag!=record.hint.seq);
        assert(!(record.capabilities&CAM134_MOTION_SAME_RAW_FRAME));
        integrated_motion::Observer observer;
        auto first=observer.observe(record,geometry,100,7);
        assert(!motion::fresh(first,100,7));
        ++record.hint.seq;
        auto next=observer.observe(record,geometry,200,7);
        const bool eligible=camera<4&&!hd;
        assert(motion::fresh(next,200,7)==eligible);
        const auto early=motion::decide(true,false,false,camera,7,next,250,200,false);
        assert(!early.request && early.reason==motion::Reason::Minimum);
        assert(motion::decide(true,false,false,camera,7,next,300,200,false).request!=eligible);
        assert(motion::decide(false,false,false,camera,7,next,250,200,false).request);
        ++record.epoch;
        assert(!motion::fresh(observer.observe(record,geometry,260,7),260,7));
        ++record.hint.seq;
        next=observer.observe(record,geometry,270,7);
        if (eligible) {
            assert(motion::fresh(next,270,7));
            auto switched=geometry; ++switched.generation;
            assert(!motion::fresh(observer.observe(record,switched,275,7),275,7));
            auto stale=record; stale.transportGeometry^=1;
            assert(!motion::fresh(observer.observe(stale,geometry,280,7),280,7));
            assert(!motion::fresh(observer.observe(record,geometry,290,7),290,7));
            auto parked=record; parked.capabilities=8;
            assert(!integrated_motion::usable(parked,geometry));
            auto association=record; association.capabilities|=2;
            assert(!integrated_motion::usable(association,geometry));
        }
        const auto old=record;
        unsigned generations=0;
        assert(!integrated_motion::capture(camera,record,write,[&](uint32_t address,uint32_t& value) {
            if(address==CAM134_MOTION_GENERATION) value=++generations;
            else value=words[selected];
            return true;
        }));
        assert(record.hint.seq==old.hint.seq);
        for (unsigned fail=1;fail<=35;++fail) {
            unsigned calls=0;
            record=old;
            assert(!integrated_motion::capture(camera,record,
                [&](uint32_t address,uint32_t selector) {
                    if (++calls==fail) return false;
                    return write(address,selector);
                },[&](uint32_t address,uint32_t& value) {
                    if (++calls==fail) return false;
                    return read(address,value);
                }));
            assert(record.hint.seq==old.hint.seq && record.epoch==old.epoch);
        }
    }
    puts("INTEGRATED_MOTION_ABI_SELFTEST_PASS: strict probes, 16 words, 8 modes, HD/park fallback, epochs, no RAW association");
}
