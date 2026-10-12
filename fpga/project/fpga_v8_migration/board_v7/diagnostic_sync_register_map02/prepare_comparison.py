"""Create byte-reversible, isolated instance-attribute comparison. No PDS."""
from pathlib import Path
import hashlib,json,re,shutil
H=Path(__file__).resolve().parent
OLD=H.parent/'diagnostic_sync_register_map_01'
E=H/'evidence'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(n,v):(E/n).write_text(json.dumps(v,indent=2,ensure_ascii=True)+'\n',encoding='ascii')
def main():
    assert not (H/'project.pds').exists(),'Refuse to overwrite comparison'
    for d in ['rtl','constraints','analysis_tools','evidence']:(H/d).mkdir(exist_ok=True)
    baseline={str(p):sha(p) for p in OLD.rglob('*') if p.is_file()}
    save('map01_guard.json',baseline)
    tag=b'(* syn_noprune=1 *) '
    changes=[]
    for p in (OLD/'rtl').glob('*.v'):
        raw=p.read_bytes()
        updated,n=re.subn(rb'(?m)^(\s*)(GTP_DFF_(?:CE|PE)\s+#)',lambda m:m[1]+tag+m[2],raw)
        assert updated.replace(tag,b'')==raw,'Attribute inverse mismatch'
        (H/'rtl'/p.name).write_bytes(updated)
        changes.append({'file':p.name,'original_sha256':sha(p),'modified_sha256':sha(H/'rtl'/p.name),'inverse_sha256':hashlib.sha256(updated.replace(tag,b'')).hexdigest(),'textual_instances':n,'elaboration_multiplier':4 if n else 0})
    assert sum(x['textual_instances'] for x in changes)==15
    assert sum(x['textual_instances']*x['elaboration_multiplier'] for x in changes)==60
    targets=json.loads((OLD/'evidence/compile_topology.json').read_bytes())['rows']
    assert len(targets)==60 and len({r['expected_instance'] for r in targets})==60
    for p in (OLD/'constraints').iterdir():
        if p.is_file():shutil.copy2(p,H/'constraints'/p.name)
    shutil.copy2(OLD/'analysis_tools/parse_objects.py',H/'analysis_tools/parse_objects.py')
    shutil.copy2(OLD/'run.py',H/'run.py')
    shutil.copy2(OLD/'audit_final.py',H/'audit_final.py')
    raw=(OLD/'project.pds').read_bytes()
    # Retain official grammar/options; erase only old DB/output records and phase state.
    raw=re.sub(rb'\(_gci_state \(_integer \d+\)\)',b'(_gci_state (_integer 0))',raw)
    for key in [b'_db_output',b'_output']:
        while True:
            m=re.search(rb'\('+key+rb'\s',raw)
            if not m:break
            depth=0;quoted=False;escaped=False
            for end in range(m.start(),len(raw)):
                ch=raw[end]
                if ch==34 and not escaped:quoted=not quoted
                if not quoted:
                    if ch==40:depth+=1
                    if ch==41:
                        depth-=1
                        if depth==0:break
                escaped=(ch==92 and not escaped)
            raw=raw[:m.start()]+raw[end+1:]
    (H/'project.pds').write_bytes(raw)
    for n in ['protected_baseline.json','active_run_input_guard.json','compact_stimulus_receipt.json','official_mapping_api_review.json']:
        shutil.copy2(OLD/'evidence'/n,E/n)
    build=H.parent/'source_diagnostics_timing_build_02'
    guard={str(p):sha(p) for d in ['rtl','constraints','runtime'] for p in (build/d).rglob('*') if p.is_file() and p.suffix.lower() in {'.v','.vh','.fdc','.tcl','.py','.ps1','.pds'} and '__pycache__' not in p.parts}
    save('build02_guard.json',guard)
    save('attribute_byte_inverse.json',{'attribute':'syn_noprune=1','scope':'Only 15 textual GTP_DFF_CE/PE instances, elaborated in four cameras = 60','files':changes,'targets':[r['expected_instance'] for r in targets],'all_inverse_exact':True,'no_functional_or_cycle_change':True,'wrapper_sha256':sha(H/'rtl/v7_sdt_top.v')})
    import fitz
    pdf=Path('C:/pango/PDS_2022.2-SP6.4/doc/ADS_Synthesis_User_Guide.pdf');doc=fitz.open(pdf)
    save('instance_scope_official.json',{'pdf':str(pdf),'sha256':sha(pdf),'pages':{str(i+1):doc[i].get_text() for i in [89,90]},'claim':'syn_noprune=1 supports instance scope; physical anti-packing efficacy is to be measured, not assumed'})
    save('input_hashes.json',{str(p.relative_to(H)):sha(p) for d in ['rtl','constraints','analysis_tools'] for p in (H/d).rglob('*') if p.is_file()}|{'project.pds':sha(H/'project.pds')})
    print('隔离 map02 准备完成：60 原语实例属性；字节逆变换精确；map01 全文件冻结',flush=True)
if __name__=='__main__':main()
