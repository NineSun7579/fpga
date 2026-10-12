#include <algorithm>
#include <atomic>
#include <chrono>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <stdexcept>
#include <vector>
#include <QVector>
#include <opencv2/opencv.hpp>
#include "rknn_api.h"
constexpr int MODEL_W=640;
constexpr float IOU_THRESH=0.45f;
struct Detection { float x1=0,y1=0,x2=0,y2=0,score=0; int cls=0; };
class ProductionDecoder {
public:
    int m_nc=3; bool m_xyxy=false; std::atomic<float> m_conf{0.25f};
#include "board_production_decoder.inc"
};
static double ms(){return std::chrono::duration<double,std::milli>(std::chrono::steady_clock::now().time_since_epoch()).count();}
static void check(int r,const char* op){if(r!=0)throw std::runtime_error(std::string(op)+" ret="+std::to_string(r));}
static float halfFloat(uint16_t v){int e=(v>>10)&31,m=v&1023; float f=e==0?std::ldexp(float(m),-24):e==31?(m?NAN:INFINITY):std::ldexp(float(1024+m),e-25); return (v&32768)?-f:f;}
static cv::Mat prepare(const cv::Mat& bgr){
    double s=std::min(640.0/bgr.cols,640.0/bgr.rows); int w=std::lround(bgr.cols*s),h=std::lround(bgr.rows*s);
    cv::Mat resized,rgb,padded(640,640,CV_8UC3,cv::Scalar(114,114,114));
    cv::resize(bgr,resized,cv::Size(w,h),0,0,cv::INTER_LINEAR); cv::cvtColor(resized,rgb,cv::COLOR_BGR2RGB);
    rgb.copyTo(padded(cv::Rect((640-w)/2,(640-h)/2,w,h))); return padded;
}
static cv::Mat paint(const cv::Mat& rgb,const QVector<Detection>& dets,const std::string& caption){
    cv::Mat bgr;cv::cvtColor(rgb,bgr,cv::COLOR_RGB2BGR); const char* labels[]={"zebra","vehicle","person"};
    for(const auto& d:dets){cv::Scalar col=d.cls==0?cv::Scalar(0,220,220):d.cls==1?cv::Scalar(0,220,0):cv::Scalar(220,100,255);
        cv::rectangle(bgr,cv::Point(cvRound(d.x1),cvRound(d.y1)),cv::Point(cvRound(d.x2),cvRound(d.y2)),col,2);
        char label[80];std::snprintf(label,sizeof(label),"%s %.2f",d.cls>=0&&d.cls<3?labels[d.cls]:"?",d.score);
        cv::putText(bgr,label,cv::Point(std::max(0,cvRound(d.x1)),std::max(18,cvRound(d.y1)-3)),cv::FONT_HERSHEY_SIMPLEX,0.45,col,1);}
    cv::putText(bgr,caption,cv::Point(8,30),cv::FONT_HERSHEY_SIMPLEX,0.6,cv::Scalar(255,255,255),1);return bgr;
}
struct Model {
    rknn_context ctx=0; std::vector<rknn_tensor_attr> attrs; std::vector<rknn_output> outs; bool acquired=false;
    explicit Model(const char* path){
        std::ifstream f(path,std::ios::binary);if(!f)throw std::runtime_error("open model");
        std::vector<char> buf((std::istreambuf_iterator<char>(f)),{});check(rknn_init(&ctx,buf.data(),buf.size(),0,nullptr),"init");
        rknn_input_output_num io{};check(rknn_query(ctx,RKNN_QUERY_IN_OUT_NUM,&io,sizeof(io)),"io query");
        rknn_tensor_attr a{};check(rknn_query(ctx,RKNN_QUERY_INPUT_ATTR,&a,sizeof(a)),"input query");
        if(io.n_input!=1||a.n_elems!=640*640*3)throw std::runtime_error("requires one RGB640 input");
        attrs.resize(io.n_output);outs.resize(io.n_output);
        for(unsigned i=0;i<io.n_output;i++){attrs[i].index=i;check(rknn_query(ctx,RKNN_QUERY_OUTPUT_ATTR,&attrs[i],sizeof(attrs[i])),"output query");}
    }
    ~Model(){release();if(ctx)rknn_destroy(ctx);}
    void set(const cv::Mat& rgb){rknn_input in{};in.buf=rgb.data;in.size=rgb.total()*3;in.type=RKNN_TENSOR_UINT8;in.fmt=RKNN_TENSOR_NHWC;check(rknn_inputs_set(ctx,1,&in),"inputs_set");}
    void run(){check(rknn_run(ctx,nullptr),"run");}
    void get(int want){for(unsigned i=0;i<outs.size();i++){outs[i]={};outs[i].index=i;outs[i].want_float=want;}check(rknn_outputs_get(ctx,outs.size(),outs.data(),nullptr),"outputs_get");acquired=true;}
    void release(){if(acquired){check(rknn_outputs_release(ctx,outs.size(),outs.data()),"release");acquired=false;}}
    QVector<Detection> decode(ProductionDecoder& dec,int want){
        if(want)return dec.decode(outs,attrs);
        std::vector<std::vector<float>> floats(attrs.size());std::vector<rknn_output> converted=outs;
        for(unsigned i=0;i<attrs.size();i++){auto& a=attrs[i];auto& v=floats[i];v.resize(a.n_elems);
            for(unsigned j=0;j<a.n_elems;j++){float x;
                switch(a.type){case RKNN_TENSOR_INT8:x=((int8_t*)outs[i].buf)[j];break;case RKNN_TENSOR_UINT8:x=((uint8_t*)outs[i].buf)[j];break;case RKNN_TENSOR_FLOAT16:x=halfFloat(((uint16_t*)outs[i].buf)[j]);break;case RKNN_TENSOR_FLOAT32:x=((float*)outs[i].buf)[j];break;default:throw std::runtime_error("unsupported native output type");}
                if(a.qnt_type==RKNN_TENSOR_QNT_AFFINE_ASYMMETRIC)x=(x-a.zp)*a.scale;else if(a.qnt_type==RKNN_TENSOR_QNT_DFP)throw std::runtime_error("DFP unsupported");v[j]=x;
            }converted[i].buf=v.data();converted[i].want_float=1;
        }return dec.decode(converted,attrs);
    }
};
static void stats(std::ofstream& f,const std::string& stage,const std::vector<double>& a){auto b=a;std::sort(b.begin(),b.end());double sum=0;for(double v:a)sum+=v;f<<stage<<","<<a.size()<<","<<b.front()<<","<<sum/a.size()<<","<<b[std::max(size_t(1),size_t(std::ceil(.95*a.size())))-1]<<","<<b.back()<<"\n";}
static bool selftest(){
    ProductionDecoder dec; std::vector<rknn_tensor_attr> a(2);a[0].n_dims=a[1].n_dims=4;
    a[0].dims[0]=a[1].dims[0]=1;a[0].dims[1]=64;a[1].dims[1]=3;
    a[0].dims[2]=a[0].dims[3]=a[1].dims[2]=a[1].dims[3]=80;
    std::vector<float> box(64*6400,-20),cls(3*6400,-20);int off=20*80+30;
    for(int k=0;k<4;k++)box[(k*16+2)*6400+off]=20;cls[6400+off]=5;
    std::vector<rknn_output> o(2);o[0].buf=box.data();o[1].buf=cls.data();auto d=dec.decode(o,a);
    if(d.size()!=1||d[0].cls!=1||std::abs(d[0].x1-228)>0.01||std::abs(d[0].y1-148)>0.01||std::abs(d[0].x2-260)>0.01||std::abs(d[0].y2-180)>0.01)return false;
    a[0].n_dims=a[1].n_dims=3;a[0].dims[1]=4;a[1].dims[1]=3;a[0].dims[2]=a[1].dims[2]=1;
    box={320,240,100,80};cls={0.1f,0.9f,0.2f};o[0].buf=box.data();o[1].buf=cls.data();d=dec.decode(o,a);
    return d.size()==1&&d[0].cls==1&&d[0].x1==270&&d[0].y1==200&&d[0].x2==370&&d[0].y2==280&&std::abs(d[0].score-0.9)<1e-6;
}
int main(int argc,char** argv){try{
    cv::setNumThreads(1); std::cout<<std::fixed<<std::setprecision(6);
    if(argc==2&&std::string(argv[1])=="selftest"){if(!selftest())throw std::runtime_error("decoder selftest failed");std::cout<<"production raw DFL and cxcywh split SELFTEST PASS\n";return 0;}
    if(argc<7){std::cerr<<"usage: board_harness bench|detect MODEL WANT_FLOAT INPUT/FRAME_LIST PREFIX MODEL_ID [iters=100] [warmup=30]\n";return 2;}
    std::string mode=argv[1],prefix=argv[5],id=argv[6];int want=std::stoi(argv[3]);Model model(argv[2]);ProductionDecoder dec;
    if(mode=="bench"){
        int n=argc>7?std::stoi(argv[7]):100,warm=argc>8?std::stoi(argv[8]):30;
        if(n<1||warm<30)throw std::runtime_error("requires warmup>=30 and iters>=1");
        auto image=cv::imread(argv[4]);if(image.empty())throw std::runtime_error("read image");auto rgb=prepare(image);
        for(int i=0;i<warm;i++){model.set(rgb);model.run();model.get(want);model.decode(dec,want);model.release();}
        std::ofstream sample(prefix+"_samples.csv"),summary(prefix+"_summary.csv");sample<<std::fixed<<std::setprecision(6);summary<<std::fixed<<std::setprecision(6);
        sample<<"iteration,run_only_ms,run_io_ms,offline_pipeline_ms,preprocess_ms,pipeline_run_ms,decode_ms,overlay_ms\n";
        std::vector<double> runs,ios,fulls;model.set(rgb);
        for(int i=0;i<n;i++){
            double t=ms();model.run();double run=ms()-t;
            t=ms();model.set(rgb);model.run();model.get(want);model.release();double io=ms()-t;
            t=ms();auto input=prepare(image);double p=ms();model.set(input);double r0=ms();model.run();double r1=ms();model.get(want);double d0=ms();auto det=model.decode(dec,want);double d1=ms();model.release();double o0=ms();auto overlay=paint(input,det,id);double end=ms();
            runs.push_back(run);ios.push_back(io);fulls.push_back(end-t);sample<<i<<","<<run<<","<<io<<","<<end-t<<","<<p-t<<","<<r1-r0<<","<<d1-d0<<","<<end-o0<<"\n";
        }summary<<"stage,n,min_ms,mean_ms,p95_ms,max_ms\n";stats(summary,"run_only",runs);stats(summary,"run_io",ios);stats(summary,"offline_pipeline",fulls);
        std::cout<<"bench complete "<<id<<" want_float="<<want<<" n="<<n<<" warmup="<<warm<<"\n";
    }else if(mode=="detect"){
        std::ifstream list(argv[4]);std::vector<std::string> paths;std::string path;while(std::getline(list,path))if(!path.empty())paths.push_back(path);
        if(paths.empty())throw std::runtime_error("empty frame list");auto first=cv::imread(paths[0]);if(first.empty())throw std::runtime_error("first frame unreadable");auto rgb=prepare(first);
        for(int i=0;i<30;i++){model.set(rgb);model.run();model.get(want);model.decode(dec,want);model.release();}
        std::ofstream df(prefix+"_detections.csv"),lf(prefix+"_latency.csv"),bf(prefix+"_box_contract.csv");df<<std::fixed<<std::setprecision(6);lf<<std::fixed<<std::setprecision(6);bf<<std::fixed<<std::setprecision(6);
        df<<"frame,class,score,x1,y1,x2,y2\n";lf<<"frame,preprocess_ms,run_ms,run_io_ms,dequant_decode_ms,overlay_ms,offline_pipeline_ms,count\n";bf<<"frame,anchor,c0,c1,c2,c3\n";
        for(unsigned i=0;i<paths.size();i++){
            auto image=cv::imread(paths[i]);if(image.empty())throw std::runtime_error("read frame");double t=ms();rgb=prepare(image);double p=ms();model.set(rgb);double r0=ms();model.run();double r1=ms();model.get(want);double g=ms();auto det=model.decode(dec,want);double d=ms();
            // Record decoded box rows directly for contract verification, once per frame.
            if(want)for(unsigned j=0;j<model.attrs.size();j++){auto& a=model.attrs[j];if(a.n_dims==3&&a.dims[1]==4){auto b=(float*)model.outs[j].buf;int anchors=a.dims[2];for(int k=0;k<anchors;k+=std::max(1,anchors/12))bf<<i<<","<<k<<","<<b[k]<<","<<b[anchors+k]<<","<<b[2*anchors+k]<<","<<b[3*anchors+k]<<"\n";}}
            model.release();double o0=ms();auto overlay=paint(rgb,det,id+" float="+std::to_string(want)+" frame="+std::to_string(i));double end=ms();
            for(auto& v:det)df<<i<<","<<v.cls<<","<<v.score<<","<<v.x1<<","<<v.y1<<","<<v.x2<<","<<v.y2<<"\n";
            lf<<i<<","<<p-t<<","<<r1-r0<<","<<g-p<<","<<d-g<<","<<end-o0<<","<<end-t<<","<<det.size()<<"\n";
            if(!cv::imwrite(prefix+"_frame_"+std::to_string(i)+".png",overlay))throw std::runtime_error("write overlay");
        }std::cout<<"detections complete "<<id<<" want_float="<<want<<" frames="<<paths.size()<<"\n";
    }else throw std::runtime_error("unknown mode");
    return 0;
}catch(const std::exception& e){std::cerr<<"ERROR "<<e.what()<<"\n";return 1;}}
