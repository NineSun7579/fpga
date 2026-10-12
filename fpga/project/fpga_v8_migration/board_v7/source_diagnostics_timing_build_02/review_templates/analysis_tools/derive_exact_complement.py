"""Structural CDC complement and grouped bundle constraints; STA validation required."""
from pathlib import Path
import json, collections
HERE=Path(__file__).resolve().parent
def main():
    g=json.loads((HERE/'graph.json').read_bytes())
    m=json.loads((HERE/'manifest.json').read_bytes())
    prim,pn,np=g['primitives'],g['pin_net'],g['netpins']
    base=(HERE/'B_one_pair.sdc').read_text().splitlines()[:-2]
    evidence=[];errors=[];lines=list(base)
    def pins(names):return '[get_pins {'+' '.join(sorted(names))+'}]'
    for camera in range(4):
        rows=[r['mapping'] for r in m['resolved'] if r['camera']==camera and r['mapping']['kind']=='register']
        pairs=sorted(set((r['launch_CLK'],r['capture_D']) for r in rows))
        assert len(pairs)==330
        mailbox={a for a,b in pairs};dest={b for a,b in pairs}
        roots={pn[a] for a in mailbox};assert len(roots)==1
        queue=list(roots);seen=set();starts=set();transparent=[];unknown=[]
        while queue:
            net=queue.pop()
            if net in seen:continue
            seen.add(net)
            for pin in np[net]:
                cell,port=pin.rsplit('/',1);r=prim[cell];typ=r['type']
                if r['ports'][port]['direction']!='INPUT':continue
                if (typ.startswith('GTP_DFF') and port=='CLK') or (typ=='GTP_DRM18K_E1' and port in ('CLKA','CLKB')):
                    starts.add(pin)
                elif typ in ('GTP_INV',) or typ.startswith(('GTP_CLKBUF','bmsKEEPBUF_Cell_')):
                    outputs=[cell+'/'+p for p,v in r['ports'].items() if v['direction']=='OUTPUT']
                    assert len(outputs)==1,(cell,outputs)
                    transparent.append({'input':pin,'output':outputs[0],'type':typ})
                    if outputs[0] in pn:queue.append(pn[outputs[0]])
                else:unknown.append({'pin':pin,'type':typ})
        assert mailbox<=starts
        for launch,capture in pairs:
            cell=launch.rsplit('/',1)[0];q=cell+'/Q'
            outputs=[p for p,v in prim[cell]['ports'].items() if v['direction']=='OUTPUT']
            assert outputs==['Q'],(cell,outputs)
            assert set(np[pn[q]])=={q,capture},(q,np[pn[q]])
            assert pn[q]==pn[capture]
        complement=starts-mailbox
        if unknown:errors.extend(unknown)
        lines.append('set_false_path -from '+pins(complement)+' -to [get_clocks {ddrphy_sysclk}]')
        lines.append('set_max_delay -datapath_only 15.238 -from '+pins(mailbox)+' -to '+pins(dest))
        lines.append('set_false_path -hold -from '+pins(mailbox)+' -to '+pins(dest))
        evidence.append({'camera':camera,'clock':f'cmos{camera+1}_pclk','clock_nets':sorted(seen),'transparent':transparent,'all_launch_pins':sorted(starts),'mailbox_launch_pins':sorted(mailbox),'complement_launch_pins':sorted(complement),'capture_D':sorted(dest),'bundle_pairs':pairs,'unknown_clock_sinks':unknown})
    result={'method':'U intersect (M x T) equals B because each mailbox Q has exactly one host_bank D sink; U minus B is (S minus M) x T. S enumerates DFF and DRM clock launch pins, including inverted/buffered camera clock nets. No input delay commands associate input ports to camera clocks. Nonstandard clock sinks block acceptance.','cameras':evidence,'errors':errors,'status':'structural candidate; STA and clock enumeration comparison pending'}
    (HERE/'exact_complement.json').write_text(json.dumps(result,indent=2))
    if errors:raise RuntimeError(errors)
    (HERE/'B_exact_grouped.sdc').write_text('\n'.join(lines)+'\n')
    print([(e['camera'],len(e['all_launch_pins']),len(e['complement_launch_pins']),len(e['bundle_pairs'])) for e in evidence])
if __name__=='__main__':main()
