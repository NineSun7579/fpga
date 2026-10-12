"""Isolated byte-preserving actual RTL miter. No PDS/remote/program."""
from pathlib import Path
import hashlib, json, re, subprocess, os, difflib, importlib.util

HERE = Path(__file__).resolve().parent
BOARD = HERE.parent
PROJECT = BOARD.parents[1]
ROUTE = BOARD/'source_diagnostics_route_02'
EXACT = BOARD/'physical_subagent_evidence_01/fixed_06/physical_exact_09'
SOURCE = ROUTE/'rtl/fpga_v8_capture_lease_tc04.v'
MS = Path(os.environ.get('MODELSIM_BIN', 'C:/modeltech64_10.6e/win64'))
ART = HERE/'evidence'
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def save(name, obj): (ART/name).write_text(json.dumps(obj, indent=2, ensure_ascii=False)+'\n', encoding='utf-8')
def protected():
    roots = [PROJECT/'source', PROJECT/'ipcore', ROUTE/'rtl', ROUTE/'inputs', ROUTE/'physical_constraints_exact_09']
    files = [p for root in roots for p in root.rglob('*') if p.is_file()]
    files += [EXACT/'input_hashes.json', ROUTE/'standard_flow_exact09.pds', PROJECT/'project.pds']
    return {str(p): sha(p) for p in sorted(set(files)) if p.exists()}

def prepare():
    ART.mkdir(parents=True, exist_ok=True)
    frozen = json.loads((EXACT/'input_hashes.json').read_bytes())
    assert sha(SOURCE) == frozen['rtl\\fpga_v8_capture_lease_tc04.v']
    top = ROUTE/'rtl/fpga_v8_cooperative_top_v2_rfg01.v'
    assert sha(top) == frozen['rtl\\fpga_v8_cooperative_top_v2_rfg01.v']
    assert re.search(rb'fpga_v8_capture_lease_tc04\s*#\([\s\S]*?\)\s*u_v8_capture_lease\s*\(', top.read_bytes())
    save('protected_before.json', protected())
    save('frozen_binding.json', dict(source=str(SOURCE), source_sha256=sha(SOURCE), top=str(top), top_sha256=sha(top), frozen_manifest=str(EXACT/'input_hashes.json'), frozen_manifest_sha256=sha(EXACT/'input_hashes.json')))
    original = HERE/'original/fpga_v8_capture_lease_tc04.v'
    candidate = HERE/'candidate/fpga_v8_capture_lease_prefix.v'
    original.parent.mkdir(exist_ok=True); candidate.parent.mkdir(exist_ok=True)
    raw = SOURCE.read_bytes(); original.write_bytes(raw)
    nl = b'\r\n' if b'\r\n' in raw else b'\n'
    text = raw.decode('ascii').replace('\r\n','\n')
    text = text.replace('module fpga_v8_capture_lease_tc04 #(', 'module fpga_v8_capture_lease_prefix #(', 1)
    text = text.replace('    genvar chunk;', '''    // Exact CURRENT count predicates. Reset dominates every event.
    // Configuration, generation restart, retirement/abort and releases do not
    // assign published_count in the frozen RTL; they hold these predicates too.
    reg [7:1] published_prefix;
    genvar prefix;
    generate for (prefix=1; prefix<8; prefix=prefix+1) begin : prefix_predicates
        // (C_low + 1) is all ones iff C_low is all ones except bit zero.
        // This decode uses only registered count; late publish selects it.
        wire before_all_ones = (&published_count[prefix*4-1:1]) &&
                               !published_count[0];
        always @(posedge clk) begin
            if (rst) published_prefix[prefix] <= 1'b0;
            else if (publish_success)
                published_prefix[prefix] <= before_all_ones;
        end
    end endgenerate
    genvar chunk;''', 1)
    text = text.replace('publish_success && (&published_count[chunk*4-1:0])', 'publish_success && published_prefix[chunk]')
    candidate.write_bytes(text.replace('\n', nl.decode()).encode('ascii'))
    assert original.read_bytes() == raw
    (ART/'candidate.diff').write_text(''.join(difflib.unified_diff(raw.decode().splitlines(True),candidate.read_bytes().decode().splitlines(True),fromfile='original/fpga_v8_capture_lease_tc04.v',tofile='candidate/fpga_v8_capture_lease_prefix.v')),encoding='ascii')
    spec = importlib.util.spec_from_file_location('old_regression', PROJECT/'fpga_v8_migration/timing_correction_04/tests/run_lease_tests.py')
    old = importlib.util.module_from_spec(spec); spec.loader.exec_module(old)
    old.REF = original
    tb, outputs = old.bench()
    # Only the dut module changes; reference is the byte-identical actual tc04.
    assert tb.count('fpga_v8_capture_lease_tc04 #') == 1
    tb = tb.replace('fpga_v8_capture_lease_tc04 #', 'fpga_v8_capture_lease_prefix #')
    tb = tb.replace('fpga_v8_capture_lease #', 'fpga_v8_capture_lease_tc04 #')
    checks = []
    scalar = ['generation','next_sequence','writing_bank','coop_offer_bank','host_offer_bank','coop_rr','host_rr','writing_eligible','next_nonzero','next_last']
    arrays = ['state','sequence','coop_claimed','coop_released','host_claimed','host_released']
    for name in scalar:
        checks.append(f'if(reference.{name} !== dut.{name}) $fatal(1,"state {name} cycle=%0d",cycles);')
    for name in arrays:
        for i in range(2):
            ident = '\\sequence ' if name == 'sequence' else name
            checks.append(f'if(reference.{ident}[{i}] !== dut.{ident}[{i}]) $fatal(1,"state {name}[{i}] cycle=%0d",cycles);')
    for i in range(1,8):
        checks.append(f'if(dut.published_prefix[{i}] !== (&dut.published_count[{i*4-1}:0])) $fatal(1,"prefix invariant width={i*4} cycle=%0d count=%h prefix=%b",cycles,dut.published_count,dut.published_prefix);')
    tb = tb.replace('end endtask', '\n'.join(checks)+'\nend endtask',1)
    tb = tb.replace('dut.next_nonzero=(seq_value!=0);', 'reference.next_nonzero=(seq_value!=0); reference.next_last=(seq_value==32\'hffffffff);\n    dut.next_nonzero=(seq_value!=0);')
    init = '\n'.join(f'    dut.published_prefix[{i}]=(&count_value[{i*4-1}:0]);' for i in range(1,8))
    tb = tb.replace('reference.published_count=count_value; dut.published_count=count_value;', 'reference.published_count=count_value; dut.published_count=count_value;\n'+init)
    tb = tb.replace('// Accelerated boundary setup only: preserve every redundant invariant.', '''// One-time idle state deposit on BOTH actual RTL instances, no force.
    // Count represents a compressed prior lifetime of completed publications.
    if(reference.state[0]!=0 || reference.state[1]!=0 || publish || rst ||
       reference.epoch_start || reference.input_valid || reference.host_valid)
        $fatal(1,"boundary setup requires quiescent legal state");
    if(seq_value==0) begin reference.armed=0; dut.armed=0; end''')
    tb = tb.replace('if(ref_published_count !== ((64\'h1<<(n*4)) & 32\'hffffffff))', '$display("PREFIX_CARRY width=%0d count=%h prefix=%b",n*4,ref_published_count,dut.published_prefix);\n            if(ref_published_count !== ((64\'h1<<(n*4)) & 32\'hffffffff))')
    extra = '''
        // Enter all-ones from all-ones-minus-one, hold, and leave across carry.
        // Every prefix width is checked on both sides of the publication edge.
        for(n=1;n<=8;n=n+1) begin
            reset_all; arm; boundary(1,(64'h1<<(n*4))-2);
            start_bank(0); publish_good;
            if(ref_published_count!==(((64'h1<<(n*4))-1)&32'hffffffff))
                $fatal(1,"prefix enter-all-ones count");
            $display("PREFIX_ENTER_ONES width=%0d count=%h prefix=%b",n*4,ref_published_count,dut.published_prefix);
            repeat(3) tick; claims; release_id(0);
            release_valid=1; host_release_valid=HOST_REQUIRED; tick;
            clear_events; tick; start_bank(1); publish_good;
            if(ref_published_count!==((64'h1<<(n*4))&32'hffffffff))
                $fatal(1,"prefix leave-all-ones count");
            $display("PREFIX_LEAVE_ONES width=%0d count=%h prefix=%b",n*4,ref_published_count,dut.published_prefix);
        end
        // Reset wins over valid publication, config and error, at full carry.
        reset_all; arm; boundary(1,32'hffffffff); start_bank(0);
        rst=1; publish=1; publish_seq=1; config_valid=1;
        config_generation=52; retired_error=1; tick;
        if(ref_published_count!=0 || ref_config_accept || ref_failed_count!=0)
            $fatal(1,"reset/config/publish/error priority");
        $display("PREFIX_RESET_PRIORITY_PASS");
        rst=0; clear_events; tick;
        // Legal idle reconfiguration plus invalid publication: no count change.
        reset_all; arm; boundary(1,32'hfffffffe);
        config_valid=1; config_generation=52; publish=1; publish_seq=1;
        retired_error=1; tick;
        if(!ref_config_accept || !ref_protocol_fault || ref_published_count!=32'hfffffffe)
            $fatal(1,"config/publish/error priority");
        $display("PREFIX_CONFIG_PUBLISH_PRIORITY_PASS");
        // Abort/rollback retains count and predicates, following SOF is legal.
        reset_all; arm; boundary(1,32'hfffffffe); start_bank(0);
        retired_error=1; tick; clear_events; tick;
        if(ref_bank0_state!=0 || ref_published_count!=32'hfffffffe || ref_failed_count!=1)
            $fatal(1,"abort changed count");
        start_bank(0); publish_good; claims;
        release_id(0); release_valid=1; host_release_valid=HOST_REQUIRED; tick;
        clear_events; tick;
        if(ref_bank0_state!=0) $fatal(1,"dual consumer copy ack did not release");
        start_bank(1); publish_good;
        if(ref_published_count!=0) $fatal(1,"full rollover failed");
        $display("PREFIX_ABORT_COPY_ACK_ROLLOVER_PASS count=%h prefix=%b",ref_published_count,dut.published_prefix);
'''
    tb = tb.replace('        // Sustained fault-free randomized', extra+'\n        // Sustained fault-free randomized')
    tb = tb.replace('LEASE_TC04_DIFF_PASS','LEASE_PREFIX_ACTUAL_RTL_DIFF_PASS')
    (HERE/'tb_lease_prefix.sv').write_text(tb,encoding='ascii')
    stim = PROJECT/'fpga_v8_migration/timing_correction_04/tests/lease_stimulus.svh'
    save('reused_regression.json',dict(path=str(stim),sha256=sha(stim),note='actual tc04 reference and candidate; extended all-state comparisons, invariant, symmetric boundary deposits and directed priority cases'))
    paths = json.loads((EXACT/'evidence/all_reported_failing_paths.json').read_bytes())
    lease = [x for x in paths if 'u_v8_capture_lease/' in x.get('Endpoint','')]
    save('actualexact09_lease_paths.json',lease)
    collisions=[]
    for p in PROJECT.rglob('*.v'):
        if 'build' in p.parts: continue
        if b'fpga_v8_capture_lease_prefix' in re.findall(rb'\bmodule\s+(\w+)',p.read_bytes()):
            collisions.append(str(p.resolve()))
    assert collisions == [str(candidate.resolve())], collisions
    save('module_collision_scan.json',dict(candidate_module='fpga_v8_capture_lease_prefix',declarations=collisions,pass_unique=True))
    return original,candidate,outputs

def run():
    original,candidate,outputs = prepare()
    build = HERE/'build'; build.mkdir(exist_ok=True)
    commands=[]
    def command(args,name):
        p=subprocess.run([str(a) for a in args],cwd=build,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=120)
        out=p.stdout.decode('utf-8',errors='replace')
        (ART/(name+'.log')).write_text(out,encoding='utf-8')
        commands.append(dict(args=[str(a) for a in args],returncode=p.returncode))
        if p.returncode or '** Error:' in out or '** Fatal:' in out: raise RuntimeError(out[-8000:])
        return out
    command([MS/'vlib.exe','work'],'vlib')
    command([MS/'vlog.exe','-quiet','-work','work',original,candidate],'compile_actual_rtl')
    command([MS/'vlog.exe','-quiet','-sv','-work','work',HERE/'tb_lease_prefix.sv'],'compile_tb')
    results={}
    for host,bad in [(1,0),(0,0)]+[(1,k) for k in range(1,8)]:
        name=f'host{host}_bad{bad}'
        out=command([MS/'vsim.exe','-c','-quiet','-voptargs=+acc','-wlf',name+'.wlf','tb_lease_tc04',f'-gHOST_REQUIRED={host}',f'-gBAD_CFG={bad}','-do','run -all; quit -f'],name)
        marker=re.search(r'LEASE_PREFIX_ACTUAL_RTL_DIFF_PASS[^\r\n]*',out)
        if not marker: raise RuntimeError(out[-8000:])
        results[name]=marker[0]; print(name,marker[0],flush=True)
    # Negative control: this isolated mutated copy must trip the same miter.
    # Never modify the delivered candidate or force execution state.
    mutant = build/'prefix_mutant.v'
    mutant.write_bytes(candidate.read_bytes().replace(b'published_prefix[prefix] <= before_all_ones;',b"published_prefix[prefix] <= 1'b0;"))
    assert mutant.read_bytes()!=candidate.read_bytes()
    command([MS/'vlib.exe','negative'],'negative_vlib')
    command([MS/'vlog.exe','-quiet','-work','negative',original,mutant],'negative_compile_rtl')
    command([MS/'vlog.exe','-quiet','-sv','-work','negative',HERE/'tb_lease_prefix.sv'],'negative_compile_tb')
    args=[MS/'vsim.exe','-c','-quiet','-voptargs=+acc','-wlf','negative.wlf','negative.tb_lease_tc04','-do','run -all; quit -f']
    p=subprocess.run([str(a) for a in args],cwd=build,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=120)
    negative=p.stdout.decode('utf-8',errors='replace')
    (ART/'negative_control.log').write_text(negative,encoding='utf-8')
    assert 'prefix invariant' in negative and '** Fatal:' in negative and 'LEASE_PREFIX_ACTUAL_RTL_DIFF_PASS' not in negative
    save('negative_control.json',dict(expected_failure_detected=True,mutation='prefix update stuck at zero after successful publish',mutant_sha256=sha(mutant),returncode=p.returncode,args=[str(a) for a in args]))
    before=json.loads((ART/'protected_before.json').read_bytes()); after=protected()
    save('protected_after.json',after)
    assert before==after, 'Protected inputs changed'
    save('results.json',dict(pass_all=True,original_sha256=sha(original),candidate_sha256=sha(candidate),tb_sha256=sha(HERE/'tb_lease_prefix.sv'),diff_sha256=sha(ART/'candidate.diff'),public_outputs=outputs,internal_state_comparison=True,prefix_invariant_widths=[4,8,12,16,20,24,28],compare_before_after_every_edge=True,negative_control_detected=True,protected_unchanged=True,protected_files=len(after),results=results,commands=commands,limitations=['Simulation equivalence, not exhaustive formal proof','No PDS: candidate WNS unmeasured','Boundary deposits are symmetric and legal; no force during execution']))

def audit():
    results=json.loads((ART/'results.json').read_bytes())
    assert results['pass_all'] and results['negative_control_detected']
    assert sha(HERE/'original/fpga_v8_capture_lease_tc04.v')==results['original_sha256']==sha(SOURCE)
    assert sha(HERE/'candidate/fpga_v8_capture_lease_prefix.v')==results['candidate_sha256']
    assert sha(HERE/'tb_lease_prefix.sv')==results['tb_sha256']
    assert sha(ART/'candidate.diff')==results['diff_sha256']
    assert protected()==json.loads((ART/'protected_before.json').read_bytes())
    paths=[p for p in HERE.rglob('*') if p.is_file() and 'build' not in p.parts and '__pycache__' not in p.parts and p.name!='artifact_hashes.json']
    save('artifact_hashes.json',{str(p.relative_to(HERE)):sha(p) for p in sorted(paths)})
    print('FINAL_AUDIT_PASS actual frozen source, candidate, TB, diff, protected bytes and artifact hashes')

if __name__=='__main__':
    import sys
    if '--audit' in sys.argv: audit()
    else: run()
