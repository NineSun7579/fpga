"""Supplement independent pair proofs, including hidden LUT6QQ first stages."""
import json,collections
from pathlib import Path
import run,audit_final
E=Path(__file__).resolve().parent/'evidence'
def main():
    run.verify()
    sy=json.loads((E/'synthesis/analysis/graph.json').read_bytes())
    mg=json.loads((E/'mapping/analysis/graph.json').read_bytes())
    topo=json.loads((E/'mapping_topology.json').read_bytes())
    by={(r['camera'],r['chain'],r['bit']):r for r in topo['rows']};pairs=[]
    for key,r in by.items():
        cam,chain,bit=key
        if bit%2:continue
        nxt=by.get((cam,chain,bit+1))
        if not nxt:continue
        common=set(r['cells'])&set(nxt['cells'])
        if common:cell=next(iter(common))
        else:
            candidates=[c for c in nxt['cells'] if mg['primitives'][c]['type']=='gopLUT6QQ']
            if len(candidates)!=1:continue
            cell=candidates[0]
        rec=mg['primitives'][cell];params=audit_final.parameters(rec)
        first=r['expected_instance'];second=nxt['expected_instance'];pn=sy['pin_net'];reset='C' if chain in {'ack_sync','req_sync','overrun_sync'} else 'P'
        checks={'synthesis_adjacent_Q_to_D':pn[first+'/Q']==pn[second+'/D'],'same_synthesis_clock':pn[first+'/CLK']==pn[second+'/CLK'],'same_synthesis_reset':pn[first+'/'+reset]==pn[second+'/'+reset]}
        if rec['type']=='gopLUT6QQ':
            output=mg['pin_net'].get(cell+'/L6QQ')
            checks.update({'mapped_second_output_alias':nxt['q_alias'] in mg['net_aliases'].get(output,[]) or '/@'+nxt['logical'] in mg['net_aliases'].get(output,[]),'internal_serial_FFAPP':params.get('FFAPPMUX_SEL')=='SRQ','both_async_SET_INIT1':params.get('FF_RS')=='SET' and params.get('FFAPP_RS')=='SET' and params.get('FF_INIT')=='1' and params.get('FFAPP_INIT')=='1' and params.get('RS_MODE')=='ASYNC','LUT_identity_I0':params.get('INIT')=='10'*32,'mapped_I0_zero':audit_final.evaluate(mg,mg['pin_net'].get(cell+'/I0'),audit_final.parameters)==0})
            if chain=='reset_pipe':
                following=by[(cam,chain,bit+2)]
                expectedD=following['expected_instance']+'/D'
                checks['mapped_second_output_alias']=pn[second+'/Q']==pn[expectedD] and len(following['cells'])==1 and output is not None and mg['pin_net'].get(following['cells'][0]+'/D')==output
        else:checks['actual_same_SRL2']=len(common)==1 and 'SRL2' in rec['type']
        pairs.append({'logical_pair':[r['logical'],nxt['logical']],'mapped_cell':cell,'type':rec['type'],'actual_parameters':params,'checks':checks})
    result={'packed_pairs':len(pairs),'packed_stages':2*len(pairs),'packed_physical_types':dict(collections.Counter(r['type'] for r in pairs)),'all_pair_proofs_passed':all(all(r['checks'].values()) for r in pairs),'rows':pairs,'graph_sha256':{s:run.sha(E/s/'analysis/graph.json') for s in ['synthesis','mapping']},'boundary':'Hidden LUT6QQ first-stage binding requires actual FFAPP serial mux, two SET/INIT parameters and second-output alias; no independent D endpoint assumed.'}
    run.save('packing_pair_complete_witnesses.json',result)
    assert result['packed_pairs']==28 and result['all_pair_proofs_passed'],result
    print('完整逐对核验通过：28 对 / 56 级，16 SRL2 + 12 LUT6QQ')
if __name__=='__main__':main()
