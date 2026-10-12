from pathlib import Path
import json,re,collections
HERE=Path(__file__).resolve().parent
def main():
    out=HERE/'ta_B_exact_grouped_01'
    timing=json.loads((out/'bundle_max_audit.json').read_bytes())
    complement=json.loads((HERE/'exact_complement.json').read_bytes())
    manifest=json.loads((HERE/'manifest.json').read_bytes())
    old=(HERE/'baseline_timing_only.sdc').read_text().splitlines()
    new=(HERE/'B_exact_grouped.sdc').read_text().splitlines()
    removed=[s for s in old if re.match(r'set_clock_groups -name (cmos[1-4]_pclk|ddrphy_sysclk) ',s)]
    unchanged=[s for s in old if s not in removed]
    assert len(removed)==5 and all(s in new for s in unchanged)
    def relations(lines,clocks):
        edges=set()
        for line in lines:
            if not line.startswith('set_clock_groups '):continue
            groups=[set((braced or plain).split()) for braced,plain in re.findall(r'-group \[get_clocks (?:\{([^}]+)\}|([^\]]+))\]',line)]
            if len(groups)==1:groups.append(set(clocks)-groups[0])
            for a in groups:
                for b in groups:
                    if a is not b:edges|={(x,y) for x in a for y in b if x!=y}
        for line in lines:
            if line.startswith('set_false_path -from [get_clocks'):
                match=re.search(r'-from \[get_clocks \{([^}]+)\}\] -to \[get_clocks \{([^}]+)\}\]',line)
                if match:edges|={(x,y) for x in match[1].split() for y in match[2].split()}
        return edges
    clocks=[re.search(r'-name \{([^}]+)\}',s)[1] for s in old if s.startswith(('create_clock ','create_generated_clock '))]
    assert len(clocks)==20 and len(set(clocks))==20
    original_edges=relations(old,clocks);candidate_edges=relations(new,clocks)
    intentional={(f'cmos{i}_pclk','ddrphy_sysclk') for i in range(1,5)}
    assert original_edges-candidate_edges==intentional
    assert not candidate_edges-original_edges
    text=(out/'bundle_max.snr').read_text(errors='replace')
    counts={name:int(count) for name,count in re.findall(r'^\s*(cmos[1-4]_pclk)\s+[0-9.]+\s+\{[^}]+\}\s+Declared\s+(\d+)',text,re.M)}
    assert not complement['errors']
    for cam in complement['cameras']:
        assert len(cam['all_launch_pins'])==counts[cam['clock']]
        assert set(cam['mailbox_launch_pins']).isdisjoint(cam['complement_launch_pins'])
    assert timing['covered_actual_pairs']==1280 and not timing['missing'] and not timing['unexpected']
    assert len(manifest['resolved'])==2048 and not manifest['errors']
    assert all(r['required'] is not None and r['required']<=15.238 and r['tco_present'] and r['setup_present'] and '15.238ns -datapath_only' in r['exception'] for r in timing['records'])
    controls={kind:json.loads((out/(kind+'_audit.json')).read_bytes()) for kind in ('ordinary','negedge','reset')}
    assert controls['ordinary']['covered']==16 and not controls['ordinary']['missing']
    assert controls['negedge']['covered_starts']==8
    result={'data_expression_slow':'validated','actual_pairs':1280,'logical_bits':2048,'clock_start_counts':counts,'unmodified_original_timing_commands':len(unchanged),'replaced_global_async_commands':removed,'clock_relation_matrix':{'clocks':clocks,'original_exempt_directed_pairs':sorted(original_edges),'candidate_global_exempt_directed_pairs':sorted(candidate_edges),'only_global_relations_migrated_to_path_complement':sorted(intentional)},'control_checks':{kind:dict(collections.Counter(r['check'] for r in info['records'])) for kind,info in controls.items()},'blockers':['Compile Sdm-2008 explicitly ignores ASYNC_REG; synthesis dump has zero ASYNC_REG occurrences.','Synthesis reports use a single Slow corner; Fast and routed checks remain open.','No PNR preparation or launch: full physical prerequisite gates have not closed.'],'limits':['Graph clock-sink enumeration agrees with TA load counts. This is not a routed signoff. The two clocks remain asynchronous; the mailbox bound uses datapath_only.']}
    (HERE/'candidate_validation.json').write_text(json.dumps(result,indent=2))
    print(json.dumps({k:v for k,v in result.items() if k!='clock_relation_matrix'},indent=2))
if __name__=='__main__':main()
