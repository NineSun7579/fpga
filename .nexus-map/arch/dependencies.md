# 系统依赖

generated_by: nexus-mapper
verified_at: 2026-09-02
provenance: manual inspection of project manifests and scripts

```text
板级资料 -> PDS目标/IP/FDC -> PDS七阶段 -> 网表/SDF/位流
                     |
                     +-> Questa USIM/VSIM -> 项目自检TB -> TEST PASS
```

- DDR3 依赖板级颗粒、拓扑、参考时钟和电压资料后重新审核 IP/FDC。
- PCIe 依赖匹配的 PG2L100H IP 或经批准的重生成输入，随后再做链路、DMA 和后级仿真。
- 双 OV5640 依赖双模组接口、视频模式、DDR3 和 HDMI 资料冻结，之后才建立 canonical 工程与 `sim/questa/`。
- 所有项目的运行态统一进入各自 `build/`，不进入源码目录或公共仿真归档。
