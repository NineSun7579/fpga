# 未来独立 build03 可采用的 actual module 源

两份 RTL 由 seal_delivery.py 从本次实际编译的 candidate/rtl 按字节导出，sourcehash.json 记录 SHA256：

- v7_sfd_candidate.v：保留当前 build02 显式 primitive 属性和实例，含 actual v7_sfd_counter、v7_sfd_candidate 和新增 v7_camera_gap_boolean。四路 source/cg 改绑专用 gap；其他 counter 使用原模块名和 W 参数。
- ov5640_cdc_tc04.v：保持 actual module 名和原 FIFO/IP 接线，仅采用 isolated boolean candidate 的 prefix 最终门控。

这些文件不登记到活动 PDS，不切换 active candidate，不预接 map02，也不代表物理时序验收。功能证据及冻结失败范围须同时阅读上一层 REPORT_ZH.md、audit.json、freeze_audit.json。本轮实际编译闭包未漂移，但 map02 外部脚本/队列观察的保护输入漂移仍保留为整体冻结 FAIL。
