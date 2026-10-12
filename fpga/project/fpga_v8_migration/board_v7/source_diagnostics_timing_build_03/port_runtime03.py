"""Explicit one-time local runtime port, preserving all 741 candidate source bytes."""
from pathlib import Path
import ast, json, re
from prepare03 import HERE, OLD, BOARD, MAP, load, sha, save, require

R = HERE / 'runtime'
LIB = R / 'libraries'
DATA = R / 'baseline_data'
changes = []

def write(relative, raw, source=None):
    p = R / relative
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(raw.encode('utf-8') if isinstance(raw, str) else raw)
    changes.append({'local': p.relative_to(HERE).as_posix(), 'sha256': sha(p),
                    'source': str(source.resolve()) if source else None,
                    'source_sha256': sha(source) if source else None})

def functions(p, names, imports):
    raw = p.read_text(encoding='utf-8')
    tree = ast.parse(raw)
    nodes = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names]
    require({n.name for n in nodes} == set(names), 'Pure function extraction mismatch')
    lines = raw.splitlines(keepends=True)
    return imports + '\n\n' + '\n'.join(''.join(lines[n.lineno - 1:n.end_lineno]) for n in nodes) + '\n'

def main():
    require(not (R / 'physical_flow.py').exists(), 'Refuse overwrite runtime port')
    source_guard = load(HERE / 'sourcehash.json')
    for p in (OLD / 'runtime/analysis_tools').glob('*.py'):
        write('analysis_tools/' + p.name, p.read_bytes(), p)
    p = OLD / 'runtime/targeted_reports.py'
    write('targeted_reports.py', p.read_bytes().replace(b'timing01_', b'timing03_'), p)
    p = OLD / 'runtime/physical_flow.py'
    raw = p.read_text(encoding='utf-8')
    # Retain reviewed stage/export/constraint routines. Remove dead legacy derive,
    # generator and external dynamic endpoint exec functions completely.
    tree = ast.parse(raw)
    retained = {'record', 'status', 'processes', 'wait_idle', 'run', 'snapshot',
                'official_stage_complete', 'stage', 'export_graph', 'runtime_constraints', 'hashlib_sha'}
    fs = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in retained]
    derive = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'derive'][-1]
    fs.append(derive)
    lines = raw.splitlines(keepends=True)
    body = '\n'.join(''.join(lines[n.lineno - 1:n.end_lineno]) for n in sorted(fs, key=lambda n:n.lineno))
    # Runtime baseline tables and pure XML functions are now local, never imported
    # by executing an old controller or generator with its original globals.
    start = body.index("    path = BOARD / 'physical_subagent_evidence_01/summarize_exact11.py'")
    end = body.index("    frozen_clocks =", start)
    body = body[:start] + "    from clock_tables import flatten, extract\n    scope = {'flatten': flatten, 'extract': extract}\n    baseline = load(DATA/'reference_tables.json')['synthesize']\n" + body[end:]
    body = body.replace("if s.startswith((b'create_clock ',b'create_generated_clock '))", "if s.lstrip().startswith((b'create_clock ',b'create_generated_clock '))")
    body = body.replace("'timing01_'", "'timing03_'")
    body = body.replace("script.write_bytes(('set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG484\\nopen_project {'+PROJECT.as_posix()+'}\\ndev_map -devmap_remove_dups 0 -devmap_const_prop 0 -devmap_control_set_num 0\\n').encode('ascii'))", "script.write_bytes(('set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG484\\nadd_constraint {'+(HERE/'constraints_live/clock.fdc').as_posix()+'}\\ndev_map -force_to_run -input_db_file {'+(HERE/'synthesize/v7_sdt_top_syn.adf').as_posix()+'} -devmap_remove_dups 0 -devmap_const_prop 0 -devmap_control_set_num 0\\n').encode('ascii'))")
    require('open_project ' not in body, 'Map API still uses unverified old project context')
    header = '''"""Build03 local serial flow; all new graph derivation and acceptance are local."""
from pathlib import Path
import ctypes, json, os, re, shutil, subprocess, sys, time, traceback
import xml.etree.ElementTree as ET
from preflight import HERE, BOARD, DATA, load, save, sha, require, verify, frozen_guard, map_gate
from queue_policy import classify_processes
PDS=Path('C:/pango/PDS_2022.2-SP6.4/bin/pds_shell.exe')
EVIDENCE=HERE/'evidence/runtime'
TOOLS=Path(__file__).resolve().parent/'analysis_tools'
PROJECT=HERE/'project.pds'
sys.path.insert(0,str(Path(__file__).resolve().parent/'libraries'))
'''
    write('physical_flow.py', header + '\n' + body, p)
    # Only local pure topology and detailed cone functions are executable.
    src = MAP / 'run.py'
    write('libraries/map_topology.py', functions(src, ['audit'], 'import collections, re\nfrom preflight import save\n'), src)
    src = MAP / 'audit_final.py'
    write('libraries/endpoint_detail.py', functions(src, ['parameters', 'detail'], 'import itertools, re\nfrom endpoint_logic import evaluate\nfrom preflight import save\n'), src)
    src = MAP / 'endpoint_logic.py'
    write('libraries/endpoint_logic.py', src.read_bytes(), src)
    src = BOARD / 'physical_subagent_evidence_01/summarize_exact11.py'
    write('libraries/clock_tables.py', functions(src, ['flatten','extract'], 'import xml.etree.ElementTree as ET'), src)
    src = BOARD.parent / 'whole_candidate_v2_route_01/summarize_route.py'
    write('libraries/summarize_route.py', functions(src, ['sha','write','row','extract'],
          "from pathlib import Path\nimport hashlib, json, xml.etree.ElementTree as ET\nfrom preflight import HERE as BUILD_ROOT\nHERE=BUILD_ROOT/'evidence/runtime'\nEVIDENCE=HERE/'evidence'"), src)
    src = BOARD.parent / 'whole_candidate_v2_route_01/audit_final.py'
    raw = src.read_text(encoding='utf-8').replace('fpga_v8_cooperative_top_v2.rtr', 'v7_sdt_top.rtr')
    raw = raw.replace("HERE.parents[1] / 'motion_100h/run_20261003_212303/phy_audit.json'", "Path(__file__).resolve().parent.parent/'baseline_data/hsst_phy.json'")
    raw = raw.replace('max_path 15000', 'max_path 200000')
    write('libraries/raw_audit.py', raw, src)
    src = BOARD / 'build01_binding_review01/review.py'
    write('libraries/routed_truth_reference.py.txt', src.read_bytes(), src)
    # New logical counters do not alter the reviewed exhaustive mailbox truth
    # contract. The reference is AST-loaded only (ten functions and the 2048 loop).
    # Full old review module, global disk loads, writes and SRL whitelists never run.
    baseline = load(BOARD.parent/'whole_candidate_v7_route_01/evidence/stage_tables.json')
    tables = {'synthesize': {k:baseline['synthesize'][k] for k in ['synthesize_report_timing_clock_summary','synthesize_report_clock_interaction']},
              'place_route': {'pnr_io_report':baseline['place_route']['pnr_io_report']}}
    DATA.mkdir(exist_ok=True)
    (DATA/'reference_tables.json').write_text(json.dumps(tables, indent=2)+'\n', encoding='utf-8')
    p = BOARD.parents[1]/'motion_100h/run_20261003_212303/phy_audit.json'
    # BOARD.parents[1] is project, matching the reviewed physical baseline.
    require(p.exists(), 'Frozen HSST baseline absent')
    (DATA/'hsst_phy.json').write_bytes(p.read_bytes())
    (DATA/'protected_guard.json').write_bytes((BOARD/'source_diagnostics_route_01/build01_guard.json').read_bytes())
    save('evidence/runtime_port/source_provenance.json', changes)
    require(all(sha(HERE/n)==h for n,h in source_guard.items()), '741 candidate source changed during runtime port')

if __name__=='__main__':
    main()
