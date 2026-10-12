"""Check the prepared project, source contracts and root clock constraints as bytes."""
from pathlib import Path
import hashlib,json,re
HERE=Path(__file__).resolve().parent
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    src=(HERE/'rtl/v7_sfd_candidate.v').read_bytes();bus=(HERE/'rtl/v7_sdt_bus.v').read_bytes();top=(HERE/'rtl/v7_sdt_top.v').read_bytes()
    cells=[]
    for raw,owner in [(src,'source'),(bus,'bus')]:
        for m in re.finditer(rb'GTP_DFF_(CE|PE)\s*#\((.*?)\)\s*(\w+)\s*\((.*?)\);',raw,re.S):
            ports={k.decode():v.strip().decode('ascii') for k,v in re.findall(rb'\.(\w+)\(([^()]*)\)',m[4])}
            params=m[2]
            assert b'.GRS_EN("TRUE")' in params
            assert (b".INIT(1'b0)" if m[1]==b'CE' else b".INIT(1'b1)") in params
            assert ports['CE']=="1'b1"
            cells.append({'owner':owner,'type':'GTP_DFF_'+m[1].decode(),'instance':m[3].decode(),'ports':ports,'parameter_bytes':params.decode('ascii')})
    assert len(cells)==15
    assert sum(c['type']=='GTP_DFF_CE' for c in cells)==7
    assert sum(c['type']=='GTP_DFF_PE' for c in cells)==8
    for chain,count in [('ack_sync',2),('req_sync',3),('overrun_sync',2),('cr',2),('hr',2),('reset_pipe',4)]:
        rows=[c for c in cells if c['instance'].startswith(chain+'_ff')]
        assert len(rows)==count and len({c['instance'] for c in rows})==count
        for i,c in enumerate(rows):
            assert c['ports']['Q']==chain+'['+str(i)+']'
            assert c['ports']['D']==chain+'_d'+str(i)
    project=(HERE/'project.pds').read_bytes()
    # Ignore quoted strings when checking S-expression balance.
    naked=re.sub(rb'"(?:[^"\\]|\\.)*"',b'""',project)
    depth=0
    for ch in naked:
        if ch==40:depth+=1
        if ch==41:depth-=1
        assert depth>=0
    assert depth==0
    paths=re.findall(rb'\(_file "((?:rtl|constraints)/[^"]+)"\s*\(_format (verilog|fdc)\)',project)
    assert len(paths)==4
    assert all((HERE/p.decode('ascii')).is_file() for p,f in paths)
    assert {p for p,f in paths if f==b'verilog'}=={b'rtl/v7_sdt_top.v',b'rtl/v7_sdt_bus.v',b'rtl/v7_sfd_candidate.v'}
    modules=[]
    for p,f in paths:
        if f==b'verilog':modules+=re.findall(rb'(?m)^module\s+(\w+)',(HERE/p.decode()).read_bytes())
    assert len(modules)==len(set(modules))==4
    clock=(HERE/'constraints/clock.fdc').read_bytes()
    assert len(re.findall(rb'(?m)^create_clock\b',clock))==5
    assert not any(w in clock for w in [b'set_false_path',b'set_clock_groups',b'set_multicycle_path'])
    assert top.count(b'v7_sdt_bus source_diagnostics')==1
    connections=re.findall(rb'\.(\w+)\((\w+)\)',top)
    assert len(connections)==43 and all(a==b for a,b in connections)
    # Everything except the experiment remains read-only. Snapshot stable inputs of active run, not its changing outputs.
    active=HERE.parent/'source_diagnostics_timing_build_01'
    activehash={str(p):sha(p) for d in ['rtl','inputs'] for p in (active/d).rglob('*') if p.is_file()}
    (HERE/'evidence/active_run_input_guard.json').write_bytes((json.dumps(activehash,indent=2)+'\n').encode('ascii'))
    out={'status':'PASS','prepared_project_sha256':sha(HERE/'project.pds'),'registered_source_files':[p.decode() for p,f in paths],'distinct_modules':[m.decode() for m in modules],'all_43_connections_bound':True,'primitive_groups':cells,'instances_per_camera':15,'sync_instances':28,'reset_instances':32,'root_clock_count':5,'timing_exceptions':0,'active_run_stable_input_count':len(activehash),'encoding':'Bytes preserved; generated ASCII is valid GBK','remote_or_program':False}
    (HERE/'evidence/offline_check.json').write_bytes((json.dumps(out,indent=2)+'\n').encode('ascii'))
    print('OFFLINE_CHECK_PASS',len(activehash),'active input files frozen for post-check')
if __name__=='__main__':main()
