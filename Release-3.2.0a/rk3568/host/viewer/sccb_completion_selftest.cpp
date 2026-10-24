// Offline transport model; reuses the established held/drained runtime model.
#include "cam1_runtime_selftest.cpp"
#include <fstream>

int main(int argc,char** argv) {
    try {
        check(argc==3,"usage: selftest scenario output.log");
        const std::string scenario=argv[1];std::ofstream log(argv[2]);
        if(scenario=="ok") {
            std::vector<unsigned> bytes={0x3f,0x07};for(unsigned v=0;v<256;++v)bytes.push_back(v);
            for(unsigned ack=0;ack<2;++ack)for(unsigned byte:bytes) {
                sccb::Snapshot before,after;before.w[2]=9;
                after.w[0]=0x53430202;after.w[1]=1;
                after.w[2]=after.w[4]=after.w[7]=10;
                after.w[3]=after.w[5]=after.w[6]=0x01380600;
                const uint32_t words[]={byte|(ack<<8),10,byte|(ack<<8)|0x800u,10,byte,10};
                auto read=[&](uint32_t a,uint32_t& v){
                    v=a>=0x20000d00?after.w[(a-0x20000d00)/16]:words[(a-0x200009a0)/16];return true;
                };
                check(sccb::completionWitness(read,[](const std::string&){},0x20000900,0x20000d00,1,0x01380600,before,byte,2|ack),"exhaustive byte/ACK witness");
            }
        }
        Board board;board.camera=2;board.signature=0x43334d31;
        if(scenario=="c4") {board.camera=3;board.signature=0x43344d31;}
        if(scenario=="wrap")for(unsigned i:{1u,2u,4u,7u})board.mailbox.w[i]=0xffffffffu;
        auto io=board.io();io.completionWitness=true;
        uint64_t clock=0;unsigned witnessReads=0;bool collecting=false;
        auto transport=[&](const char* op,uint32_t a,uint32_t v,bool ok){
            char text[512];char raw[33];
            for(unsigned i=0;i<16;++i)std::snprintf(raw+2*i,3,"%02x",i<4?unsigned((v>>(8*i))&255):0);
            const auto start=++clock;const auto end=++clock;
            std::snprintf(text,sizeof(text),"SCCB_IO op=%s stage=start monotonic-ns=%llu addr=%08x value=%08x\nSCCB_IO op=%s stage=end monotonic-ns=%llu elapsed-ns=1 addr=%08x ok=%d raw16=%s\n",op,static_cast<unsigned long long>(start),a,v,op,static_cast<unsigned long long>(end),a,int(ok),raw);
            log<<text;
        };
        io.read=[&](uint32_t a,uint32_t& v){
            bool ok=true;const auto base=board.alias();const uint32_t page=board.camera==2?0x20000d00:0x20000e00;
            if(a>=base+0xa0&&a<=base+0xf0) {
                collecting=true;++witnessReads;
                const uint32_t id=board.mailbox.w[2];
                const uint32_t values[]={board.data,id,board.data|0x800u,id,board.data,id};
                v=values[(a-base-0xa0)/16];
                if(scenario=="native"&&a==base+0xa0)v^=1;
                if(scenario=="destination"&&a==base+0xc0)v^=1;
                if(scenario=="axi"&&a==base+0xe0)v^=1;
                if(scenario=="stale"&&a==base+0xf0)--v;
                if(scenario=="invalid"&&a==base+0xc0)v&=~0x800u;
                if(scenario=="fault"&&a==base+0xc0)v|=0x200u;
                if(scenario=="transport"&&a==base+0xb0)ok=false;
            } else {
                ok=board.read(a,v);
                if(scenario=="host"&&a==base+0x20)v^=0x10;
                if(scenario=="certificate"&&board.commands&&a==page+0x80)v^=1;
                if(scenario=="guard"&&collecting&&a==page+0x20)v^=1;
            }
            if((a>=page&&a<page+256)||(a>=base+0xa0&&a<=base+0xf0)||a==base+0x20||a==base+0x30)transport("F2H",a,v,ok);
            return ok;
        };
        io.write=[&](uint32_t a,uint32_t v){bool ok=board.write(a,v);if(a==board.alias()+16)transport("H2F",a,v,ok);return ok;};
        const auto originalReport=io.diagnostic;
        io.diagnostic=[&](const std::string& text){originalReport(text);log<<"CAM134_RUNTIME camera="<<board.camera+1<<' '<<text<<'\n';};
        cam1::Switch runtime(io,board.camera);uint8_t output[4]={};std::string error;
        const bool success=scenario=="write"?runtime.apply(true,false,error):runtime.readStartupGeometry(output,error);
        if(scenario=="write")check(success&&board.commands>100&&witnessReads==unsigned(board.commands)*6,"reads and writes collect witnesses");
        else if(scenario=="ok"||scenario=="wrap"||scenario=="c4")check(success&&board.commands==5&&witnessReads==30,"successful startup witnesses");
        else {
            check(!success&&board.commands==1&&witnessReads==6,"failure collects before next command");
            check(!runtime.readStartupGeometry(output,error)&&board.commands==1,"failure sticky command block");
        }
        log.flush();std::puts("SCCB_COMPLETION_SELFTEST_PASS");return 0;
    } catch(const std::exception& e) {std::fprintf(stderr,"FAIL %s\n",e.what());return 1;}
}
