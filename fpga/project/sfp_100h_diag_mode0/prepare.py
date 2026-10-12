"""Read-only production inspection; all writes stay in this private directory."""
from pathlib import Path
import argparse, hashlib, json, re, shutil

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
C = ROOT / 'sim/sfp_100h_candidate'
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p, obj): p.write_text(json.dumps(obj, indent=2), encoding='utf8')

def main(mode=0):
    if (HERE/'input_sha256.json').exists():
        raise RuntimeError('Already prepared; use build.py --check; do not overwrite this snapshot')
    for row in json.loads((C/'manifest.json').read_text()).values():
        assert sha(Path(row['source'])) == row['sha256'], row['source']
    original = {}
    for tree in ('source', 'ipcore'):
        for p in (ROOT/tree).rglob('*'):
            if p.is_file(): original[str(p)] = sha(p)
        shutil.copytree(ROOT/tree, HERE/tree)
    for rel in ('top.v','sfp/sfp_rx_link.v','preprocess/prep_regs.v',
                'sfp/rx_symbol_candidate.sv','sfp/sfp_rx_diagnostics.sv'):
        shutil.copy2(C/'candidate'/rel, HERE/'source'/rel)
    assert re.search(rb'parameter\s+SFP_NEW_PARSER\s*=\s*0', (HERE/'source/top.v').read_bytes())
    if mode:
        top=HERE/'source/top.v'
        top.write_bytes(re.sub(rb'(parameter\s+SFP_NEW_PARSER\s*=\s*)0',rb'\g<1>1',top.read_bytes(),count=1))
    work = HERE/'work'; work.mkdir()
    base = ROOT/'project_build/project.pds'
    original[str(base)] = sha(base)
    pds = base.read_bytes()
    # Delete complete runtime output/status nodes, preserving configuration bytes.
    spans = []
    for m in re.finditer(rb'\((_db_output|_output|_gci_state)\b', pds):
        depth=0; quoted=False; end=m.start()
        for end in range(m.start(), len(pds)):
            b=pds[end]
            if b==34: quoted=not quoted
            if not quoted:
                if b==40: depth+=1
                elif b==41:
                    depth-=1
                    if depth==0: break
        spans.append((m.start(),end+1))
    for start,end in reversed(spans): pds=pds[:start]+pds[end:]
    insert=b'\n'.join(b'                (_file "../source/'+n+b'" (_format systemverilog))' for n in
                         (b'sfp/rx_symbol_candidate.sv',b'sfp/sfp_rx_diagnostics.sv'))
    pos=pds.index(b'                (_file ')
    pds=pds[:pos]+insert+b'\n'+pds[pos:]
    # Clock-group false paths override max-delay; expose the new RX/host crossing.
    clock=HERE/'source/constraints/clock.fdc'
    raw=clock.read_bytes()
    names=[]; kept=[]
    for line in raw.splitlines(keepends=True):
        if line.strip().startswith(b'set_clock_groups '):
            m=re.search(rb'-name\s+(\w+)',line); assert m
            names.append(m[1].decode())
        else: kept.append(line)
    added=['\n# Private diagnostic CDC: preserve original asynchronous pairs except RX/PCIe.']
    all_names=[m[1].decode() for m in re.finditer(rb'^\s*create_(?:generated_)?clock\s+-name\s+\{([^}]+)\}',raw,re.M)]
    pairs=set()
    for a in names:
        for b in all_names:
            if a==b: continue
            pair=tuple(sorted((a,b)))
            if pair in pairs: continue
            pairs.add(pair)
            if {a,b}=={'sfp_fabric','ddrphy_sysclk'}: continue
            added.append(f'set_clock_groups -asynchronous -group [get_clocks {{{a}}}] -group [get_clocks {{{b}}}]')
    added += ['# Held data changes with ack; host consumes after two data stages and ack equality.',
              '# Host axi_clk=core_clk is DDR ddrphy_sysclk, period 7.619 ns; 4 ns is conservative.',
              '# Only handshake first stages are false-pathed; data and second stages remain timed.',
              'set_false_path -from [get_cells -hierarchical {*u_sfp_diag/req/*}] -to [get_cells -hierarchical {*u_sfp_diag/req_sync[[]0[]]/*}]',
              'set_false_path -from [get_cells -hierarchical {*u_sfp_diag/ack/*}] -to [get_cells -hierarchical {*u_sfp_diag/ack_sync[[]0[]]/*}]',
              'set_max_delay 4.000 -datapath_only -from [get_cells -hierarchical {*u_sfp_diag*held*}] -to [get_cells -hierarchical {*u_sfp_diag*data_sync0*}]',
              'set_min_delay 0.000 -from [get_cells -hierarchical {*u_sfp_diag*held*}] -to [get_cells -hierarchical {*u_sfp_diag*data_sync0*}]',
              '']
    clock.write_bytes(b''.join(kept)+'\n'.join(added).encode('ascii'))
    (work/'project.pds').write_bytes(pds)
    # Every registered input/IP item must resolve inside the isolated snapshot.
    refs=re.findall(rb'"(\.\./(?:source|ipcore)/[^"\r\n]+)"',pds)
    for ref in refs:
        p=(work/ref.decode('ascii')).resolve()
        assert p.is_file() and HERE in p.parents, p
    # Latest successful 192245 output is still in project_build; previous_* is older.
    baseline=HERE/'baseline'; baseline.mkdir()
    for name in ('top_prr.prt','top_pnr.adf'):
        p=ROOT/'project_build/place_route'/name
        original[str(p)]=sha(p); shutil.copy2(p,baseline/name)
    for name in ('project.pds','source_sha256.json','top_timing_summary_after_hold_fix.txt','bit.log','pnr.log'):
        shutil.copy2(ROOT/'bitstream_six_recovery_20261002_192245'/name,baseline/name)
    save(baseline/'provenance.json',{'route_source':str(ROOT/'project_build/place_route'),
         'route_sha256':sha(baseline/'top_pnr.adf'), 'pin_sha256':sha(baseline/'top_prr.prt'),
         'note':'192245 final route retained in project_build; archive previous_place_route is NOT its final route'})
    # Run copied tests; never write into candidate-author directories.
    sim=HERE/'sim'; sim.mkdir()
    for name in ('sfp_100h_candidate','sfp_align','sfp_payload_probe','sfp_diag','cdc_pixel_repro'):
        shutil.copytree(ROOT/'sim'/name,sim/name,ignore=shutil.ignore_patterns('__pycache__','e2ework','regwork','work'))
    save(HERE/'original_sha256.json',original)
    inputs={p.relative_to(HERE).as_posix():sha(p) for tree in ('source','ipcore') for p in (HERE/tree).rglob('*') if p.is_file()}
    inputs['work/project.pds']=sha(work/'project.pds')
    save(HERE/'input_sha256.json',inputs)
    save(HERE/'status.json',{'status':'prepared_no_pds_launch','mode':mode,'registered_input_references':len(refs)})
    for name,h in original.items(): assert sha(Path(name))==h,name
    print('Prepared isolated mode 0; no PDS launched; original hashes unchanged')

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--mode',type=int,choices=(0,1),default=0);args=parser.parse_args()
    if args.mode==1:
        HERE=ROOT/'sfp_100h_diag_mode1'
        HERE.mkdir(exist_ok=False)
        for name in ('prepare.py','build.py','build.ps1','README.md'):
            if (Path(__file__).parent/name).exists(): shutil.copy2(Path(__file__).parent/name,HERE/name)
    main(args.mode)
