"""Reuse TC02 stimulus/run helper without calling its destructive main()."""
from pathlib import Path
import ast
import hashlib
import importlib.util
import json
import re
import textwrap

HERE = Path(__file__).resolve().parents[1]
BASE = HERE.parent
OUT = HERE / 'receipts/dma'
V5 = BASE / 'whole_candidate_v5_route_01'
REFERENCE = V5 / 'rtl/axi_dma_write_tc02.v'
CANDIDATE = HERE / 'rtl/axi_dma_write_tc04.v'
RUNNER = BASE / 'timing_correction_02/run_dma_tests.py'


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def tokens(data):
    data = re.sub(rb'//[^\r\n]*|/\*.*?\*/', b'', data, flags=re.S)
    return re.findall(rb'\w+|[^\s]', data)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    # Protect production, frozen V5, TC02/TC03, all pre-existing TC04 runners,
    # RTL and receipts outside this task's dedicated DMA output directory.
    protected = []
    for folder in [BASE.parent.parent / 'source', V5,
                   BASE / 'timing_correction_02', BASE / 'timing_correction_03', HERE]:
        for p in folder.rglob('*'):
            if p.is_file() and '__pycache__' not in p.parts and OUT not in p.parents:
                if p not in [CANDIDATE, Path(__file__).resolve(), HERE / 'tests/dma_edges_body.sv']:
                    protected.append(p)
    before = {str(p): sha(p) for p in set(protected)}
    raw, candidate = REFERENCE.read_bytes(), CANDIDATE.read_bytes()
    old_start = raw.index(b'always @(posedge clk) begin\n    if(rst || abort_r)')
    old_end = raw.index(b'// Timeout may fill', old_start)
    new_start = candidate.index(b'// TC04:')
    new_end = candidate.index(b'// Timeout may fill', new_start)
    assert tokens(raw[:old_start] + raw[old_end:]) == tokens(
        (candidate[:new_start] + candidate[new_end:]).replace(b'axi_dma_write_tc04', b'axi_dma_write_tc02', 1))
    # Byte-level duplicate scan (GBK-safe). Never alter any binding.
    duplicates = []
    for p in BASE.parent.parent.rglob('*.v'):
        if p != CANDIDATE and re.search(rb'\bmodule\s+axi_dma_write_tc04\b', p.read_bytes()):
            duplicates.append(str(p))
    assert not duplicates, duplicates
    spec = importlib.util.spec_from_file_location('tc02_dma_reuse', RUNNER)
    runner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runner)
    runner.OUT = OUT
    # Extract only TC02's public API parser and stimulus construction. No
    # source/target generation, no main(), no old output directory writes.
    main_node = next(n for n in ast.parse(RUNNER.read_text()).body
                     if isinstance(n, ast.FunctionDef) and n.name == 'main')
    statements = [n for n in main_node.body if 20 <= n.lineno <= 56]
    construction = '\n'.join(ast.get_source_segment(RUNNER.read_text(), n) for n in statements)
    construction = construction.replace("('axi_dma_write','old')", "('axi_dma_write_tc02','old')")
    construction = construction.replace("('axi_dma_write_tc02','new')", "('axi_dma_write_tc04','new')")
    env = dict(raw=raw, re=re)
    exec(compile(textwrap.dedent(construction), str(RUNNER) + ':reused_stimulus', 'exec'), env)
    lines = env['lines']
    # Same 80 cases/mode; add whole watchdog-state checks each clock.
    extra = ['if(old_dut.wd_cnt !== new_dut.wd_cnt || old_dut.abort_r !== new_dut.abort_r || old_dut.available_q !== new_dut.available_q) $fatal(1,"watchdog state mismatch");']
    idx = next(i for i, line in enumerate(lines) if 'beat count mismatch' in line)
    lines[idx] = 'if(old_dut.len !== new_dut.len) $fatal(1,"beat count mismatch");'
    lines[idx+1:idx+1] = extra
    original_tb = OUT / 'tb_dma_original_160.sv'
    original_tb.write_text('\n'.join(lines), encoding='ascii')
    # Reuse precisely the same port declarations/bindings for edge tests.
    prefix = lines[:lines.index('always #4 clk=~clk;')]
    prefix[1] = 'module tb_dma_edges; parameter integer WAIT=1; parameter LIMIT=7;'
    prefix = [line.replace('.BURST_LEN(16)', '.BURST_LEN(16),.WD_LIMIT(LIMIT)') for line in prefix]
    oldbus = env['oldbus']
    newbus = env['newbus']
    body = (HERE / 'tests/dma_edges_body.sv').read_text()
    edge_tb = OUT / 'tb_dma_edges.sv'
    edge_tb.write_text('\n'.join(prefix) + '\n' + body.replace('@OLDBUS@', oldbus).replace('@NEWBUS@', newbus), encoding='ascii')
    stream = V5 / 'inputs/source/axi_dma/stream_pipe.v'
    runner.run([runner.SIM / 'vlib.exe', 'work'], 'vlib')
    runner.run([runner.SIM / 'vlog.exe', '-sv', stream, REFERENCE, CANDIDATE,
                original_tb, edge_tb], 'compile')
    simulations = []
    for mode in [0, 1]:
        label = 'original_wait_' + str(mode)
        data = runner.run([runner.SIM / 'vsim.exe', '-c', '-onfinish', 'stop', 'work.tb_dma_tc02',
                           '-gWAIT=' + str(mode), '-do', 'run -all; quit -f'], label)
        assert b'DMA_TC02_PASS cases=80' in data
        simulations.append(dict(label=label, cases=80))
        for limit in [0, 1, 7, 16777215]:
            label = f'edges_wait_{mode}_limit_{limit}'
            data = runner.run([runner.SIM / 'vsim.exe', '-c', '-onfinish', 'stop', 'work.tb_dma_edges',
                               '-gWAIT=' + str(mode), '-gLIMIT=' + str(limit),
                               '-do', 'run -all; quit -f'], label)
            match = re.search(rb'DMA_TC04_EDGES_PASS cycles=(\d+) vectors=(\d+) natural=(\d+)', data)
            assert match, data.decode(errors='replace')
            simulations.append(dict(label=label, cycles=int(match[1]), vectors=int(match[2]), natural=int(match[3])))
    changed = [p for p, h in before.items() if not Path(p).exists() or sha(Path(p)) != h]
    # A sibling subagent can run the already-existing cam6 simulation in
    # parallel. Its transcript/live ModelSim database is not an immutable
    # source; record those changes honestly instead of claiming all hashes
    # match. This runner has no write target outside OUT.
    cam6_runtime = HERE / 'receipts/cam6'
    def sibling_runtime(p):
        path = Path(p)
        return cam6_runtime in path.parents
    externally_changed_runtime = [p for p in changed if sibling_runtime(p)]
    # Known sibling task owns this newly-added cam6 runner. Do not edit it;
    # retain before/after hashes if that task updates it during our tests.
    sibling_tests = HERE / 'tests/cam6'
    externally_changed_runner = [p for p in changed if sibling_tests in Path(p).parents]
    unexpected_changes = [p for p in changed if not sibling_runtime(p) and sibling_tests not in Path(p).parents]
    assert not unexpected_changes, unexpected_changes
    assert sha(CANDIDATE) == hashlib.sha256(candidate).hexdigest()
    result = dict(status='PASS', original_cases=160, simulations=simulations,
                  edge_cycles=sum(s.get('cycles', 0) for s in simulations),
                  directed_vectors=sum(s.get('vectors', 0) for s in simulations),
                  natural_protocol_scenarios=sum(s.get('natural', 0) for s in simulations),
                  candidate_sha256=sha(CANDIDATE), reference_sha256=sha(REFERENCE),
                  tc02_runner_sha256=sha(RUNNER), protected_files=len(before),
                  protected_sha256_unchanged=not changed,
                  protected_non_sibling_sha256_unchanged=True,
                  sibling_cam6_runtime_changes=externally_changed_runtime,
                  sibling_cam6_runner_changes=externally_changed_runner,
                  externally_changed_hashes={p: {'before': before[p], 'after': sha(Path(p)) if Path(p).exists() else None} for p in changed},
                  unchanged_non_watchdog_tokens=True,
                  all_public_outputs_including_invalid_payloads=True,
                  reference='actual V5 rtl/axi_dma_write_tc02.v',
                  routed_timing_verified=False,
                  limitations=['No PDS synthesis/place/route; RS mapping and slack are unverified.',
                               'Saturation/carry exhaustive bit boundaries use paired internal state deposits; not a 2^24-cycle dwell.',
                               'RTL differential simulation is not formal equivalence or exhaustive X/Z input testing.'])
    (OUT / 'protected_sha256.json').write_text(json.dumps(before, indent=2))
    (OUT / 'results.json').write_text(json.dumps(result, indent=2))
    artifacts = [CANDIDATE, REFERENCE, RUNNER, stream, Path(__file__).resolve(),
                 HERE / 'tests/dma_edges_body.sv', original_tb, edge_tb]
    artifacts += list(OUT.glob('*.log'))
    (OUT / 'artifact_sha256.json').write_text(json.dumps({str(p): sha(p) for p in artifacts}, indent=2))
    print(json.dumps(result, indent=2), flush=True)


if __name__ == '__main__':
    main()
