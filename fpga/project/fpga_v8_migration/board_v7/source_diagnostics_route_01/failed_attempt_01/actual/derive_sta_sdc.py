from pathlib import Path
import json,re,collections
HERE=Path(__file__).resolve().parent;BUILD=HERE.parent
def main():
    g=json.loads((HERE/'graph.json').read_bytes());m=json.loads((HERE/'manifest.json').read_bytes())
    assert len(m['resolved'])==2048 and not m['errors']
    normalized=collections.defaultdict(set)
    def key(s):return s.replace('/@','/').strip('/').replace('/','.').lower()
    for n,aa in g['net_aliases'].items():
        for a in aa:normalized[key(a)].add(n)
    changes=[];errors=[];lines=[]
    valid={'create_clock','create_generated_clock','set_clock_groups','set_clock_uncertainty','set_clock_latency','set_input_delay','set_output_delay','set_max_delay','set_min_delay','set_multicycle_path','set_false_path','set_max_skew','set_min_pulse_width','set_disable_timing'}
    def substitute(mt):
        kind,old=mt.group(1),mt.group(2)
        if kind=='ports':return mt.group()
        nets=normalized.get(key(old),set())
        if len(nets)!=1:errors.append({'kind':kind,'original':old,'matches':len(nets)});return mt.group()
        net=next(iter(nets));aa=g['net_aliases'][net]
        candidates=[p for p in g['netpins'].get(net,[]) if g['primitives'][p.rsplit('/',1)[0]]['ports'][p.rsplit('/',1)[1]]['direction']=='OUTPUT']
        if not candidates:errors.append({'kind':kind,'original':old,'error':'no primitive output'});return mt.group()
        actual=candidates[0]
        changes.append({'kind':kind,'original':old,'actual':actual})
        return '[get_pins {'+actual+'}]'
    for f in (BUILD/'inputs/source/constraints').glob('*.fdc'):
        for no,line in enumerate(f.read_bytes().decode('gbk',errors='replace').splitlines(),1):
            s=line.strip()
            if not s or s.startswith('#') or s.split()[0] not in valid:continue
            lines.append(re.sub(r'\[get_(pins|nets|ports) \{([^{}]+)\}\]',substitute,s))
    (HERE/'timing_object_translation.json').write_text(json.dumps({'changes':changes,'errors':errors},indent=2))
    pairs=sorted(set((r['mapping']['launch_CLK'],r['mapping']['capture_D']) for r in m['resolved'] if r['mapping']['kind']=='register'))
    (HERE/'baseline_timing_only.sdc').write_text('\n'.join(lines)+'\n')
    for variant in ['A','B','C','D','sensitivity']:
        base=list(lines)
        if variant!='A':
            base=[s for s in base if not re.match(r'set_clock_groups -name (cmos[1-4]_pclk|ddrphy_sysclk) ',s)]
            cams=[f'cmos{i}_pclk' for i in range(1,5)];others=['free_clk','cam1_sccb','cam2_sccb','cam3_sccb','cam4_sccb','clk_150m','rst_clk','phy_dq_clk_0','phy_dq_sysclk_0','phy_dq_clk_1','phy_dq_sysclk_1','sfp_fabric','pclk','pclk_div2','ref_clk']
            for clocks in [cams,['ddrphy_sysclk']]:base.append('set_clock_groups -asynchronous -group [get_clocks {'+' '.join(clocks)+'}] -group [get_clocks {'+' '.join(others)+'}]')
            for i,c in enumerate(cams):
                base.append(f'set_false_path -from [get_clocks {{ddrphy_sysclk}}] -to [get_clocks {{{c}}}]')
                for c2 in cams[i+1:]:base.append(f'set_clock_groups -asynchronous -group [get_clocks {{{c}}}] -group [get_clocks {{{c2}}}]')
                if variant=='D':base.append(f'set_clock_groups -asynchronous -allow_paths -group [get_clocks {{{c}}}] -group [get_clocks {{ddrphy_sysclk}}]')
        for index,(a,b) in enumerate(pairs):
            delay='0.001' if variant=='sensitivity' and index==0 else '15.238'
            base.append(f'set_max_delay -datapath_only {delay} -from [get_pins {{{a}}}] -to [get_pins {{{b}}}]')
            if variant!='C':base.append(f'set_false_path -hold -from [get_pins {{{a}}}] -to [get_pins {{{b}}}]')
            if index==0:(HERE/f'{variant}_one_pair.sdc').write_text('\n'.join(base)+'\n')
        (HERE/f'{variant}_timing_only.sdc').write_text('\n'.join(base)+'\n')
    print('original active timing lines',len(lines),'translated',len(changes),'errors',errors,'unique bundled pairs',len(pairs))
if __name__=='__main__':main()
