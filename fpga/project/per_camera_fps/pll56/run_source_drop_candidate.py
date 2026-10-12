"""Single measured RTL/control-set experiment with unchanged strict build gates."""
from pathlib import Path
import json
import subprocess
import sys
import time
from counter_experiment import HERE, BASE, sha, save

def main():
    out=Path(sys.argv[1]).resolve()
    prep=json.loads((out/'preparation.json').read_bytes())
    sim_path=out/'simulation/receipt.json'
    sim=json.loads(sim_path.read_bytes())
    candidate=Path(prep['candidate'])
    assert sim['status']=='PASS'
    assert sim['candidate_sha256']==sha(candidate)==prep['candidate_sha256']
    assert sim['original_sha256']==sha(Path(prep['original']))
    assert sim['testbench_sha256']==sha(HERE/'tb_source_drop_equivalence.v')
    assert sim['log_sha256']==sha(sim_path.parent/'simulation.log')
    upstream=HERE/'build_capture_generated.py'
    text=upstream.read_bytes().decode('utf-8').replace('\r\n','\n')
    insertion='''    candidate_counter = Path(%r)
    assert sha(candidate_counter) == %r
    receipt.update(counter_original_sha256=%r, counter_candidate_sha256=%r,
                   counter_simulation_receipt=%r, counter_simulation_sha256=%r,
                   experiment_base_build=%r,
                   rtl_experiment='Same-edge source-drop counter control set to D; preserved record capture candidate',
                   rtl_override='source/ov5640/ov5640/ov5640_cdc.v; existing adapter overlay preserved')
''' % (str(candidate),sha(candidate),prep['original_sha256'],sha(candidate),str(sim_path),sha(sim_path),str(BASE))
    marker='    simulations = []\n'
    assert text.count(marker)==1
    text=text.replace(marker,insertion+marker)
    old="tempfile.mkdtemp(prefix='build_capture_', dir=HERE)"
    assert text.count(old)==1
    text=text.replace(old,"tempfile.mkdtemp(prefix='build_counter_', dir=HERE)")
    overlay="        (run / 'inputs/source/motion/motion_stream_adapter.v').write_bytes(candidate_adapter.read_bytes())\n"
    assert text.count(overlay)==1
    text=text.replace(overlay,overlay+"        (run / 'inputs/source/ov5640/ov5640/ov5640_cdc.v').write_bytes(candidate_counter.read_bytes())\n")
    marker="        save(run / 'input_sha256.json', expected)\n"
    assert text.count(marker)==1
    text=text.replace(marker,marker+'''        base_manifest = json.loads((Path(%r) / 'input_sha256.json').read_bytes())
        assert set(expected) == set(base_manifest)
        differences = [name for name in expected if expected[name] != base_manifest[name]]
        assert differences == ['source/ov5640/ov5640/ov5640_cdc.v'], differences
        save(run / 'input_diff_proof.json', dict(base=%r, files=len(expected), differences=differences))
''' % (str(BASE),str(BASE)))
    marker="            assert sha(candidate_adapter) == receipt['adapter_candidate_sha256']\n"
    assert text.count(marker)==1
    text=text.replace(marker,marker+"            assert sha(candidate_counter) == receipt['counter_candidate_sha256']\n")
    marker="        script = (FROZEN / 'strong_pnr.tcl').read_bytes().decode('ascii')\n"
    assert text.count(marker)==1
    text=text.replace(marker,'''        # A documented attribute is only a hypothesis until actual FF mapping proves it.
        receipt['stage'] = 'counter_mapping_verification'
        save(run / 'receipt.json', receipt)
        save(HERE / 'current_run.json', receipt)
        netlist = work / 'synthesize/top_syn.vm'
        net = netlist.read_bytes()
        counter_cells = []
        for module_block in re.finditer(rb'\\nmodule [\\s\\S]+?\\nendmodule', net):
            module_raw = module_block.group()
            is_counter_module = bool(re.match(rb'\\nmodule pll56_source_drop_counter\\b', module_raw))
            for block in re.finditer(rb'\\n    GTP_DFF[^;]+;', module_raw):
                rawcell = block.group()
                if (is_counter_module and b'value' in rawcell) or b'u_src_drop/value' in rawcell:
                    counter_cells.append(rawcell)
        assert len(counter_cells) >= 32, 'Missing extracted counter FF evidence: ' + str(len(counter_cells))
        dynamic_ce = [cell.decode('ascii','replace') for cell in counter_cells
                      if re.search(rb'\\.CE\\s*\\(',cell)]
        save(run / 'counter_mapping_proof.json', dict(status='FAIL' if dynamic_ce else 'PASS',
            netlist_sha256=sha(netlist), counter_register_cells=len(counter_cells),
            cells=[cell.decode('ascii','replace') for cell in counter_cells], dynamic_ce=dynamic_ce))
        assert not dynamic_ce, 'Counter control-set attribute did not eliminate CE; route experiment blocked'
        receipt['counter_mapping'] = 'PASS no counter CE pins in synthesized FFs'
        receipt.setdefault('completed_stages', {})['counter_mapping_verification'] = time.strftime('%Y-%m-%d %H:%M:%S')
        save(run / 'receipt.json', receipt)
        save(HERE / 'current_run.json', receipt)
        print('COUNTER_MAPPING_PASS', len(counter_cells), 'register cells; no CE', flush=True)
'''+marker)
    text=text.replace('Detector/history RTL preserved; only adapter capture predicate rewritten; map built afresh for PLL56.',
        'Detector/history and snapshot RTL preserved; adapter capture overlay retained; source-drop control set scoped to D; map built afresh for PLL56.')
    runner=HERE/('build_counter_generated_'+out.name+'.py')
    compile(text,str(runner),'exec')
    runner.write_text(text,encoding='utf-8')
    launch=dict(status='starting',started=time.strftime('%Y-%m-%d %H:%M:%S'),
        candidate_sha256=sha(candidate),simulation_receipt=str(sim_path),
        generated_runner=str(runner),generated_runner_sha256=sha(runner),
        inherited_runner_sha256=sha(upstream),placement_seed=1,
        log=str(out/'build_launch.log'),hardware_access=False)
    receipt_path=out/'launch_receipt.json'
    save(receipt_path,launch)
    code=1
    try:
        with (out/'build_launch.log').open('xb') as log:
            proc=subprocess.Popen([sys.executable,'-B','-u',str(runner),'--run','--placement-seed','1'],
                cwd=HERE,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL)
            launch.update(status='running',supervisor_child_pid=proc.pid)
            save(receipt_path,launch)
            for line in iter(proc.stdout.readline,b''):
                log.write(line);log.flush()
                print(line.decode('gb18030','replace').rstrip(),flush=True)
            code=proc.wait()
            current=json.loads((HERE/'current_run.json').read_bytes())
            if current.get('counter_candidate_sha256')==sha(candidate):
                launch['build']=current
            if code: launch['error']='Build child failed; see stage/error in build receipt and launch log'
    except Exception as e:
        launch['error']=str(e)
        raise
    finally:
        launch.update(status='finished' if code==0 else 'failed',returncode=code,
            finished=time.strftime('%Y-%m-%d %H:%M:%S'))
        save(receipt_path,launch)
        print('COUNTER_BUILD_FINISHED',launch['status'],receipt_path,flush=True)
    sys.exit(code)

if __name__=='__main__':
    try:
        main()
    except Exception as e:
        failure=Path(sys.argv[1]).resolve()/'supervisor_failure.json'
        save(failure,dict(status='failed',stage='supervisor_preflight_or_launch',
            error=repr(e),finished=time.strftime('%Y-%m-%d %H:%M:%S')))
        raise
