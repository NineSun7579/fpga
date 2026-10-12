#include "mvp_decode.h"
#include <cstdio>
#include <limits>

namespace mvp {
int runSelfTest() {
    int failed = 0;
    auto check = [&](bool ok, const char* name) { if (!ok) { ++failed; std::fprintf(stderr,"[mvp-selftest] FAIL %s\n",name); } };
    auto near = [](float a,float b) { return std::fabs(a-b)<0.001f; };
    std::array<std::vector<float>,4> data{{std::vector<float>(64*24*8,-5),std::vector<float>(48*32*8,-5),std::vector<float>(2*24*8,0),std::vector<float>(2*32*8,0)}};
    std::array<const float*,4> ptr{{data[0].data(),data[1].data(),data[2].data(),data[3].data()}};
    LaneContract anchors; std::vector<Point> points;
    check(decodePoints(ptr,anchors,points) && points.empty(),"existence ties are absent");
    auto set = [&](int axis,int a,int lane,int bin) { const int count=axis==0?24:32; data[axis][bin*count*8+a*8+lane]=10; data[axis+2][count*8+a*8+lane]=1; };
    set(0,0,0,0); set(0,23,7,63); set(0,9,3,17);
    set(1,0,1,0); set(1,31,6,47); set(1,11,4,13);
    check(decodePoints(ptr,anchors,points) && points.size()==6,"NCHW grid/anchor/lane indexing");
    if(points.size()==6) {
        check(near(points[0].x,0)&&near(points[0].y,281.1799927f),"row first boundary and canonical +80");
        check(points[1].lane==3&&near(points[1].x,17.f/63*639)&&near(points[1].y,anchors.rows[9]+80),"interior row reference");
        check(points[2].lane==7&&near(points[2].x,639)&&near(points[2].y,535.0499878f),"row last boundary");
        check(points[3].lane==1&&near(points[3].x,anchors.cols[0])&&near(points[3].y,80),"column first boundary");
        check(points[4].lane==4&&near(points[4].y,13.f/47*479+80),"interior column reference");
        check(points[5].lane==6&&near(points[5].y,559),"column last boundary");
        check(!near(points[0].x,0.5f/64*640),"delivered independent reference is endpoint, not half-cell");
        // HDMI: 60 network padding rows + 80 canonical rows; active height 360.
        check(near((points[0].y-80),anchors.rows[0]),"camera inverse padding");
        check(near((points[0].y-140)*480/360,188.2399902f),"HDMI inverse pad and full-height scaling");
        check(points[3].y<140&&points[5].y>500,"HDMI padding points excluded by pane clipping");
    }
    // First grid bin wins a localization tie, exactly as both references.
    data[0][0*24*8+9*8+3]=10;
    check(decodePoints(ptr,anchors,points)&&near(points[1].x,0),"localization ties use first bin");
    data[2][24*8]=std::numeric_limits<float>::quiet_NaN();
    check(!decodePoints(ptr,anchors,points),"non-finite logits fail closed");
    std::vector<rknn_tensor_attr> attrs(10);
    const unsigned dims[10][3]={{64,60,80},{5,60,80},{64,30,40},{5,30,40},{64,15,20},{5,15,20},{64,24,8},{48,32,8},{2,24,8},{2,32,8}};
    for(int i=0;i<10;++i) { auto& a=attrs[i]; a.n_dims=4;a.fmt=RKNN_TENSOR_NCHW;a.dims[0]=1;a.n_elems=1; for(int d=0;d<3;++d) {a.dims[d+1]=dims[i][d];a.n_elems*=dims[i][d];} }
    check(validOutputs(attrs,Kind::Shared),"shared raw10 contract");
    check(validOutputs(std::vector<rknn_tensor_attr>(attrs.begin(),attrs.begin()+6),Kind::Detection),"detection raw6 contract");
    auto grouped=attrs;
    const int order[6]={0,2,4,1,3,5};
    for(int i=0;i<6;++i) grouped[i]=attrs[order[i]];
    check(validOutputs(grouped,Kind::Shared),"runtime box-first detection ordering");
    auto malformed=attrs; malformed[0].fmt=RKNN_TENSOR_NHWC;
    check(!validOutputs(malformed,Kind::Shared),"physical NHWC output rejected");
    malformed=attrs; malformed[0].n_elems=1;
    check(!validOutputs(malformed,Kind::Shared),"wrong element count rejected");
    malformed=attrs; malformed[2]=malformed[0];
    check(!validOutputs(malformed,Kind::Shared),"duplicate detection head rejected");
    check(validOutputs(std::vector<rknn_tensor_attr>(attrs.begin()+6,attrs.end()),Kind::Independent),"independent raw4 contract");
    std::swap(attrs[6],attrs[8]); check(!validOutputs(attrs,Kind::Shared),"reordered lane outputs rejected");
    std::swap(attrs[6],attrs[8]); attrs[1].dims[1]=16; check(!validOutputs(attrs,Kind::Shared),"traffic16 cannot masquerade as coarse five classes");
    std::fprintf(stderr,"[mvp-selftest] %s (%d failures)\n",failed?"FAIL":"PASS",failed);
    return failed?1:0;
}
}
#ifdef MVP_HOST_SELFTEST
int main() { return mvp::runSelfTest(); }
#endif
