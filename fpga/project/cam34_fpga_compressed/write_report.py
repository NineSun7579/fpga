from pathlib import Path
import json,re,shutil
root=Path(__file__).resolve().parent;e=root/'board_evidence'
d=json.loads((e/'fps_summary.json').read_bytes());pv=json.loads((e/'pixel_verification.json').read_bytes());m=json.loads((root/'viewer_build/manifest.json').read_bytes());b=json.loads((root/'bitstream_receipt.json').read_bytes())
assert b['status']=='finished'and b['return_code']==0
assert all(x['valid_size']for x in d['measured_dma_policy_by_camera'].values())
assert not d['driver_error_lines']and pv['composition_mismatch_bytes']==0
log=(e/'runtime.log').read_text(encoding='utf-8',errors='replace');points=[];count=0
for line in log.splitlines():
 if line.startswith('[cam34-detections] '):count+=1
 if line.startswith('[cam34-pair] '):
  x=re.search(r'frames=(\d+) host_ms=(\d+)',line)
  if x:points.append((int(x[2]),count,int(x[1])))
first=next(p for p in points if p[0]>=points[0][0]+10000);last=points[-1]
seconds=(last[0]-first[0])/1000;completed=last[1]-first[1];fps=completed/seconds
inf={'seconds':seconds,'completed_results':completed,'fps':fps,'definition':'completed results received by GUI between host-monotonic pair markers, >=10s startup excluded; boundary uncertainty about one result'}
(e/'inference_counted_fps.json').write_text(json.dumps(inf,indent=2),encoding='utf-8')
shots=sorted(e.glob('desktop_*.png'));assert shots;shutil.copy2(shots[-1],e/'verified_six_camera_desktop.png')
rows=[]
for c in range(1,7):
 cap=d['measured_dma_policy_by_camera'][str(c)]['mean_delivered_fps'];disp=d['fresh_display_fps']['cam'+str(c)]['fps'];wire=d['measured_dma_policy_by_camera'][str(c)]['expected_pixel_bytes'];size='320×240'if c in[3,4]else'640×480'
 rows.append(f'| C{c} | {size} | {wire:,} B | {cap:.2f} fps | {disp:.2f} fps |')
text=f'''# FPGA C3/C4 压缩直传、200%六路显示验证报告

FPGA在DDR写入前把C3/C4从640×480做2×2 RGB565均值降采样至320×240。RK3568只读取每路153600字节图像和16字节帧标签，不再传输两路全尺寸RAW。C1/C2/C5/C6继续原路径。

六路3×2网格、窗口大小、位置、4:3比例保持。C3/C4的320×240纹理在原逻辑640×480窗格内由GPU宽高各放大2倍；全窗口适配屏幕统一作用于所有窗格。两路压缩图像左右拼成640×240，上下各120行灰114，成为MVP-R1的640×480输入。共享框去掉canonical80+内容120偏移、x/y均乘2，映射回各自窗格。

| 路 | 实际PCIe图像尺寸 | 图像载荷/帧 | 新帧采集 | 新画面显示 |
|---|---|---:|---:|---:|
'''+ '\n'.join(rows)+f'''

共享新输入：{d['accepted_pair_fps']['fps']:.2f} fps。
完整YOLO结果：{completed}个/{seconds:.3f}秒={fps:.2f}次/秒，每次同时覆盖两路。
单次推理平均：{d['inference_ms']['mean']:.2f} ms。
显示有效计数：{d['fresh_display_fps']['cam3']['seconds']:.3f}秒，已剔除启动阶段。
DMA故障和推理失败：未发现DMA故障，推理失败0。

cam3_dma_identity.json及cam4_dma_identity.json记录实际DMA为153616字节。C3/C4帧标签在DDR基址+153600；readonly geometry magic、尺寸、帧长和stride在启动时核对。等待两组bank完整发布后才读新tag位置。主机长度guard禁止C3/C4超过153616字节的读取，无CPU再次降采样、无RAW回退。

相同帧数下，C3/C4图像载荷合计从1228800降到307200字节，减少75%；完整六路各传一帧从3686400降到2764800，减少25%。比例不包含轮询、tag和PCIe封装，不能等同于未测得的整体速度提升。

板端两张压缩图像与实际模型输入独立组合比对：{pv['model_rgb_bytes']:,}RGB字节差异0。2×2滤波、DDR打包、tag提交由完整RTL golden、真实Pango FIFO、AXI背压、短帧恢复和tag B响应延迟测试验证。板端未传RAW，因此不宣称板端同帧RAW滤波比对。模型有场景误检，此项不是准确率评估。

时序总结与详细报告均通过后才生成并烧录SRAM，SPI Flash及旧安装程序保留。
Bitstream SHA256：{b['sha256']}。
Viewer：{m['executable']}。
Viewer SHA256：{m['executable_sha256']}。

证据：verified_six_camera_desktop.png、cam3_wire_320x240.png、cam4_wire_320x240.png、actual_rknn_input.png、cam3_dma_identity.json、cam4_dma_identity.json、runtime.log、fps_summary.json、inference_counted_fps.json、pixel_verification.json。
'''
(e/'FPGA_CAM34_压缩直传与200显示_验证报告.md').write_text(text,encoding='utf-8');print('VERIFIED_REPORT',e/'FPGA_CAM34_压缩直传与200显示_验证报告.md')
