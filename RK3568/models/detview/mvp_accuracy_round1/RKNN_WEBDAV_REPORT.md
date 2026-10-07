# 新MVP准确度优先版本：RKNN转换、WebDAV与验证报告

已将本轮选定的COCO初始化MVP转为RK3568 INT8，上传新WebDAV目录并逐文件GET回读校验。原WebDAV模型未覆盖。

远端：`/mnt/webdav/yolo_project/MVP_accuracy_round1_rk3568_int8_20261007_125445`。HTTP：`https://webdav.123pan.cn/webdav/yolo_project/MVP_accuracy_round1_rk3568_int8_20261007_125445`。完成时间：2026-10-07T12:55:31.087415。
本地包：`/root/yolo_project/artifacts/MVP_accuracy_round1_rk3568_int8_20261007_125445`；共38文件，26953941字节，长度及SHA256均一致。

## 模型与输入输出

YOLOv8n、五类person0/vehicle1（骑行者归车）/zebra2/traffic_light3/traffic_sign4，固定宽640高480。raw DFL6：boxP3、boxP4、boxP5、clsP3、clsP4、clsP5；网格60×80、30×40、15×20，box64、cls5，reg_max16。
RKNN外部RGB uint8 NHWC，配置mean0/std255；ONNX float NCHW /255。等比letterbox padding114，NMS与原图还原在外部。输出物理layout/stride/scale/zp须查询新模型运行时，不沿用旧模型数值。

源模型SHA256：`b418d1e662e661616866a0961a4401345fca89410fe8797740e79f2905bde272`。
RKNN SHA256：`6cdfe6c8d834e2b99994633b483e048819a79c440562a2ea1ccbc55947be03e2`。

256张train用于INT8标定，未使用阈值calibration集合。原GT val/test各128张用于PT/ONNX/INT8对照。四split全部采集组/SHA隔离检查通过；新test没有zebra GT，不制造其AP。

## 量化精度对照

| 子集 | PT AP95 | ONNX AP95 | INT8模拟 AP95 | INT8−PT |
|---|---:|---:|---:|---:|
| val128 | 0.334004 | 0.334004 | 0.324537 | -0.009467 |
| test128 | 0.277882 | 0.277882 | 0.270255 | -0.007627 |

上述为按原GT类别范围屏蔽未知预测后计算的AP，不等同生产完整五类误检率。阈值运行评估保留完整五类NMS，固定0.35/0.45/0.25/0.35/0.40，记录在`fixed_threshold_INT8_validation.json`。阈值来自先前浮点calibration，量化后只验证、不按test重调。

完整固定阈值PT/ONNX/INT8的每类Precision、Recall、TP/FP/FN和输入/模型指纹随包保存；完整1000图浮点冻结测试与128图量化子集不是同一集合，不能把两者分数直接相减。zebra范围不足、第三方GT遗漏及域外误检仍限制结论。

## 交付与边界

- 模型：`MVP_rk3568_int8.rknn`，附PT、raw ONNX、后处理及量化/编译协议。
- `thresholds.json`及`deployment_manifest.json`绑定新PT/RKNN，旧模型不可混用。
- `validation.json`、`numeric.json`、固定阈值验证与训练报告保留。
- 全部文件HTTP PUT后GET回读，支持CDN重定向；不是挂载缓存读回。
- 本次只转换新MVP检测，没有将新检测器与旧共享车道头混搭。
- 编译及CPU模拟通过；**新RKNN尚无板端速度或板端准确度实测**，旧MVP20.03ms不能作为新模型实测。

## 上传审计

逐文件审计：`logs/MVP_accuracy_round1_rk3568_int8_20261007_125445_upload.json`；远端校验和：`SHA256SUMS`。报告形成于上传完整校验之后，上传成功不代表现场精度认证。

## 固定阈值逐类回归

| 子集 | 类别 | ONNX Precision | INT8 Precision | ONNX Recall | INT8 Recall | ONNX FP→INT8 FP |
|---|---|---:|---:|---:|---:|---:|
| val | person | 0.805195 | 0.770270 | 0.433566 | 0.398601 | 15→17 |
| val | vehicle | 0.919952 | 0.937500 | 0.609660 | 0.581948 | 67→49 |
| val | zebra | 0.609756 | 0.631579 | 0.961538 | 0.923077 | 16→14 |
| val | traffic_light | 0.746032 | 0.739130 | 0.458537 | 0.414634 | 32→30 |
| val | traffic_sign | 0.729730 | 0.757812 | 0.387097 | 0.347670 | 40→31 |
| test | person | 0.637500 | 0.681818 | 0.404762 | 0.357143 | 29→21 |
| test | vehicle | 0.924479 | 0.945607 | 0.546154 | 0.521538 | 58→39 |
| test | zebra | 无GT | 无GT | 无GT | 无GT | 不计算 |
| test | traffic_light | 0.732394 | 0.725806 | 0.474164 | 0.410334 | 57→51 |
| test | traffic_sign | 0.792969 | 0.820175 | 0.415133 | 0.382413 | 53→41 |

NMS和匹配的数值舍入、量化分数变化可能改变候选数，按相同子集记录实测变化，不把小子集结果当作全量测试。模拟器是否直接加载导出二进制或由相同图/配置重建，见固定阈值报告的simulator记录。

本次固定阈值检查尝试load_rknn成功，但本机CPU init_runtime返回-1，因此使用完全相同冻结ONNX、256张train标定图及RKNN配置重建CPU模拟器。全部已记录输入/输出量化参数与原导出一致；**没有直接执行导出的二进制，也没有执行板端测试**。记录可复现的量化模拟回归，不扩大为板端精度结论。

保持原阈值时test128 vehicle Precision为94.56%、Recall52.15%，ONNX分别为92.45%/54.62%；traffic_light Recall由47.42%降至41.03%，person由40.48%降至35.71%。部分未匹配预测减少伴随真阳性减少，不能称量化提高准确率。阈值未根据test修改，下一步若校准INT8应只使用独立calibration并另行留出验收，不在此test上搜索阈值。
