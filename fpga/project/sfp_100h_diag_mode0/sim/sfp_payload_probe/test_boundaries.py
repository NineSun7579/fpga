from pathlib import Path
import subprocess,json,re,importlib.util
R=Path(__file__).resolve().parent; A=R.parent/'sfp_align';B=Path('C:/modeltech64_10.6e/win64')
spec=importlib.util.spec_from_file_location('vectors',A/'run_tests.py');v=importlib.util.module_from_spec(spec);spec.loader.exec_module(v)
def run(args,name):
 p=subprocess.run([str(x) for x in args],cwd=R,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
 text=p.stdout.decode(errors='replace');(R/name).write_text(text)
 if p.returncode:raise RuntimeError(name)
 return text
run([B/'vlib.exe','boundarywork'],'boundary_vlib.log')
run([B/'vlog.exe','-sv','-work','boundarywork',A/'hsst_sfp_stub.v',R.parents[1]/'source/sfp/sfp_rx_link.v','rx_symbol_candidate.sv','tb_candidate.v'],'boundary_compile.log')
results=[]
for kind in ['baseline','delete_before_sof','insert_before_sof','delete_sof','delete_sof_repeated','delete_payload','insert_payload','delete_before_data','insert_before_data']:
 for offset in range(4):
  syms,gold=v.stimulus(kind,64);syms=[(0xc5,0)]*offset+syms;syms += v.ctrl()[:(-len(syms))%4]
  name=f'boundary_{kind}_{offset}'
  with (R/(name+'.vec')).open('w') as f:
   for i in range(0,len(syms),4):
    chunk=syms[i:i+4];f.write(f'{sum(b<<(j*8) for j,(b,k) in enumerate(chunk)):08x} {sum(k<<j for j,(b,k) in enumerate(chunk)):x}\n')
  text=run([B/'vsim.exe','-c','boundarywork.tb_sfp_align',f'+VECTOR={name}.vec',f'+PIXELS={name}.pixels',f'+TRACE={name}.trace','-do','onbreak {quit -code 1 -force}; run -all; quit -code 0 -force'],name+'.log')
  obs=[int(l,16) for l in (R/(name+'.pixels')).read_text().splitlines()]
  m=re.search(r'RESULT pixels=(\d+) frame_pixels=(\d+) sof=(\d+) controls=(\d+) relocks=(\d+) overflow=(\d+)',text)
  row=dict(zip(['pixels','frame_pixels','sof','controls','relocks','overflow'],map(int,m.groups())))
  row.update(kind=kind,offset=offset,exact=obs==gold)
  results.append(row)
  assert row['exact'] and row['sof']==1 and row['frame_pixels']==64 and row['overflow']==0,row
(R/'boundary_summary.json').write_text(json.dumps(results,indent=2));print('PASS 36 boundary cases: exact 64 pixels, one SOF, no overflow')
