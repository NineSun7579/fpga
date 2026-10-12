"""Resolve mapped register channels through actual preserved net aliases."""
from pathlib import Path
import json,collections
ROOT=Path(__file__).resolve().parent/'fixed_06'
OUT=ROOT/'map_audit14'
def main():
    g=json.loads((OUT/'actual/analysis/graph.json').read_bytes())
    m=json.loads((ROOT/'synthesis_epoch10/actual/analysis/manifest.json').read_bytes())
    old=json.loads((ROOT/'synthesis_epoch10/actual/analysis/graph.json').read_bytes())
    aliases={a:n for n,aa in g['net_aliases'].items() for a in aa}
    prim,pn,np=g['primitives'],g['pin_net'],g['netpins']
    def outputs(net):
        return [p for p in np[net] if prim[p.rsplit('/',1)[0]]['ports'][p.rsplit('/',1)[1]]['direction']=='OUTPUT']
    def resolve_net(cell):
        name='/@'+cell
        assert name in aliases,(cell,name)
        return aliases[name],name
    rows=[];pairs=set();channels=set();errors=[]
    for r in m['resolved']:
        rec={'camera':r['camera'],'logical_bit':r['logical_bit'],'kind':r['mapping']['kind']}
        if rec['kind']=='register':
            a=r['mapping'];qn,qa=resolve_net(a['launch_cell']);hn,ha=resolve_net(a['capture_cell'])
            launch=outputs(qn);capture=outputs(hn)
            assert len(launch)==len(capture)==1,(r['camera'],r['logical_bit'],launch,capture)
            lcell,lport=launch[0].rsplit('/',1);hcell,hport=capture[0].rsplit('/',1)
            assert lport in {'Q','L5Q','L6Q','AQ','BQ'},(lcell,lport)
            assert hport in {'Q','L5Q','L6Q','AQ','BQ'},(hcell,hport)
            assert 'CLK' in prim[lcell]['ports'] and 'CLK' in prim[hcell]['ports']
            assert 'D' in prim[hcell]['ports'],hcell
            d=hcell+'/D';assert pn[d]==qn,(d,qn,pn[d])
            assert {p for p in np[qn] if prim[p.rsplit('/',1)[0]]['ports'][p.rsplit('/',1)[1]]['direction']=='INPUT'}=={d},np[qn]
            clk=lcell+'/CLK'
            rec.update({'launch_CLK':clk,'launch_Q':launch[0],'capture_D':d,'capture_Q':capture[0],'launch_type':prim[lcell]['type'],'capture_type':prim[hcell]['type'],'preserved_aliases':[qa,ha],'launch_clock_net':pn[clk],'capture_clock_net':pn[hcell+'/CLK']})
            pairs.add((clk,d));channels.add((launch[0],d))
        rows.append(rec)
    assert len(rows)==2048 and len(pairs)==len(channels)==1280,(len(pairs),len(channels))
    result={'method':'Preserved mapped output net aliases, unique register outputs and direct unique D sinks; packed multi-Q primitives kept as separate channels','logical_readout_proof':'Synthesis exhaustive 2048-bit proof retained; mapped LUT readout re-evaluation pending','resolved':rows,'pairs':sorted(pairs),'output_channels':sorted(channels),'pair_count':len(pairs),'errors':errors,'bit_permitted':False}
    (OUT/'mapped_channel_manifest.json').write_text(json.dumps(result,indent=2))
    print('mapped logical bits',len(rows),'channels',len(channels),'CLK-to-D pairs',len(pairs),flush=True)
if __name__=='__main__':main()
