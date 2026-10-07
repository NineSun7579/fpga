# MVP 准确度优先第一轮 RK3568 INT8

这份是新的COCO初始化、原GT扩充与难例采样训练后选定的五类YOLOv8n，不是之前WebDAV的旧MVP。640宽×480高；RGB、等比letterbox、padding114。

MVP_rk3568_int8.rknn为raw DFL6，输出顺序box_p3、box_p4、box_p5、cls_p3、cls_p4、cls_p5。对应NCHW网格60×80、30×40、15×20；box64通道、cls5通道，reg_max16。ONNX为RGB float32 NCHW /255；RKNN外部RGB uint8 NHWC，由模型配置内部/255。实际board输入/输出layout、dtype、stride、scale和zp必须查询新模型，不能沿用旧MVP参数。

五类ID为person0、vehicle1（骑行者归车）、zebra2、traffic_light3、traffic_sign4。配套运行阈值依次0.35、0.45、0.25、0.35、0.40。阈值在浮点校准集选择，量化后保持并验证，没有根据test重调。类阈值应用于dequantized logits经sigmoid后的score，不能直接将概率阈值与INT8整数值比较。按类别筛选前使用完整五类NMS conf0.001、iou0.7、max_det300，才能匹配本报告运行口径。

量化AP记录在validation.json，固定阈值后的P/R/FP/FN在fixed_threshold_INT8_validation.json；验证为本机CPU模拟，不是RK3568板端实测。float_frozen_test.json为完整1000张浮点冻结测试；量化子集不得与完整测试分数直接相减。zebra新test无GT，val只有历史来源，未认证跨域效果。

postprocess.py负责raw DFL解码与检测NMS；runtime_quantization.json、rknn_config.json和graph.json说明编译及逻辑输出。阈值绑定源PT SHA（thresholds.json），deployment_manifest.json同时绑定新RKNN SHA。FP16/INT8量化误差与误检限制仍需读取验证报告，不能因上传成功宣称现场可靠。

本包只更新MVP检测。旧共享MVP-plus头与新检测权重SHA不匹配，不能直接拼接；这次没有更新车道模型。旧WebDAV目录保留，新包单独发布。
