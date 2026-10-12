# exact09 routed 实证复核

来自 actual routed `physical_exact_09/evidence/final_sta_summary.json`：

|检查|Slow failing endpoints|Slow worst ns|Fast failing endpoints|Fast worst ns|
|---|---:|---:|---:|---:|
|Setup|1486|-12.219|604|-8.460|
|Hold|0|0.158|0|0.116|
|Recovery|132|-8.393|132|-5.177|
|Removal|0|0.315|0|0.250|
|Minimum Pulse Width|0|0.011|0|0.011|

全部2354条报告负路径有独立JSON详细记录。不能声明十组通过。

已有分类包含 camera FIFO first sync、diagnostic ack_sync[0]、raw debug crossing、snapshot路径、init_done跨PCLK reset恢复路径。路径豁免需按实际结构与原约束关系证明，不能为关闭时序直接扩大CDC例外。

当前 audit_fixed.py 对定向报告沿用 synthesis 名字，routed primitive实例带 opit_* 等转换名；必须在routed DB重新解析及映射，不得用旧名得到的空报告验收。reset必须保留32逻辑位到24实体的解析，区分16 AXI可检查endpoint和8 camera跨域既有豁免，同时检查同域树与MPW。

独立 synthesis_epoch10 与先前1280图的2048逐位 mapping 完全一致，clock_provenance也完全一致；dump SHA256为c0a920ae2ca11360df4cad4376b2f25318896956f6a21fac53b23e15563959f9。这个新综合为分阶段约束验证提供实际输入，未关闭routed门槛。
