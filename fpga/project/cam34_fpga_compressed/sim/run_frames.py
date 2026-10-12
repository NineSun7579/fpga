from pathlib import Path
import subprocess,sys
root=Path(__file__).resolve().parent
bin=Path(r'C:/modeltech64_10.6e/win64')
log=root/'frames.log'
commands=[['vlib.exe','cam34sim'],['vlog.exe','-sv','-work','cam34sim','../source/ov5640/cam34_downsample_2x2.v','tb_cam34_frames.sv'],['vsim.exe','-c','-vopt','-lib','cam34sim','tb_cam34_frames','-do','run -all; quit -f']]
with log.open('w',encoding='utf-8') as out:
 for argv in commands:
  p=subprocess.run([str(bin/argv[0])]+argv[1:],cwd=root,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding='utf-8',errors='replace');out.write(p.stdout);out.flush()
  if p.returncode:print(p.stdout[-3000:]);sys.exit(1)
text=log.read_text();print(text[-2600:]);sys.exit(0 if 'CAM34_FULLFRAME_PASS' in text and '** Fatal' not in text else 1)
