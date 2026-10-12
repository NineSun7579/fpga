#include "thumbnail_delivery.h"
#include "six_dma_layout.h"
#include <vector>
#include <cstring>
#include <cstdio>
#include <algorithm>
constexpr int F2H_CMD = 1;
struct DmaOp { uint32_t offset_addr=0, ddr3_addr=0, total_length=0; };
struct Dev {
    std::vector<uint8_t> mapping = std::vector<uint8_t>(sixdma::Allocation, 0xa7);
    uint8_t* rx_ = mapping.data();
    int calls=0, fault=0;
    int ioctlTmo(int command, DmaOp* op, int timeout,
                 thumbnail::StageStats::Io category = thumbnail::StageStats::Other) {
        ++calls;
        if (category != thumbnail::StageStats::Snapshot ||
            command != F2H_CMD || timeout != 2 || op->ddr3_addr != thumbnail::Base ||
            op->offset_addr != sixdma::Metadata || op->total_length != thumbnail::SnapshotBytes) return -1;
        if (fault == 1) return -1;
        for (uint32_t i=0; i<op->total_length; ++i) rx_[op->offset_addr+i]=uint8_t(i*13);
        if (fault == 2) op->offset_addr = sixdma::SharedInput;
        if (fault == 3) op->ddr3_addr += 16;
        if (fault == 4) op->total_length -= 16;
        return 0;
    }
};
struct Transport { Dev& dev;
        bool readSnapshot(void* output, size_t count) {
            if (!output || count != thumbnail::SnapshotBytes ||
                !sixdma::scratchRange(sixdma::Metadata, count)) return false;
            DmaOp op{};
            op.offset_addr = sixdma::Metadata;
            op.ddr3_addr = thumbnail::Base;
            op.total_length = uint32_t(count);
            if (dev.ioctlTmo(F2H_CMD, &op, 2, thumbnail::StageStats::Snapshot) != 0) return false;
            if (op.offset_addr != sixdma::Metadata || op.ddr3_addr != thumbnail::Base ||
                op.total_length != count) return false;
            std::memcpy(output, dev.rx_ + sixdma::Metadata, count);
            return true;
        }
};
int main() {
 int failures=0, cases=0;
 auto expect=[&](bool ok) {++cases; if(!ok) ++failures;};
 for(int fault=0; fault<=4; ++fault) {
  Dev dev; dev.fault=fault; Transport io{dev};
  std::vector<uint8_t> out(thumbnail::SnapshotBytes+32,0xa5);
  bool ok=io.readSnapshot(out.data()+16,thumbnail::SnapshotBytes);
  expect(ok == (fault==0) && dev.calls==1);
  expect(std::all_of(out.begin(),out.begin()+16,[](uint8_t b){return b==0xa5;}) &&
         std::all_of(out.end()-16,out.end(),[](uint8_t b){return b==0xa5;}));
  for(size_t i=0;i<thumbnail::SnapshotBytes;++i)
   expect(out[i+16]==(fault==0?uint8_t(i*13):0xa5));
  expect(std::all_of(dev.mapping.begin()+sixdma::SharedInput,dev.mapping.end(),[](uint8_t b){return b==0xa7;}));
  expect(std::all_of(dev.mapping.begin(),dev.mapping.begin()+sixdma::Metadata,[](uint8_t b){return b==0xa7;}));
  if(ok) {std::memset(dev.rx_+sixdma::Metadata,0,thumbnail::SnapshotBytes); expect(out[17]==13);}
 }
 Dev dev; Transport io{dev}; uint32_t out[76]{};
 expect(!io.readSnapshot(nullptr,thumbnail::SnapshotBytes));
 expect(!io.readSnapshot(out,thumbnail::SnapshotBytes-16));
 expect(!io.readSnapshot(out,thumbnail::SnapshotBytes+16));
 expect(dev.calls==0);
 std::printf("SIX_BATCH_TRANSPORT_%s cases=%d failures=%d\n",failures?"FAIL":"PASS",cases,failures);
 return failures?2:0;
}
