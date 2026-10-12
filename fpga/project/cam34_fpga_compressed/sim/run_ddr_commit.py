from pathlib import Path
import subprocess,sys
root=Path(__file__).resolve().parent;bin=Path(r'C:/modeltech64_10.6e/win64');src=root.parent/'source'
files=[src/'ov5640/cam34_downsample_2x2.v',src/'ov5640/ov5640_ddr/ov5640_ddr.v',src/'ov5640/ov5640_ddr/ov5640_ddr_w.v',src/'ov5640/ov5640_ddr/ov5640_ddr_w_ctrl.v',src/'ov5640/ov5640_ddr/ov5640_ddr_w_en.v',src/'axi_dma/axi_dma_write.v',src/'axi_dma/stream_pipe.v',root/'fifo_models.sv',root/'tb_cam34_ddr_commit.sv']
commands=[['vlog.exe','-sv','-work','cam34sim']+list(map(str,files)),['vsim.exe','-c','-vopt','-lib','cam34sim','tb_cam34_ddr_commit','-do','run -all; quit -f']]
log=root/'ddr_commit.log'
with log.open('w',encoding='utf-8')as out:
 for argv in commands:
  p=subprocess.run([str(bin/argv[0])]+argv[1:],cwd=root,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding='utf-8',errors='replace');out.write(p.stdout);out.flush()
  if p.returncode:print(p.stdout[-3000:]);sys.exit(1)
text=log.read_text();print(text[-3000:]);sys.exit(0 if 'CAM34_DDR_COMMIT_PASS' in text and '** Fatal' not in text else 1)
