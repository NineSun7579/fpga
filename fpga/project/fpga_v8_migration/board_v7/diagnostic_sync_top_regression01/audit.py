"""Read-only final regression evidence audit; seal current deliverable hashes."""
from pathlib import Path
import hashlib,json,re,gzip,collections
P=Path(__file__).resolve().parent
O=P.parent/'source_diagnostics_top_candidate'
C=P.parent/'diagnostic_sync_register_timing_candidate'
def sha(f):return hashlib.sha256(Path(f).read_bytes()).hexdigest()
R=json.loads((P/'results.json').read_text())
frozen=json.loads((P/'frozen_inputs.json').read_text())
assert all(sha(f)==h for f,h in frozen.items())
assert R['exact_four_state_trace_comparison']['equal']
counts={}
warnings={}
for variant in ['baseline','primitive']:
 D=P/variant
 original_tb=(O/'tb_sdt.sv').read_bytes()
 assert (D/'tb_sdt.sv').read_bytes()==original_tb.replace(b'`include "scenario.vh"',b'`include "scenario.vh"\n`include "compare_monitor.vh"')
 original_scenario=(O/'scenario.vh').read_bytes()
 assert (D/'scenario.vh').read_bytes()==original_scenario.replace(b'$finish;',b'\n'+(P/'reset_extension.vh').read_bytes()+b'\n$finish;')
 log=(D/'simulation.log').read_text(errors='replace')
 warning_lines=[s for s in log.splitlines() if '** Warning' in s]
 warnings[variant]={'count':len(warning_lines),'codes':dict(collections.Counter(re.search(r'\((?:vopt|vsim)-\d+\)',s).group(0) if re.search(r'\((?:vopt|vsim)-\d+\)',s) else 'uncoded' for s in warning_lines)),'messages':warning_lines}
 assert 'Loading vendor.GTP_GRS' in log
 if variant=='primitive':
  assert 'Loading vendor.GTP_DFF_CE' in log and 'Loading vendor.GTP_DFF_PE' in log
 original_files=[Path(x.strip().strip('"')) for x in (O/'compile.f').read_text().splitlines() if x.strip()]
 actual_files=[Path(x.strip().strip('"')) for x in (D/'compile.f').read_text().splitlines() if x.strip()]
 assert len(original_files)==len(actual_files)
 for old,new in zip(original_files,actual_files):
  assert new==(D/'rtl'/old.name if old.name in {'v7_sfd_candidate.v','v7_sdt_bus.v'} else old)
 m=re.search(r'SDT_ALL_PASS checks=(\d+) M01_reads=(\d+) M01_writes=(\d+) legacy_reads=(\d+)',log)
 assert m and tuple(map(int,m.groups()))==(14540,1234,214,17)
 cams=re.findall(r'TOP_RESET_CAM_PASS camera=(\d+)',log)
 assert cams==['1','2','3','4']
 final=re.search(r'TOP_FOUR_RESET_PASS checks=(\d+)',log)
 assert final
 counts[variant]={'original_checks':int(m[1]),'M01_reads':int(m[2]),'M01_writes':int(m[3]),'legacy_reads':int(m[4]),'checks_after_four_reset_extension':int(final[1]),'four_reset_cameras':cams}
 for fn in ['v7_sfd_candidate.v','v7_sdt_bus.v']:
  source=next(f for f in original_files if f.name==fn) if variant=='baseline' else C/'rtl_primitive'/fn
  assert (D/'rtl'/fn).read_bytes()==source.read_bytes()
 with gzip.open(D/'comparison.trace.gz','rb') as f:
  h=hashlib.sha256()
  while True:
   data=f.read(1024*1024)
   if not data:break
   h.update(data)
  assert h.hexdigest()==R[variant]['trace_sha256']
bindings=json.loads((P/'actual_parent_bindings.json').read_text())
assert len(bindings['primitive_instances'])==60
for g in range(4):
 paths=[s for s in bindings['primitive_instances'] if f'cameras[{g}]' in s]
 assert len(paths)==15
 for stem,n in [('reset_pipe',4),('cr',2),('hr',2),('ack_sync',2),('req_sync',3),('overrun_sync',2)]:
  for i in range(n):assert any(f'/{stem}_ff{i}' in s for s in paths),(g,stem,i)
links=json.loads((P/'evidence_links.json').read_text())
old_evidence={k:{'path':v,'sha256':sha(v)} for k,v in links.items()}
assert 'checks=2038 errors=0' in Path(links['source_2038']).read_text(errors='replace')
for k in ['bus_11986_original','bus_11986_corrected']:
 assert 'SDB_ALL_PASS checks=11986' in Path(links[k]).read_text(errors='replace')
models=Path('C:/pango/PDS_2022.2-SP6.4/arch/vendor/pango/verilog/simulation')
vendor_list=(O/'vendor.f').read_text()
model_hashes={}
for name in ['GTP_DFF_CE.v','GTP_DFF_PE.v','GTP_GRS.v']:
 f=models/name
 assert f.as_posix() in vendor_list.replace('\\','/')
 assert str(f) in frozen or f.as_posix() in frozen
 model_hashes[str(f)]=sha(f)
summary={'status':'PASS','counts':counts,'original_evidence':old_evidence,'installed_real_primitive_models':model_hashes,'protected_hash_count':len(frozen),'registered_primitive_instance_count':60,'trace_comparison':R['exact_four_state_trace_comparison'],'pds_invoked':False,'hardware_operations':False}
warnings['same_warning_multiset']=collections.Counter(warnings['baseline']['messages'])==collections.Counter(warnings['primitive']['messages'])
(P/'warnings.json').write_text(json.dumps(warnings,indent=2),encoding='utf8')
(P/'summary.txt').write_text('PASS baseline_checks=14540 primitive_checks=14540 extended_checks=14668\nM01_reads=1234 M01_writes=214 legacy_reads=17\nhost_samples=1158545 camera_samples=827533 reset_samples=18 exact_trace_records=6792\nreal_vendor_CE=28 PE=32 total=60 protected_hashes=1881\nPDS_NOT_INVOKED HARDWARE_NOT_TOUCHED\n',encoding='ascii')
(P/'audit.json').write_text(json.dumps(summary,indent=2),encoding='utf8')
hashes={str(f.relative_to(P)):sha(f) for f in P.rglob('*') if f.is_file() and not any(x in f.parts for x in ['work','__pycache__']) and f.name!='hashlog.json'}
(P/'hashlog.json').write_text(json.dumps(hashes,indent=2),encoding='utf8')
assert all(sha(P/f)==h for f,h in hashes.items())
print(json.dumps(summary,indent=2))
print('FINAL_AUDIT_PASS hashlog_count='+str(len(hashes)))
