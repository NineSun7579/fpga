from pathlib import Path
import subprocess,sys
HERE=Path(__file__).resolve().parent
VSIM='C:/modeltech64_10.6e/win64/vsim.exe'
VLOG='C:/modeltech64_10.6e/win64/vlog.exe'
def run(args,log,need):
    p=subprocess.run(args,cwd=HERE,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
    text=p.stdout.decode(errors='replace')
    (HERE/log).write_text(text,encoding='utf-8')
    if p.returncode or need not in text or '** Fatal:' in text or '** Error:' in text:
        print(text[-6000:]); raise SystemExit(f'FAIL {log}')
    print(log, '\n'.join(s for s in text.splitlines() if 'PASS' in s or 'RESULT' in s))
if not sys.argv[1:]:
 run([VSIM,'-c','-do','run_cdc.do'],'fixed_cdc.log','PASS stage snapshots')
run([VLOG,'-work','work_cdc','-sv','../../source/ov5640/ov5640/cmos_capture.v',
     '../../source/ov5640/cam_fir3.v','tb_frontend.sv','tb_cdc_drop.sv'],'compile_frontend.log','Errors: 0')
for name,top,opts,need in [
 ('drop_recovery','tb_cdc_drop',[],'PASS DROP'),
 ('fixed_injected','tb_cdc_pixels',['-gINJECT=1'],'PASS stage snapshots'),
 ('real_rows84','tb_cdc_pixels',['-gREAL_ROWS=1'],'PASS stage snapshots'),
 ('real_rows48','tb_cdc_pixels',['-gREAL_ROWS=1','-gCAM_HALF=10.416666667','-gCAM_PHASE=2.1'],'PASS stage snapshots'),
 ('frontend84','tb_frontend',[],'PASS FRONTEND'),
 ('frontend84_phase','tb_frontend',['-gPHASE=2.731'],'PASS FRONTEND'),
 ('frontend48','tb_frontend',['-gCAM_HALF=10.416666667','-gPHASE=1.813'],'PASS FRONTEND')]:
 if not sys.argv[1:] or name in sys.argv[1:]:
  run([VSIM,'-c','-voptargs=+acc',f'work_cdc.{top}',*opts,'-do','run -all; quit -force'],name+'.log',need)
print('OVERALL PASS')
