from pathlib import Path
import hashlib,json,re,subprocess
P=Path(__file__).resolve().parent;B=P.parent
SIM=Path('C:/modeltech64_10.6e/win64');V=Path('C:/pango/PDS_2022.2-SP6.4/arch/vendor/pango/verilog/simulation')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
 d=P/'cycle';d.mkdir(exist_ok=True);binding={};rename={}
 for tag,source in [('old',B/'source_diagnostics_timing_build_01/rtl/v7_sfd_candidate.v'),('new',B/'source_diagnostics_timing_build_04/rtl/v7_sfd_candidate.v'),('original',B/'source_frame_diagnostics_candidate/v7_sfd_candidate.v')]:
  raw=source.read_bytes();binding[str(source)]=sha(source)
  names=re.findall(rb'\bmodule\s+(\w+)',raw);mapping={n:tag.encode()+b'_'+n for n in names}
  transformed=re.sub(rb'\b(?:'+b'|'.join(names)+rb')\b',lambda m:mapping[m.group()],raw)
  (d/(tag+'.v')).write_bytes(transformed);rename[tag]={a.decode():b.decode() for a,b in mapping.items()}
 for n in ['GTP_DFF_CE.v','GTP_DFF_PE.v','GTP_GRS.v']:binding[str(V/n)]=sha(V/n)
 binding[str(P/'tb_mailbox_cycle.sv')]=sha(P/'tb_mailbox_cycle.sv')
 def run(exe,args,name):
  r=subprocess.run([str(SIM/exe),*map(str,args)],cwd=d,capture_output=True);text=(r.stdout+r.stderr).decode('utf8','replace')
  (P/name).write_text(text,encoding='utf8');print(text[-1500:],flush=True)
  assert r.returncode==0 and not re.search(r'\*\* (Error|Fatal)',text),name
  return text
 run('vlib.exe',['work'],'cycle_vlib.log')
 run('vlog.exe',['-sv',V/'GTP_DFF_CE.v',V/'GTP_DFF_PE.v',V/'GTP_GRS.v','old.v','new.v','original.v',P/'tb_mailbox_cycle.sv'],'cycle_compile.log')
 text=run('vsim.exe',['-c','-voptargs=+acc','work.tb_mailbox_cycle','-do','onerror {quit -code 2}; run -all; quit -code 0'],'cycle_simulation.log')
 assert 'PASS ALL2048' in text and len(re.findall(r'PASS camera\d cycles=40000',text))==4
 for source,h in binding.items():assert sha(source)==h
 (P/'cycle_result.json').write_text(json.dumps({'status':'PASS_FRESH_RTL_CYCLE_MITER','source_bindings':binding,'only_transformation':'module identifier namespace renaming','namespace_mapping':rename,'cameras':4,'cycles_per_camera':40000,'compared_each_observation':['all512 mailbox bits','all512 host_bank bits','bus data flags outputs'],'goldens':['original source_frame_diagnostics_candidate','actual build01 source'],'limitations':'RTL functional simulation plus sharedlane induction; no mapped60 signoff or routed timing'},ensure_ascii=False,indent=2)+'\n',encoding='utf8')
if __name__=='__main__':main()
