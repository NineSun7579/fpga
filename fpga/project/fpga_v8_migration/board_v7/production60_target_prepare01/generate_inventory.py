"""Bind actual synthesized target identities; this does not select physical sites."""
from pathlib import Path
import hashlib,json,re

H=Path(__file__).resolve().parent
B=H.parent
M=B/'diagnostic_sync_register_map02/evidence'
S=B/'source_diagnostics_timing_build_03/rtl'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    output=H/'target_inventory.json';assert not output.exists()
    paths=[M/'synthesis_endpoint_details.json',M/'synthesis/analysis/graph.json',
           M/'synthesis/synthesis_export/synthesis_dump.txt',M/'synthesis_topology.json',
           S/'v7_sfd_candidate.v',S/'v7_sdt_bus.v',S/'v7_sdt_top.v']
    topo=json.loads(paths[3].read_bytes())
    graph=json.loads(paths[1].read_bytes())
    detail=json.loads(paths[0].read_bytes())
    candidate=(S/'v7_sfd_candidate.v').read_bytes()
    bus=(S/'v7_sdt_bus.v').read_bytes()
    targets=[]
    count={'sync':0,'reset':0}
    roles={'ack_sync':2,'req_sync':3,'overrun_sync':2,'cr':2,'hr':2,'reset_pipe':4}
    for row in detail['rows']:
        c,chain,bit=row['camera'],row['chain'],row['bit']
        assert c in range(4) and chain in roles and bit in range(roles[chain])
        target=f'source_diagnostics/cameras[{c}].'+('' if chain=='reset_pipe' else 'source/')+f'{chain}_ff{bit}'
        assert row['expected_instance']==target and row['cells']==[target]
        assert row['independent_endpoint_passed'] and row['all_proven_checks_passed']
        rec=graph['primitives'][target]
        kind='sync' if chain in {'ack_sync','req_sync','overrun_sync'} else 'reset'
        expected='GTP_DFF_C' if kind=='sync' else 'GTP_DFF_P'
        assert rec['type']==expected
        leaf=f'{chain}_ff{bit}'.encode('ascii')
        source=bus if chain=='reset_pipe' else candidate
        decls=re.findall(rb'GTP_DFF_[CP]E\s*#\s*\([^;]*?\)\s*'+leaf+rb'\s*\([^;]*?;',source,re.S)
        assert len(decls)==1,(target,'Actual source declaration ambiguous/missing')
        count[kind]+=1
        targets.append({'camera':c,'chain':chain,'bit':bit,'kind':kind,'actual_synthesized_instance':target,
                        'actual_synthesized_type':rec['type'],'actual_synthesized_ports':rec['ports'],
                        'parameters_decoded':row['parameters_decoded'],'clock_root_expected':row['clock_root_expected'],
                        'clock_root_found':row['clock_root_found'],
                        'build03_source':str(S/('v7_sdt_bus.v' if chain=='reset_pipe' else 'v7_sfd_candidate.v')),
                        'build03_primitive_declaration_ascii':decls[0].decode('ascii'),
                        'physical_site':None})
    assert count=={'sync':28,'reset':32} and len(targets)==60
    assert len({r['actual_synthesized_instance'] for r in targets})==60
    output.write_text(json.dumps({'status':'TARGET_IDENTITY_PREPARATION_ONLY','input_hashes':{str(p):sha(p) for p in paths},
                                 'counts':count,'targets':targets,'production_mapping_PASS':False,
                                 'limitation':'map02 synthesized identities correspond to build03 source declarations; full build03 candidate differs and needs fresh synthesis/mapping. No sites selected.'},indent=2),encoding='ascii')
    print('60 actual synthesized targets bound to explicit build03 primitive declarations; no physical or production PASS')

if __name__=='__main__':main()
