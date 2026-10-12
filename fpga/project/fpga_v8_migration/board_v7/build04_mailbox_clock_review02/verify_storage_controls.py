"""Check real synthesis storage controls for every1280 physical record."""
from pathlib import Path
import hashlib,json
P=Path(__file__).resolve().parent;S=P.parent/'source_diagnostics_timing_build_04'
def load(p):return json.loads(p.read_bytes())
g=load(S/'evidence/runtime/actual/analysis/graph.json');m=load(P/'fresh/manifest.json');rows=[]
for cam in range(4):
 pre=f'source_diagnostics/cameras[{cam}].source/'
 regs=[r['mapping'] for r in m['resolved'] if r['camera']==cam and r['mapping']['kind']=='register']
 controls={}
 for key in ['launch_cell','capture_cell']:
  cells={r[key] for r in regs};assert len(cells)==320
  for port in ['CLK','C','CE']:assert len({g['pin_net'][c+'/'+port] for c in cells})==1
  for c in cells:
   r=g['primitives'][c];assert r['type']=='GTP_DFF_CE' and not r['parameters']
   assert r['default_parameters']==[['PARAMETER','GRS_EN',['DATATYPE','STRING'],['STRING','"TRUE"']],['PARAMETER','INIT',['DATATYPE','BIT'],['BIT',['B','1','"0"']]]]
  controls[key]={port:g['pin_net'][next(iter(cells))+'/'+port] for port in ['CLK','C','CE']}
 assert controls['launch_cell']['CLK']!=controls['capture_cell']['CLK']
 reset_cam=pre+'cr_ff1/Q';reset_host=pre+'hr_ff1/Q'
 assert g['pin_net'][reset_cam]==controls['launch_cell']['C'] and g['pin_net'][reset_host]==controls['capture_cell']['C']
 one_net=g['pin_net'][pre+'mailbox[240]/D'];assert any(a.endswith('/@$constant_1') for a in g['net_aliases'][one_net])
 rows.append({'camera':cam,'physical_records':320,'all_storage_GTP_DFF_CE_INIT0_GRS_TRUE_no_override':True,'all320_common_controls':controls,'source_clear_from':reset_cam,'capture_clear_from':reset_host,'shared_representative_D_constant1_net':one_net})
(P/'actual1280_storage_control_identity.json').write_text(json.dumps({'synthesis_graph_sha256':hashlib.sha256((S/'evidence/runtime/actual/analysis/graph.json').read_bytes()).hexdigest(),'cameras':rows,'official_GTP_DFF_CE_sha256':hashlib.sha256(Path('C:/pango/PDS_2022.2-SP6.4/arch/vendor/pango/verilog/simulation/GTP_DFF_CE.v').read_bytes()).hexdigest(),'official_behavior':'GRS -> INIT0; asynchronous C ->0; CE ->D; otherwise hold; same actual controls across320 per bank/camera'},ensure_ascii=False,indent=2)+'\n',encoding='utf8')
print('PASS all1280 actual source/capture storage INIT0/GRS/control identity; four shared D=1 lanes')
