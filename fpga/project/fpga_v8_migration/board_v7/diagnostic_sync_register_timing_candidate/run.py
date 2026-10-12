"""ModelSim regression only. No PDS, external network, or device operations."""
from pathlib import Path
import hashlib, json, subprocess, os
P=Path(__file__).resolve().parent
F=P.parents[1]/'whole_candidate_v7_route_01'
bin_dir=Path(os.environ.get('MODELSIM_BIN','C:/modeltech64_10.6e/win64'))
manifest=json.loads((P/'evidence/frozen_inputs.json').read_text())
def verify():
    assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in manifest.items()), 'Protected input changed'
verify()
def run(exe,args,log):
    r=subprocess.run([str(bin_dir/exe),*map(str,args)],cwd=P/'sim',stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
    (P/'evidence'/log).write_bytes(r.stdout)
    print(r.stdout.decode('utf8','replace')[-4500:],flush=True)
    assert r.returncode==0,(exe,r.returncode)
    return r.stdout
run('vlib.exe',['work'],'vlib.log')
files=[F/'inputs/source/ov5640/ov5640/cmos_capture.v',F/'inputs/source/ov5640/axi_to_axi_lite.v',
       F/'rtl/ovreg_axil_decode_tc01.v',P/'rtl/v7_sfd_candidate.v',P/'rtl/v7_sdt_bus.v',
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
result['artifact_hashes']={str(p.relative_to(P)):hashlib.sha256(p.read_bytes()).hexdigest()
    for d in ['rtl','baseline','sim'] for p in (P/d).glob('*') if p.is_file() and p.suffix in ['.v','.sv','.vh']}
(P/'evidence/results.json').write_text(json.dumps(result,indent=2),encoding='utf8')
print('FROZEN_INPUT_HASHES_UNCHANGED; PDS_NOT_INVOKED')
