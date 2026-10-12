from pathlib import Path
import json,shutil,re,hashlib
HERE=Path(__file__).resolve().parent;BUILD=HERE.parent
def q(s):return '{'+s+'}'
def setup_trial(name,mode='A',hold=True,value='15.238'):
    d=HERE/(name+'_inputs');d.mkdir(exist_ok=False)
    db=d/'synthesis.adf';shutil.copy2(BUILD/'synthesize/v7_sdt_top_syn.adf',db)
    files=[]
    for f in (BUILD/'inputs/source/constraints').glob('*.fdc'):
        dest=d/f.name;b=f.read_bytes()
        if f.name=='clock.fdc' and mode!='A':
            b=b'\n'.join(x for x in b.split(b'\n') if not re.search(rb'^\s*set_clock_groups -name (cmos[1-4]_pclk|ddrphy_sysclk) ',x))
            cams=['cmos%d_pclk'%i for i in range(1,5)];other=['free_clk','cam1_sccb','cam2_sccb','cam3_sccb','cam4_sccb','clk_150m','rst_clk','phy_dq_clk_0','phy_dq_sysclk_0','phy_dq_clk_1','phy_dq_sysclk_1','sfp_fabric','pclk','pclk_div2','ref_clk']
            b+=('\nset_clock_groups -asynchronous -group [get_clocks {'+' '.join(cams)+'}] -group [get_clocks {'+' '.join(other)+'}]\n').encode()
            b+=('\nset_clock_groups -asynchronous -group [get_clocks {ddrphy_sysclk}] -group [get_clocks {'+' '.join(other)+'}]\n').encode()
            for i in range(4):
                b+=f'set_false_path -from [get_clocks {{ddrphy_sysclk}}] -to [get_clocks {{{cams[i]}}}]\n'.encode()
                for j in range(i+1,4):b+=f'set_clock_groups -asynchronous -group [get_clocks {{{cams[i]}}}] -group [get_clocks {{{cams[j]}}}]\n'.encode()
            if mode=='D':
                for c in cams:b+=f'set_clock_groups -asynchronous -allow_paths -group [get_clocks {{{c}}}] -group [get_clocks {{ddrphy_sysclk}}]\n'.encode()
        dest.write_bytes(b);files.append(dest)
    o=json.loads((HERE/'objects.json').read_bytes());bundles=[r for r in o['bundles'] if r['direct_q_to_d']]
    f=d/'bundle.fdc';lines=[]
    for r in bundles:
        a=r['launch']['pins']['CLK'];b=r['capture']['pins']['D']
        # PDS FDC uses '.' to delimit hierarchy (as original clock.fdc); report queries use '/'.
        a=a.rsplit('/',1)[0].replace('/','.')+'/'+a.rsplit('/',1)[1]
        b=b.rsplit('/',1)[0].replace('/','.')+'/'+b.rsplit('/',1)[1]
        lines.append(f'set_max_delay -datapath_only {value} -from [get_pins {q(a)}] -to [get_pins {q(b)}]')
        if hold:lines.append(f'set_false_path -hold -from [get_pins {q(a)}] -to [get_pins {q(b)}]')
    f.write_text('\n'.join(lines)+'\n');files.append(f)
    # Initial tests of precedence only; complement must be added before any candidate is accepted.
    launch=[r['launch']['pins']['CLK'] for r in bundles];capture=[r['capture']['pins']['D'] for r in bundles]
    script='set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG484\n'
    for f in files:script+='add_constraint '+q(f.as_posix())+'\n'
    script+='report_timing -of_flow synthesize -input_db_file '+q(db.as_posix())+' -force_to_run -delay_type min_max -nworst 1 -max_path 10000 -input_pins TRUE -report_exception TRUE -from {'+' '.join(q(p) for p in launch)+'} -to {'+' '.join(q(p) for p in capture)+'}\n'
    (HERE/(name+'.tcl')).write_text(script)
    return name
if __name__=='__main__':setup_trial('A_original')
