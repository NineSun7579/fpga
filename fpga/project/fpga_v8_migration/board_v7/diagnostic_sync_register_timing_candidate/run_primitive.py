"""Run exact installed GTP models against frozen RTL, using isolated ModelSim work."""
from pathlib import Path
import json,hashlib,subprocess,os
P=Path(__file__).resolve().parent
F=P.parents[1]/'whole_candidate_v7_route_01'
V=Path('C:/pango/PDS_2022.2-SP6.4/arch/vendor/pango/verilog/simulation')
bin_dir=Path(os.environ.get('MODELSIM_BIN','C:/modeltech64_10.6e/win64'))
manifest=json.loads((P/'evidence/frozen_inputs.json').read_text())
def verify():
    assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in manifest.items())
verify()
def run(exe,args,log):
    r=subprocess.run([str(bin_dir/exe),*map(str,args)],cwd=P/'sim_primitive',stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
    (P/'evidence'/('primitive_'+log)).write_bytes(r.stdout)
    print(r.stdout.decode('utf8','replace')[-4300:],flush=True)
    assert r.returncode==0,(exe,r.returncode)
    return r.stdout
run('vlib.exe',['work'],'vlib.log')
files=[V/'GTP_DFF_CE.v',V/'GTP_DFF_PE.v',V/'GTP_GRS.v',
       F/'inputs/source/ov5640/ov5640/cmos_capture.v',F/'inputs/source/ov5640/axi_to_axi_lite.v',
       F/'rtl/ovreg_axil_decode_tc01.v',P/'rtl_primitive/v7_sfd_candidate.v',P/'rtl_primitive/v7_sdt_bus.v',
       'baseline_source.v','baseline_bus.v','tb_source.sv','tb_bus.sv']
run('vlog.exe',['-sv',*files],'compile.log')
result={}
for tb,marker in [('tb_v7_sfd_candidate',b'DSR_SOURCE_COMPARE_PASS'),('tb_v7_sdb',b'DSR_BUS_COMPARE_PASS')]:
    data=run('vsim.exe',['-c','-voptargs=+acc',tb,'-do','onerror {quit -code 1}; run -all; quit -code 0'],tb+'.log')
    assert marker in data and b'FAIL' not in data and b'Error:' not in data
    result[tb]=[s.decode('utf8','replace') for s in data.splitlines() if b'PASS' in s or b'DONE' in s]
verify()
result['protected_inputs_unchanged']=True
result['pds_invoked']=False
result['physical_mapping_verified']=False
result['simulation_model']='Installed PDS real GTP_DFF_CE, GTP_DFF_PE, GTP_GRS; GRS_N held 1; initial asserted local resets.'
result['artifact_hashes']={str(p.relative_to(P)):hashlib.sha256(p.read_bytes()).hexdigest()
    for d in ['rtl_primitive','sim_primitive'] for p in (P/d).glob('*') if p.is_file() and p.suffix in ['.v','.sv','.vh']}
(P/'evidence/primitive_results.json').write_text(json.dumps(result,indent=2),encoding='utf8')
print('REAL_PRIMITIVE_MODELS_PASS; FROZEN_INPUT_HASHES_UNCHANGED; PDS_NOT_INVOKED')
