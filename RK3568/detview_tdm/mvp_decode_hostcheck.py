"""Compile verbatim production DFL methods and point decoder without Qt/NPU."""
import argparse
from pathlib import Path
import re
import subprocess
import sys
import tempfile

def block(text, marker):
    start = text.index(marker)
    opening = text.index("{", start)
    tokens = re.finditer(r'//[^\n]*|/\*.*?\*/|"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|[{}]',text[opening:],re.S)
    depth = 0
    for token in tokens:
        if token.group() == "{": depth += 1
        elif token.group() == "}":
            depth -= 1
            if depth == 0: return text[start:opening+token.end()]
    raise ValueError(marker)

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--cxx",default="g++")
    parser.add_argument("--package",type=Path)
    parser.add_argument("--round1-package",type=Path)
    args=parser.parse_args()
    root=Path(__file__).resolve().parent
    source=(root/"main.cpp").read_text(encoding="utf-8")
    geometry=(root/"inference_geometry.h").read_text(encoding="utf-8")
    types=(root/"vision_types.h").read_text(encoding="utf-8")
    harness=r'''
#include <algorithm>
#include <atomic>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <limits>
#include <string>
#include <vector>
#include "mvp_decode.h"
#include "mvp_round1_policy.h"
using qint64=int64_t;
using QString=std::string;
using QStringList=std::vector<std::string>;
template<class T> struct QVector:std::vector<T> {
 using std::vector<T>::vector;
 void append(const T& v){this->push_back(v);}
 int size()const{return int(std::vector<T>::size());}
};
static const int MODEL_W=640;
static const int MODEL_H=640;
static const float IOU_THRESH=0.45f;
using QRgb=uint32_t;
inline QRgb qRgba(int r,int g,int b,int a){return (uint32_t(a)<<24)|(r<<16)|(g<<8)|b;}
inline int qAlpha(QRgb p){return int(p>>24);}
struct QImage {
 enum Format {Format_ARGB32};
 int w=0,h=0;std::vector<QRgb> storage;
 QImage()=default;
 QImage(int width,int height,Format):w(width),h(height),storage(width*height){}
 bool isNull()const{return storage.empty();}
 unsigned char* scanLine(int y){return reinterpret_cast<unsigned char*>(storage.data()+y*w);}
 QRgb pixel(int x,int y)const{return storage[y*w+x];}
};
'''
    harness+=block(source,"static QStringList trafficlightNames()")+"\n"
    harness+=block(source,"static QStringList mvpNames()")+"\n"
    harness+=block(types,"struct Detection {")+";\nnamespace tdm {\n"
    harness+=block(geometry,"struct InferenceGeometry {")+";\n"
    harness+=block(geometry,"inline bool queryInputGeometry(")+"\n"
    harness+=block(geometry,"template<class Detections>")+"\n}\n"
    hdmi=(root/"hdmi_view.h").read_text(encoding="utf-8")
    harness+="namespace tdm {\n"+"\n".join(re.findall(r"constexpr int [^;]+;",hdmi))+"\n}\n"
    harness+="static_assert(tdm::hdmiModelPad==140 && tdm::hdmiAnalyticsHeight==360,\"MVP HDMI transform test must match production\");\n"
    harness+="struct InferenceThread {\n"+block(source,"struct CandD {")+";\n"
    methods=["static bool selfTestDfl(","static bool selfTestTrafficlight()","static bool selfTestMvp()","static bool selfTestRound1()",
             "static QImage decodeLaneMask(","static bool selfTestLane()",
             "static bool validTrafficlightOutputs(","static float sigmoidf(","static void nmsAppend(",
             "bool tryDecodeDfl(","QVector<Detection> decode("]
    harness+="\n".join(block(source,marker) for marker in methods)
    harness+=r'''
 int m_nc=1; bool m_trafficlight=false,m_mvpDetect=false,m_xyxy=false;
 mvp::Round1Policy m_mvpPolicy;
 tdm::InferenceGeometry m_geometry; std::atomic<float> m_conf{0.25f};
};
int main() {
 bool ok=mvp::runSelfTest()==0;
 ok=InferenceThread::selfTestMvp()&&ok;
 ok=InferenceThread::selfTestRound1()&&ok;
 ok=InferenceThread::selfTestTrafficlight()&&ok;
 ok=InferenceThread::selfTestDfl()&&ok;
 ok=InferenceThread::selfTestDfl(8,29)&&ok;
 ok=InferenceThread::selfTestLane()&&ok;
 std::fprintf(stderr,ok?"MVP_PRODUCTION_HOSTCHECK_PASS\n":"MVP_PRODUCTION_HOSTCHECK_FAIL\n");
 return ok?0:1;
}
'''
    with tempfile.TemporaryDirectory(prefix=".mvp-hostcheck-",dir=root) as tmp:
        directory=Path(tmp); cpp=directory/"hostcheck.cpp"; exe=directory/"hostcheck.exe"
        cpp.write_text(harness,encoding="utf-8")
        command=[args.cxx,"-std=c++17","-O2","-Wall","-Wextra","-I",str(root),str(cpp),
                 str(root/"mvp_decode_selftest.cpp"),"-o",str(exe)]
        if sys.platform=="win32": command.append("-Wl,--stack,16777216")
        subprocess.run(command,check=True)
        subprocess.run([str(exe)],check=True)
        if args.package:
            reference_check(args,root,directory)
        if args.round1_package:
            round1_reference_check(args,root,directory,source,types)

def round1_reference_check(args,root,directory,source,types):
    import hashlib
    import importlib.util
    import json
    import numpy as np
    package=args.round1_package
    manifest=json.loads((package/"deployment_manifest.json").read_text(encoding="utf-8-sig"))
    model=(package/"MVP_rk3568_int8.rknn").read_bytes()
    actual=hashlib.sha256(model).hexdigest()
    assert actual==manifest["rknn_sha256"], "Imported RKNN bytes do not match manifest"
    assert manifest["classes"]==["person","vehicle","zebra","traffic_light","traffic_sign"]
    assert manifest["input"]==[1,3,480,640] and manifest["reg_max"]==16
    limits=np.array([manifest["thresholds"][str(c)] for c in range(5)],dtype=np.float32)
    cpp=directory/"round1_nms.cpp";exe=directory/"round1_nms.exe"
    harness=r'''
#include <algorithm>
#include <cstdint>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <limits>
#include <string>
#include <vector>
#include "mvp_round1_policy.h"
using qint64=int64_t;
using QString=std::string;
template<class T> struct QVector:std::vector<T> {
 using std::vector<T>::vector;
 void append(const T& v){this->push_back(v);}
 int size()const{return int(std::vector<T>::size());}
};
static const float IOU_THRESH=.45f;
'''
    harness+=block(types,"struct Detection {")+";\nstruct Decoder {\n"
    harness+=block(source,"struct CandD {")+";\n"+block(source,"static void nmsAppend(")+"\n};\n"
    harness+=r'''
int main(int argc,char** argv) {
 if(argc==3) return mvp::Round1Policy::matchesSha(argv[1],argv[2])?0:2;
 std::vector<Decoder::CandD> candidates;
 Decoder::CandD box{};
 while(std::cin>>box.score>>box.x1>>box.y1>>box.x2>>box.y2>>box.cls)
  if(box.score>=mvp::Round1Policy::candidateFloor)candidates.push_back(box);
 QVector<Detection> dets;
 Decoder::nmsAppend(dets,candidates,true,mvp::Round1Policy::nmsIou);
 mvp::Round1Policy policy;policy.enabled=true;policy.filterAfterNms(dets);
 std::cout<<std::setprecision(9);
 for(const auto& d:dets)std::cout<<d.cls<<" "<<d.score<<" "<<d.x1<<" "<<d.y1<<" "<<d.x2<<" "<<d.y2<<"\n";
}
'''
    cpp.write_text(harness,encoding="utf-8")
    subprocess.run([args.cxx,"-std=c++17","-O2","-Wall","-Wextra","-I",str(root),str(cpp),"-o",str(exe)],check=True)
    subprocess.run([str(exe),manifest["rknn_sha256"],actual],check=True)
    wrong=hashlib.sha256(model+b"wrong model bytes").hexdigest()
    assert subprocess.run([str(exe),manifest["rknn_sha256"],wrong]).returncode==2
    print("ROUND1_IMPORTED_FILE_SHA_BINDING_PASS",flush=True)
    spec=importlib.util.spec_from_file_location("round1_postprocess",package/"postprocess.py")
    reference=importlib.util.module_from_spec(spec);spec.loader.exec_module(reference)
    rng=np.random.default_rng(3568)
    xy=rng.uniform(0,450,(750,2)).astype(np.float32)
    size=rng.uniform(5,100,(750,2)).astype(np.float32)
    boxes=np.concatenate([xy,xy+size],axis=1)
    scores=rng.uniform(.0005,.99,750).astype(np.float32)
    classes=rng.integers(0,5,750)
    cases=[("random-five-class",boxes,scores,classes),
           ("maxdet-before-thresholds",np.array([[i*3,0,i*3+1,1] for i in range(301)],np.float32),
            np.concatenate([np.linspace(.44,.4,300),[.3]]).astype(np.float32),np.array([1]*300+[2])),
           ("duplicates-before-maxdet",np.array([[0,0,10,10]]*350+[[100,0,110,10]],np.float32),
            np.concatenate([np.linspace(.9,.5,350),[.3]]).astype(np.float32),np.array([1]*350+[2])),
           ("overlap-different-classes",np.array([[0,0,10,10],[2.5,0,12.5,10],[0,0,10,10]],np.float32),
            np.array([.8,.7,.6],np.float32),np.array([0,0,1]))]
    for label,b,s,c in cases:
        text="".join(f"{score:.9g} {x1:.9g} {y1:.9g} {x2:.9g} {y2:.9g} {cls}\n" for (x1,y1,x2,y2),score,cls in zip(b,s,c))
        output=subprocess.check_output([str(exe)],input=text,text=True)
        got=np.array([[float(value) for value in line.split()] for line in output.splitlines()]).reshape(-1,6)
        mask=s>=np.float32(.001);b,s,c=b[mask],s[mask],c[mask]
        keep=reference._nms_per_class(b,s,c,.7)
        keep=keep[np.argsort(s[keep])[::-1]][:300] # Complete NMS, global cap, then thresholds.
        keep=keep[s[keep]>=limits[c[keep]]]
        expected=np.column_stack([c[keep],s[keep],b[keep]])
        np.testing.assert_allclose(got,expected,rtol=0,atol=.0001)
        print(f"ROUND1_DELIVERED_NMS_MATCH_PASS {label} ({len(got)} detections)",flush=True)

def reference_check(args,root,directory):
    import ast
    import importlib.util
    import json
    import numpy as np
    package=args.package
    spec=importlib.util.spec_from_file_location("shared_reference",package/"MVP_plus_shared_FP16"/"mvp_shared_postprocess.py")
    shared=importlib.util.module_from_spec(spec);spec.loader.exec_module(shared)
    data=json.loads((package/"UFLDv2_independent_FP16"/"dataset_summary.json").read_text(encoding="utf-8-sig"))
    pipeline=json.loads((package/"MVP_plus_shared_FP16"/"pipeline.json").read_text(encoding="utf-8-sig"))
    assert data["row_anchors"]==pipeline["row_anchors"] and data["col_anchors"]==pipeline["col_anchors"]
    rows=np.array(data["row_anchors"],dtype=np.float32);cols=np.array(data["col_anchors"],dtype=np.float32)
    tree=ast.parse((package/"UFLDv2_independent_FP16"/"train_mvp_lane.py").read_text(encoding="utf-8"))
    decode=next(node for node in tree.body if isinstance(node,ast.FunctionDef) and node.name=="decode_lane")
    decode.decorator_list=[]
    module=ast.Module(body=[decode],type_ignores=[])
    scope=dict(np=np,GR=64,GC=48,W=640,H=480,LANES=8,ROW=rows,COL=cols)
    exec(compile(module,"delivered_decode_lane","exec"),scope)
    class Tensor:
        def __init__(self,value): self.value=value
        def argmax(self,axis): return Tensor(self.value.argmax(axis))
        def float(self): return Tensor(self.value.astype(np.float32))
        def cpu(self): return self
        def numpy(self): return self.value
    cpp=directory/"points.cpp";exe=directory/"points.exe"
    cpp.write_text(r'''
#include "mvp_decode.h"
#include <fstream>
#include <iomanip>
#include <iostream>
int main(int argc,char** argv) {
 if(argc!=2)return 2;
 std::ifstream file(argv[1],std::ios::binary);
 const int sizes[4]={64*24*8,48*32*8,2*24*8,2*32*8};
 std::array<std::vector<float>,4> data; std::array<const float*,4> tensors;
 for(int i=0;i<4;++i){data[i].resize(sizes[i]);file.read(reinterpret_cast<char*>(data[i].data()),sizes[i]*sizeof(float));tensors[i]=data[i].data();}
 if(!file)return 3;
 std::vector<mvp::Point> points;
 if(!mvp::decodePoints(tensors,mvp::LaneContract{},points))return 4;
 for(const auto& p:points)std::cout<<p.lane<<","<<int(p.row)<<","<<std::setprecision(9)<<p.x<<","<<p.y<<"\n";
}
''',encoding="utf-8")
    subprocess.run([args.cxx,"-std=c++17","-O2","-I",str(root),str(cpp),"-o",str(exe)],check=True)
    rng=np.random.default_rng(3568)
    tensors=[rng.standard_normal(shape).astype(np.float32) for shape in [(1,64,24,8),(1,48,32,8),(1,2,24,8),(1,2,32,8)]]
    for axis in range(2):
        tensors[axis][0,:,0,0]=-5;tensors[axis][0,0,0,0]=10
        tensors[axis][0,:,-1,7]=-5;tensors[axis][0,-1,-1,7]=10
        tensors[axis+2][0,:,0,0]=[0,1];tensors[axis+2][0,:,-1,7]=[0,1]
        tensors[axis+2][0,:,1,1]=0 # Existence tie: absent.
    binary=directory/"logits.bin"
    binary.write_bytes(b"".join(t.tobytes() for t in tensors))
    actual=[]
    for line in subprocess.check_output([str(exe),str(binary)],text=True).splitlines():
        lane,row,x,y=line.split(",");actual.append((int(lane),int(row),float(x),float(y)))
    actual.sort()
    refs=[shared.decode_lanes(tensors,rows,cols),scope["decode_lane"]([Tensor(t) for t in tensors])]
    for label,reference in zip(["shared","independent"],refs):
        expected=[]
        for lane,points in enumerate(reference[0]):
            for key,row in [("row_points",1),("col_points",0)]:
                for x,y in points[key]: expected.append((lane,row,float(x),float(y)+80))
        expected.sort()
        np.testing.assert_allclose(np.array(actual),np.array(expected),rtol=0,atol=0.0001)
        print(f"DELIVERED_{label.upper()}_REFERENCE_MATCH_PASS ({len(actual)} points)",flush=True)

if __name__=="__main__": main()
