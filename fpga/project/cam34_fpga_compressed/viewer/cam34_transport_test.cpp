#include <QFile>
#include <QDir>
#include <QJsonDocument>
#include <QJsonObject>
#include <QElapsedTimer>
#include <QThread>
#include <QByteArray>
#include <cstring>
#include <memory>
#include <vector>
#include <cassert>
#include <cstdio>
#include "camera_dma.h"
#include "fair_dma.h"
static constexpr unsigned long F2H_CMD=5;
static constexpr int CAM_COUNT=6;
struct DmaOp{uint32_t current_len=0,offset_addr=0,cmd=0,ddr3_addr=0,total_length=0;};
static qint64 monotonicMs(){return 10000;}
class Probe{
public:
 std::shared_ptr<tdm::FairDmaMutex>dmaMutex_=std::make_shared<tdm::FairDmaMutex>();
 QByteArray storage=QByteArray(4*1024*1024,Qt::Uninitialized);uint8_t*rx_=reinterpret_cast<uint8_t*>(storage.data());
 bool m_wireEvidenceWritten[2]={};
 uint32_t quota=153600,ping=0x01000000,pong=0x01200000;std::vector<uint32_t>tags;std::vector<DmaOp>requests;
 bool corrupt=false;
 bool cameraTagLocked(uint32_t address,uint32_t&tag){tags.push_back(address);assert(address==ping+quota||address==pong+quota);tag=address==ping+quota?101:100;return true;}
 int ioctlTmo(unsigned long command,DmaOp*op,unsigned){assert(command==F2H_CMD);requests.push_back(*op);
  for(uint32_t i=0;i<quota;++i)rx_[op->offset_addr+i]=uint8_t(i*7);
  uint32_t t=corrupt?102:101;memcpy(rx_+op->offset_addr+quota,&t,4);return 0;
 }
    int cameraRead(int camera, uint32_t ping, uint32_t pong, uint32_t frameBytes,
                   bool delivered, uint32_t last, void* output, uint32_t& selected,
                   qint64& dmaNs, qint64& copyNs, qint64& capturedMs) {
        if (camera < 0 || camera >= CAM_COUNT) return -1;
        tdm::FairDmaGuard lock(dmaMutex_.get());
        uint32_t a = 0, b = 0;
        if (!cameraTagLocked(ping + frameBytes, a) || !cameraTagLocked(pong + frameBytes, b)) return -1;
        const int bank = tdm::newestCameraBank(a, b, delivered, last);
        if (bank < 0) return 0;
        selected = bank == 0 ? a : b;
        DmaOp op{};
        op.offset_addr = tdm::cameraSlotOffset(camera);
        op.ddr3_addr = bank == 0 ? ping : pong;
        op.total_length = frameBytes + 16;
        QElapsedTimer timer; timer.start();
        if (ioctlTmo(F2H_CMD, &op, 2) != 0) return -1;
        dmaNs = timer.nsecsElapsed();
        capturedMs = monotonicMs();
        const uint8_t* pixels = rx_ + op.offset_addr;
        uint32_t actual = 0;
        memcpy(&actual, pixels + frameBytes, sizeof(actual));
        if (actual != selected) return 2;
        if(camera==2 || camera==3){
            const QString dir=qEnvironmentVariable("DETVIEW_CAM34_EVIDENCE_DIR");
            if(!dir.isEmpty() && !m_wireEvidenceWritten[camera-2]){
                QFile proof(dir+QString("/cam%1_dma_identity.json").arg(camera+1));
                QDir().mkpath(dir);
                if(proof.open(QIODevice::WriteOnly)){
                    const QJsonObject row{{"camera",camera+1},{"frame_bytes",int(frameBytes)},
                        {"dma_bytes",int(op.total_length)},{"bank",bank},{"base",QString::number(op.ddr3_addr,16)},
                        {"tag",QString::number(selected)},{"host_ms",double(capturedMs)}};
                    proof.write(QJsonDocument(row).toJson());m_wireEvidenceWritten[camera-2]=true;
                }
            }
        }

        lock.unlock();
        timer.restart();
        tdm::copyCameraPixels(output, pixels, frameBytes);
        copyNs = timer.nsecsElapsed();
        return 1;
    }


};
int main(){
 for(int camera=0;camera<6;++camera){
  Probe p;p.quota=(camera==2||camera==3)?153600:614400;
  p.ping=0x00800000+uint32_t(camera)*0x400000;p.pong=p.ping+0x200000;
  QByteArray out(p.quota+16,char(0xcc));uint32_t tag=0;qint64 dma=0,copy=0,captured=0;
  int ret=p.cameraRead(camera,p.ping,p.pong,p.quota,false,0,out.data(),tag,dma,copy,captured);
  assert(ret==1&&tag==101&&p.requests.size()==1);
  const auto&op=p.requests[0];assert(op.total_length==p.quota+16&&op.ddr3_addr==p.ping&&op.offset_addr==tdm::cameraSlotOffset(camera));
  for(uint32_t i=0;i<p.quota;++i)assert(uint8_t(out[i])==uint8_t(i*7));
  for(int i=0;i<16;++i)assert(uint8_t(out[p.quota+i])==0xcc);
  printf("[PASS] camera=%d image=%u dma=%u slot=%u tag_offset=%u full_RAW_read=%d\n",camera+1,p.quota,op.total_length,op.offset_addr,p.quota,int(p.quota==614400));
  p.requests.clear();ret=p.cameraRead(camera,p.ping,p.pong,p.quota,true,101,out.data(),tag,dma,copy,captured);assert(ret==0&&p.requests.empty());
  out.fill(char(0xcc));p.corrupt=true;ret=p.cameraRead(camera,p.ping,p.pong,p.quota,false,0,out.data(),tag,dma,copy,captured);assert(ret==2);
  for(uint32_t i=0;i<p.quota;++i)assert(uint8_t(out[i])==0xcc);
 }
 puts("CAM34_ACTUAL_TRANSPORT_PASS");
}
