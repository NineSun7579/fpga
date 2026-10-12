#include "rknn_api.h"
#include <fstream>
#include <iterator>
#include <vector>
#include <cstdio>
int main(int argc,char**argv) {
    if(argc!=2)return 2;
    std::ifstream file(argv[1],std::ios::binary);
    std::vector<char> model((std::istreambuf_iterator<char>(file)),{});
    if(model.empty())return 3;
    rknn_context context=0;
    if(rknn_init(&context,model.data(),model.size(),0,nullptr))return 4;
    rknn_tensor_attr attr{}; attr.index=0;
    int rc=rknn_query(context,RKNN_QUERY_INPUT_ATTR,&attr,sizeof(attr));
    if(!rc) {
        std::printf("input type=%d fmt=%d size=%u size_with_stride=%u w_stride=%u n_dims=%u dims=",attr.type,attr.fmt,attr.size,attr.size_with_stride,attr.w_stride,attr.n_dims);
        for(unsigned i=0;i<attr.n_dims;++i)std::printf("%u/",attr.dims[i]);
        std::puts("");
    }
    rknn_destroy(context);
    return rc?5:0;
}
