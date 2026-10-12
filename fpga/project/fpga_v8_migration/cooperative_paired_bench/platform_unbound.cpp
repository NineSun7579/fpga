#include "platform_binding.hpp"
namespace paired_bench {
Binding bind_platform(const std::string&,std::uint32_t) {
    throw std::runtime_error("平台尚未绑定：需要外部持久化 generation、运行时预留和共享互斥锁凭据");
}
}
