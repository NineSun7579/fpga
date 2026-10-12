"""One-time isolated source preparation. No subprocess, PDS or device operations."""
from pathlib import Path
import hashlib, json, re, shutil

HERE = Path(__file__).resolve().parent
BOARD = HERE.parent
OLD = BOARD / 'source_diagnostics_timing_build_02'
REG = BOARD / 'diagnostic_integrated_top_regression03'
MAP = BOARD / 'diagnostic_sync_register_map02'

def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def load(p):
    return json.loads(Path(p).read_text(encoding='utf-8'))

def save(n, v):
    p = HERE / n
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(v, indent=2, ensure_ascii=True) + '\n', encoding='ascii')

def require(v, message):
    if not v:
        raise RuntimeError(message)

def main():
    require(not (HERE / 'manifest.json').exists(), 'Refuse overwrite sealed candidate')
    old = load(OLD / 'manifest.json')
    require(len(old['local_hashes']) == 741 and len(old['registered_sources']) == 186, 'Baseline inventory changed')
    before = {n: sha(OLD / n) for n in old['local_hashes']}
    require(before == old['local_hashes'], 'Build02 actual frozen source drift')
    contracts = load(REG / 'replacement_contract.json')
    require(len(contracts['candidate']) == len(contracts['golden']) == 243, 'Actual closure count changed')
    for side in ('candidate', 'golden'):
        for row in contracts[side]:
            require(sha(row['source']) == row['sha256'], 'Actual regression source drift: ' + row['source'])
    results = load(REG / 'results.json')
    require(results['functional_pass'] is True, 'Regression03 functional gate failed')
    for n in before:
        dest = HERE / n
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(OLD / n, dest)
    two = ['rtl/ov5640_cdc_tc04.v', 'rtl/v7_sfd_candidate.v']
    srchashes = load(REG / 'src/sourcehash.json')
    for n in two:
        src = REG / 'src' / Path(n).name
        require(sha(src) == srchashes['src\\' + src.name], 'Actualsrc seal drift')
        require(src.read_bytes() == (REG / 'candidate' / n).read_bytes(), 'Actualsrc not compiled candidate')
        shutil.copyfile(src, HERE / n)
    # Candidate02 contains old counter logic: port only the proven byte-local attributes,
    # NEVER replace the new boolean module with its old map02 file.
    attr = b'(* syn_noprune=1 *) '
    inverse = []
    for name, count in [('v7_sfd_candidate.v', 11), ('v7_sdt_bus.v', 4)]:
        oldbytes = (OLD / 'rtl' / name).read_bytes()
        mapbytes = (MAP / 'rtl' / name).read_bytes()
        require(mapbytes.count(attr) == count and mapbytes.replace(attr, b'') == oldbytes, 'Map02 has non-attribute delta')
        p = HERE / 'rtl' / name
        original = p.read_bytes()
        # Anchored to primitive type and instance line, not wires or generic reg declarations.
        changed, actual = re.subn(rb'(?m)^(\s*)(GTP_DFF_(?:CE|PE)\s+#)', rb'\1' + attr + rb'\2', original)
        require(actual == count and changed.replace(attr, b'') == original, 'Attribute inverse failed')
        p.write_bytes(changed)
        inverse.append({'path': 'rtl/' + name, 'textual_instances': count, 'elaborated_instances': count * 4,
                        'before_sha256': hashlib.sha256(original).hexdigest(), 'candidate_sha256': sha(p),
                        'inverse_sha256': hashlib.sha256(changed.replace(attr, b'')).hexdigest(), 'inverse_exact': True,
                        'map02_attribute_source': str((MAP / 'rtl' / name).resolve()), 'map02_attribute_source_sha256': sha(MAP / 'rtl' / name)})
    hashes = {n: sha(HERE / n) for n in before}
    deltas = [{'path': n, 'build02_sha256': before[n], 'build03_sha256': h} for n, h in hashes.items() if h != before[n]]
    require({x['path'] for x in deltas} == set(two + ['rtl/v7_sdt_bus.v']), 'Unexpected source delta')
    rows = []
    for n in old['registered_sources']:
        actual = REG / 'candidate' / n
        local = (HERE / n).read_bytes()
        normalized = local.replace(attr, b'') if n in ['rtl/v7_sfd_candidate.v', 'rtl/v7_sdt_bus.v'] else local
        if actual.exists():
            require(normalized == actual.read_bytes(), 'Registered actual regression mismatch: ' + n)
        else:
            require(normalized == (OLD / n).read_bytes(), 'Uncompiled registered source changed: ' + n)
        rows.append({'path': n, 'absolute_build03_path': str((HERE / n).resolve()), 'sha256': hashes[n],
                     'regression03_actual_source': str(actual.resolve()) if actual.exists() else None,
                     'regression03_actual_sha256': sha(actual) if actual.exists() else None,
                     'status': 'ACTUAL_COMPILED_MATCH_AFTER_ATTRIBUTE_INVERSE' if actual.exists() else 'BUILD02_BYTE_IDENTICAL_NOT_IN_SIM_CLOSURE'})
    constraints = HERE / 'constraints_templates'
    constraints.mkdir()
    for name in ['clock.fdc', 'cdc.fdc', 'ddr3.fdc', 'ov5640.fdc', 'pcie.fdc', 'sfp.fdc']:
        src = OLD / ('inputs/source/constraints/clock.fdc' if name == 'clock.fdc' else 'constraints_live/' + name)
        shutil.copyfile(src, constraints / name)
    project = (OLD / 'project_template.pds').read_bytes().replace(b'constraints_pending/', b'constraints_templates/')
    project = re.sub(rb'\(_gci_state \(_integer \d+\)\)', b'(_gci_state (_integer 0))', project)
    require(not re.search(rb'[A-Za-z]:[\\/]|\.\./', project), 'External project binding')
    (HERE / 'project_template.pds').write_bytes(project)
    registrations = [x.decode('ascii') for x in re.findall(rb'\(_file "([^"]+)"', project)]
    require([n for n in registrations if n.startswith(('rtl/', 'inputs/'))] == old['registered_sources'], 'Registered source list mismatch')
    outputs = {'compile', 'synthesize', 'device_map', 'place_route', 'generate_bitstream'}
    assets = [n for n in registrations if Path(n).parts[0] not in outputs]
    require(all((HERE / n).is_file() for n in assets), 'Missing project side asset')
    references = []
    for n in hashes:
        raw = (HERE / n).read_bytes()
        for line, text in enumerate(raw.splitlines(), 1):
            if re.search(rb'[A-Za-z]:[\\/]', text):
                references.append({'path': n, 'line': line, 'text_ascii_escaped': text.decode('ascii', 'backslashreplace'),
                                   'registered_rtl': n in old['registered_sources'],
                                   'action': 'PRESERVED_PROTECTED_IP_BYTES; review inactive INIT_FILE or auxiliary simulation/generation history; no external source registration'})
    # Reviewed runtime is reference material only. Preserve latest bytes and name each
    # unresolved hard binding; do not silently relabel two-version acceptance consumers.
    runtime_refs = {}
    bindings = []
    for p in (OLD / 'runtime').rglob('*'):
        if not p.is_file() or '__pycache__' in p.parts:
            continue
        rel = p.relative_to(OLD / 'runtime')
        dest = HERE / 'review_templates/build02_latest_runtime' / (str(rel) + '.txt')
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(p, dest)
        runtime_refs[dest.relative_to(HERE).as_posix()] = sha(dest)
        if p.suffix == '.py':
            for i, line in enumerate(p.read_text(encoding='utf-8').splitlines(), 1):
                if any(k in line for k in ['build02', 'build01', 'map_01', 'ALLOWED_BUILDS', 'PREP.', 'BASE', 'ORIGIN', 'BOARD/', 'BOARD /']):
                    bindings.append({'reference': dest.relative_to(HERE).as_posix(), 'line': i, 'text': line, 'status': 'MAIN_REVIEW_PORT_REQUIRED'})
    save('sourcehash.json', hashes)
    save('source03hash.json', {'schema': 1, 'root': str(HERE), 'hashes': hashes, 'digest_rule': 'SHA256 of canonical sorted compact JSON hashes',
                             'source_set_sha256': hashlib.sha256(json.dumps(hashes, sort_keys=True, separators=(',', ':')).encode()).hexdigest()})
    save('evidence/build02_sources_before.json', before)
    save('evidence/registered_source_audit.json', rows)
    save('evidence/attribute_inverse.json', inverse)
    save('evidence/absolute_path_inventory.json', references)
    save('evidence/runtime_port_hardbindings.json', bindings)
    save('evidence/regression03_closure_receipt.json', {'contracts_sha256': sha(REG / 'replacement_contract.json'),
          'compiled_files_each': 243, 'unchanged_compile_files': 241, 'actual_sources_hash_verified': True,
          'registered_count': 186, 'actual_compiled_registered': sum(x['regression03_actual_source'] is not None for x in rows),
          'uncompiled_registered': sum(x['regression03_actual_source'] is None for x in rows),
          'functional_pass': True, 'overall_freeze_pass': results['freeze_pass'], 'results_sha256': sha(REG / 'results.json'),
          'actualsrc_sourcehash_sha256': sha(REG / 'src/sourcehash.json'), 'external_evidence_paths': {str((REG / n).resolve()): sha(REG / n) for n in ['audit.json', 'freeze_audit.json', 'results.json', 'REPORT_ZH.md', 'replacement_contract.json', 'src/sourcehash.json']}})
    save('manifest.json', {'schema': 1, 'status': 'PLANNED', 'root': str(HERE), 'baseline_root': str(OLD),
          'mode': 'ISOLATED_SOURCES_CONSTRAINT_TEMPLATES_OFFLINE_ONLY', 'local_hashes': hashes,
          'registered_sources': old['registered_sources'], 'registered_count': 186, 'source_inventory_count': 741,
          'changes_from_build02': deltas, 'attribute_candidate_status': 'PENDING_REAL_MAP02_MAPPING_FINAL_PASS',
          'map_gate': {'status': 'PENDING', 'root': str(MAP), 'required': 'Fresh real mapping final PASS plus independently recomputed compile/synthesis/mapping 60-cell topology, INIT/GRS/polarity/predecessor/clock checks and ADF/nativeDB/export/input hashes', 'physical_start_allowed': False},
          'optimization_gate': old['optimization_gate'], 'runtime_reference_hashes': runtime_refs,
          'constraint_template_hashes': {p.relative_to(HERE).as_posix(): sha(p) for p in constraints.iterdir()},
          'project_template_sha256': sha(HERE / 'project_template.pds'), 'constraints_qualified': False,
          'runtime_port_status': 'MAIN_CONTINUATION_REQUIRED', 'consumer_extension': 'SEPARATE_MAIN_REVIEW_REQUIRED; no ALLOWED_BUILDS edits',
          'pds_started': False, 'mapped': False, 'bit_generated': False, 'device_operations': False})
    require({n: sha(OLD / n) for n in before} == before, 'Build02 changed during source copy')

if __name__ == '__main__':
    main()
