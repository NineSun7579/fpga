from pathlib import Path
import subprocess
R=Path(__file__).resolve().parent;W=R.parents[2];B=Path('C:/modeltech64_10.6e/win64')
T=W/'ov5640_sfp480p_test/ov5640_sfp480p_test/source/rtl'
for args,name in [(['vlib.exe','recoverywork'],'recovery_vlib.log'),
 (['vlog.exe','-sv','-work','recoverywork',str(T/'video_async_fifo.v'),'candidate_sfp_video_tx.v',str(W/'project/source/sfp/sfp_video_rx.v'),'tb_recovery.sv'],'recovery_compile.log'),
 (['vsim.exe','-c','recoverywork.tb_recovery','-do','onbreak {quit -code 1 -force};run -all;quit -code 0 -force'],'recovery.log')]:
 p=subprocess.run([str(B/args[0]),*args[1:]],cwd=R,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
 t=p.stdout.decode(errors='replace');(R/name).write_text(t)
 assert p.returncode==0,name
 if name=='recovery.log':assert 'PASS RECOVERY' in t
print('PASS recovery')
