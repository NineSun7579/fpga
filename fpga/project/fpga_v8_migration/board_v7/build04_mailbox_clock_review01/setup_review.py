"""External offline review only. No vendor/remote commands or old-tree writes."""
from pathlib import Path
import hashlib,json,shutil,sys
sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent
BOARD=HERE.parent
B04=BOARD/'source_diagnostics_timing_build_04'
PREP=BOARD/'build04_route_prepare01'
def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for block in iter(lambda:f.read(4*1024*1024),b''):h.update(block)
    return h.hexdigest()
def save(p,v):
    p=HERE/p;p.parent.mkdir(parents=True,exist_ok=True)
    if p.exists():
        if json.loads(p.read_bytes())==json.loads(json.dumps(v,ensure_ascii=True)):return
        raise RuntimeError('Refuse changed evidence overwrite: '+str(p))
    with p.open('x',encoding='ascii') as f:json.dump(v,f,indent=2,ensure_ascii=True);f.write('\n')
def main():
    a=HERE/'analysis';a.mkdir()
    binding={}
    def bind(p):binding[str(p.resolve())]=sha(p)
    for n in ['graph_adapter.py','resolve_manifest.py','derive_new_constraints.py','endpoint_logic.py','endpoint_detail.py','endpoints.py','preflight.py']:
        p=PREP/'offline_fresh_synthesis/analysis'/n;bind(p);shutil.copy2(p,a/n)
    for n in ['graph.json','objects.json']:
        p=B04/'evidence/runtime/actual/analysis'/n;bind(p);shutil.copy2(p,a/n)
    for stage in ['compile','actual','mapping60_01/mapping']:
        root=B04/'evidence/runtime'/stage
        for n in ['analysis/graph.json','synthesis_export/synthesis_dump.txt','synthesis_export/synthesis_dump.v']:
            bind(root/n)
    for n in ['manifest.json','source04hash.json','inputs/source/constraints/clock.fdc','rtl/v7_sfd_candidate.v','evidence/runtime/mapping60_01/final_result.json','compile/v7_sdt_top_comp.adf','synthesize/v7_sdt_top_syn.adf','evidence/runtime/mapping60_01/isolated_mapping_work/device_map/v7_sdt_top_map.adf']:
        bind(B04/n)
    for n in ['REVIEW_PLAN_ZH.md','offline_bridge_step1.log','actual_offline_inventory.json']:bind(PREP/n)
    for bn in ['01','03']:
        root=BOARD/f'source_diagnostics_timing_build_{bn}'
        for n in ['rtl/v7_sfd_candidate.v','manifest.json']:
            bind(root/n)
    old=BOARD/'source_diagnostics_timing_build_01/evidence/actual/analysis'
    for n in ['graph.json','manifest.json']:bind(old/n)
    bind(Path('C:/pango/PDS_2022.2-SP6.4/arch/lib/bms/verilog/bmsPrim.v'))
    manifest=json.loads((B04/'manifest.json').read_bytes())
    source_check=[]
    for rel,h in manifest['full_source_copy_hashes'].items():
        p=B04/rel;actual=sha(p);bind(p);source_check.append({'path':rel,'expected':h,'actual':actual,'match':h==actual})
    save('source_identity.json',{'candidate_id':manifest['candidate_id'],'source_count':len(source_check),'registered_sources':manifest['registered_sources'],'registered_files':manifest['registered_files'],'full_source_checks':source_check,'source03_candidate_equal':(B04/'rtl/v7_sfd_candidate.v').read_bytes()==(BOARD/'source_diagnostics_timing_build_03/rtl/v7_sfd_candidate.v').read_bytes()})
    save('input_binding.json',binding)
    print('copied offline algorithms; bound',len(binding),'inputs')
if __name__=='__main__':main()
