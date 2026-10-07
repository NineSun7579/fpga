# MVP accuracy-first round1：RK3568 INT8

WebDAV来源：`yolo_project/MVP_accuracy_round1_rk3568_int8_20261007_125445/`。本目录的模型字节来自已校验包，发布名加accuracy_round1以便与旧MVP区分。

`MVP_accuracy_round1_rk3568_int8.rknn`：SHA256 `6cdfe6c8d834e2b99994633b483e048819a79c440562a2ea1ccbc55947be03e2`。外部RGB uint8 NHWC宽640高480，内部/255。六路raw DFL输出为box_p3/p4/p5、cls_p3/p4/p5；实际layout/stride/type/scale/zp须查询该模型运行时。

五类person0、vehicle1、zebra2、traffic_light3、traffic_sign4。sigmoid后的类别阈值依次0.35/0.45/0.25/0.35/0.40；完整五类候选conf0.001、按类NMS IoU0.7、max_det300后再过滤类别阈值。必须把`.names.json`和`.deployment.json`与模型一起部署；detview会核对模型字节SHA256再启用该配置。

源模型与转换/模拟验证报告保留为提供方证据，未据此宣称板端道路精度。实时性能与防闪烁实测见[发布记录](../../../releases/detview_temporal_20261007/README.md)。未把新检测权重拼入旧共享车道头。
