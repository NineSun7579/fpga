"""Read-only review of existing artifacts; no PDS invocation, no audit_library import."""
from pathlib import Path
import re, json, hashlib, collections, tkinter

OUT = Path(__file__).resolve().parent
H = OUT.parent
OLD = H.parent / 'diagnostic_sync_register_map09'
hashes = {}
checks = []
def sha(p):
    p = Path(p).resolve()
    v = hashlib.sha256(p.read_bytes()).hexdigest()
    hashes[str(p)] = v
    return v
def load(p):
    sha(p)
    return json.loads(Path(p).read_bytes())
def check(name, result, evidence=None):
    checks.append(dict(name=name, passed=bool(result), evidence=evidence))
def parse(raw):
    stack = [[]]
    for t in re.findall(r'"(?:\\.|[^"\\])*"|\\[^\s]+|[()]|[^\s()]+', raw.decode('utf8')):
        if t == '(':
            stack.append([])
        elif t == ')':
            stack[-2].append(stack.pop())
        else:
            stack[-1].append(t)
    assert len(stack) == 1
    return stack[0]
def kids(n, tag):
    return [x for x in n if isinstance(x, list) and x and x[0] == tag]
def one(n, tag):
    k = kids(n, tag)
    return k[0] if k else []
def allnodes(n, tag):
    if isinstance(n, list):
        if n and n[0] == tag:
            yield n
        for x in n:
            yield from allnodes(x, tag)
def nm(x):
    if isinstance(x, str):
        return x.lstrip('\\').strip('"')
    if x[0] == 'BIT':
        return '$constant_' + x[1][2].strip('"')
    if x[0] == 'INDEXED':
        return nm(x[1]) + '[' + x[2] + ']'
    if x[0] == 'ARRAY':
        return nm(x[1])
    raise ValueError(x)
def scalar(x):
    if x[0] in ('BIT', 'BITVEC'):
        return x[1][2].strip('"')
    return x[1].strip('"')
def params(r):
    result = {}
    for nodes in [r['default_parameters'], r['parameters']]:
        for n in allnodes(nodes, 'PARAMETER'):
            result[n[1]] = scalar(n[-1])
    return result
def reconstruct(p):
    """Independent full S-expression parse and union of exported ADIF connections."""
    sha(p)
    tree = parse(p.read_bytes())
    definitions = {}
    for c in allnodes(tree, 'CELL'):
        for v in kids(c, 'VIEW'):
            definitions[(nm(c[1]), nm(v[1]))] = (c, v)
    parent = {}
    def find(x):
        parent.setdefault(x, x)
        if parent[x] != x:
            parent[x] = find(parent[x])
        return parent[x]
    def join(x, y):
        parent[find(x)] = find(y)
    primitives = {}
    def walk(key, path):
        c, v = definitions[key]
        contents = one(v, 'CONTENTS')
        for n in kids(contents, 'NET') + kids(contents, 'CONNECT'):
            connects = kids(n, 'CONNECT') if n[0] == 'NET' else [n]
            for con in connects:
                ref = one(con, 'NETREF')
                net = path + '/@' + nm(ref[1] if ref else n[1])
                find(net)
                for port in kids(con, 'PORTREF'):
                    ir = one(port, 'INSTREF')
                    pin = (path + ('/' + nm(ir[1]) if ir else '') + '/' + nm(port[1])).lstrip('/')
                    join(pin, net)
        for inst in kids(contents, 'INSTANCE'):
            cr = next(allnodes(inst, 'CELLREF'))
            vr = next(allnodes(inst, 'VIEWREF'))
            key2 = (nm(cr[1]), nm(vr[1]))
            ip = (path + '/' + nm(inst[1])).lstrip('/')
            dc, dv = definitions[key2]
            if kids(one(dv, 'CONTENTS'), 'INSTANCE'):
                walk(key2, ip)
            else:
                ports = {}
                for port in kids(one(dv, 'INTERFACE'), 'PORT'):
                    names = [nm(port[1])]
                    if isinstance(port[1], list) and port[1][0] == 'ARRAY':
                        names = [nm(port[1]) + '[' + str(i) + ']' for i in range(int(port[1][3]), int(port[1][2]) + 1)]
                    for name in names:
                        ports[name] = dict(direction=one(port, 'DIRECTION')[1], clock=any(a[1] == 'PAP_IS_CLOCK_PIN' for a in kids(port, 'ATTRIBUTE')))
                primitives[ip] = dict(type=key2[0], view=key2[1], ports=ports,
                    attributes=kids(inst, 'ATTRIBUTE'), parameters=kids(inst, 'PARAMETERMAP') or kids(inst, 'PARAMETER'),
                    cdb_entries=kids(inst, 'CDBENTRY'), default_parameters=kids(dc, 'PARAMETER'))
    top = [key for key in definitions if key[0] == 'map03_twoff_probe']
    assert len(top) == 1
    walk(top[0], '')
    groups = collections.defaultdict(list)
    for x in list(parent):
        groups[find(x)].append(x)
    pin_net = {ip + '/' + port: find(ip + '/' + port) for ip, rec in primitives.items() for port in rec['ports'] if ip + '/' + port in parent}
    return dict(primitives=primitives, pin_net=pin_net, net_aliases=dict(groups))
def canonical(g):
    return sorted(sorted(v) for v in g['net_aliases'].values())
def connected(g, *pins):
    return all(p in g['pin_net'] for p in pins) and len({g['pin_net'][p] for p in pins}) == 1
def verify_export(root, stage, adf):
    exp = root / 'evidence' / stage
    g = reconstruct(exp / 'synthesis_export/synthesis_dump.txt')
    stored = load(exp / 'analysis/graph.json')
    check(str(root) + ':' + stage + ':independent_graph', g['primitives'] == stored['primitives'] and canonical(g) == canonical(stored))
    for pin, net in stored['pin_net'].items():
        check(stage + ':pin_partition:' + pin, connected(g, pin, next(x for x in stored['net_aliases'][net] if x in g['pin_net'])))
    receipt = load(exp / 'hashes.json')
    for key, p in [('adf_sha256', adf), ('dump_sha256', exp/'synthesis_export/synthesis_dump.txt'), ('parser_sha256', exp/'analysis/parse_objects.py'), ('graph_sha256', exp/'analysis/graph.json')]:
        check(str(root) + ':' + stage + ':' + key, sha(p) == receipt[key])
    export_receipt = load(root/'evidence'/(stage+'_export.json'))
    check(stage+':export_receipt', export_receipt['exit'] == 0 and not export_receipt['rejected_lines'] and sha(root/'evidence'/(stage+'_export.log')) == export_receipt['log_sha256'], export_receipt)
    sha(exp/'export.tcl')
    script = (exp/'export.tcl').read_bytes().decode('ascii')
    check(stage+':export_input_output_bound', '-input {'+adf.as_posix()+'}' in script and '-output {'+(exp/'synthesis_export/synthesis_dump.txt').as_posix()+'}' in script)
    return g
def project_semantics(p):
    sha(p)
    t = p.read_bytes().decode('ascii')
    meta = {}
    for tag, pat in [('comment', r'\(_comment "[^"\r\n]*"\)'), ('timespec', r'\(_timespec "[^"\r\n]*"\)'), ('gci_state', r'\(_gci_state \(_integer [0-9]+\)\)')]:
        meta[tag] = re.findall(pat, t)
        t = re.sub(pat, '('+tag+'_METADATA)', t)
    return re.findall(r'"(?:\\.|[^"\\])*"|[^\s()]+|[()]', t), meta
def stage_receipt(root, stage):
    r = load(root/'evidence'/(stage+'.json'))
    p = root/'evidence'/(stage+'.log')
    check(str(root)+':'+stage+':receipt', r['exit'] == 0 and not r['rejected_lines'] and sha(p) == r['log_sha256'], r)
    return r
def expected(g, cell, typ, values):
    r = g['primitives'][cell]
    actual = params(r)
    check(cell+':exact_type', r['type'] == typ)
    check(cell+':parameters', all(actual.get(k) == v for k,v in values.items()), actual)
    return dict(cell=cell, type=r['type'], effective_parameters=actual,
                connected_pins={k:g['pin_net'].get(cell+'/'+k) for k in r['ports']}, attributes=r['attributes'])
def main():
    original = {str(p):sha(p) for p in H.rglob('*') if p.is_file() and OUT not in p.parents}
    result = dict(scope='map12 twoFF actual artifacts only', production60='BLOCKED', bit='BLOCKED', mapping={}, reuse=[])
    claim = load(H/'evidence/actual_final_result.json')
    common = dict(RS_MODE='ASYNC', LRS_POL='FALSE', LRS_EN='TRUE', LCE_POL='FALSE', LCE_EN='FALSE', CLK_POL='FALSE', RSMUX_SEL='LOCAL', CEMUX_SEL='LOCAL', GRS_EN='TRUE', LATCH_EN='FALSE')
    for arm in ['baseline','site']:
        root = H/'execution'/arm
        old = OLD/'execution'/arm
        prep = H/arm
        a, am = project_semantics(prep/'project.pds')
        b, bm = project_semantics(old/'project.pds')
        check(arm+':reuse_project_options_sources_equal', a == b)
        check(arm+':prepared_execution_project_equal', project_semantics(root/'project.pds')[0] == a)
        reuse = dict(arm=arm, metadata_prepared=am, metadata_map09_executed=bm, input_comparisons=[], stages={})
        for p in prep.rglob('*'):
            if p.is_file() and p.name != 'project.pds':
                rel = p.relative_to(prep)
                if rel.as_posix() == 'constraints/site.lcf':
                    check(arm+':new_mapping_constraint_execution_equal', sha(p) == sha(root/rel))
                    reuse['mapping_constraint_change'] = dict(old_sha256=sha(old/rel), new_sha256=sha(p), excluded_only_from_compile_synthesis=True)
                else:
                    ok = sha(p) == sha(old/rel) == sha(root/rel)
                    check(arm+':reuse_input_equal:'+str(rel), ok)
                    reuse['input_comparisons'].append(dict(path=str(rel), sha256=sha(p), equal=ok))
        for stage, folder, suffix, native in [('compile','compile','comp','cmr.db'), ('synthesis','synthesize','syn','snr.db')]:
            art = load(old/'evidence'/(stage+'_artifact.json'))
            adf = old/folder/('map03_twoff_probe_'+suffix+'.adf')
            db = old/folder/native
            check(arm+':'+stage+':native_adf_bound', Path(art['adf']).resolve()==adf.resolve() and Path(art['native_db']).resolve()==db.resolve() and sha(adf)==art['adf_sha256'] and sha(db)==art['native_db_sha256'])
            stage_receipt(old,stage)
            g = verify_export(old,stage,adf)
            typ = 'GTP_DFF_CE' if stage=='compile' else 'GTP_DFF_C'
            records = [expected(g,c,typ,dict(GRS_EN='TRUE',INIT='0')) for c in ['ff0','ff1']]
            check(arm+':'+stage+':chain', connected(g,'ff0/Q','ff1/D'))
            check(arm+':'+stage+':clock_reset', connected(g,'ff0/CLK','ff1/CLK') and connected(g,'ff0/C','ff1/C'))
            check(arm+':'+stage+':target_whitelist', {c for c in g['primitives'] if c.startswith('ff')} == {'ff0','ff1'})
            if stage == 'compile':
                check(arm+':compile:CE_constant_one', all('$constant_1' in g['pin_net'].get(c+'/CE','') for c in ['ff0','ff1']))
                check(arm+':compile:original_inputs', g['pin_net']['ff0/D']=='/@d' and all(g['pin_net'][c+'/CLK']=='/@clk' and g['pin_net'][c+'/C']=='/@rst' for c in ['ff0','ff1']))
            else:
                check(arm+':synthesis:no_CE_port', all('CE' not in g['primitives'][c]['ports'] for c in ['ff0','ff1']))
                check(arm+':copied_synthesis_exact', sha(root/folder/adf.name)==sha(adf) and sha(root/folder/native)==sha(db))
                check(arm+':synthesis:original_inputs', connected(g,'d_ibuf/O','ff0/D') and all(connected(g,'clk_ibuf/O',c+'/CLK') and connected(g,'rst_ibuf/O',c+'/C') for c in ['ff0','ff1']))
            reuse['stages'][stage] = dict(adf_sha256=sha(adf), native_sha256=sha(db), cells=records)
        result['reuse'].append(reuse)
        receipt = stage_receipt(root,'mapping')
        adf = root/'device_map/map03_twoff_probe_map.adf'
        g = verify_export(root,'mapping',adf)
        native = root/'device_map/dmr.db'
        sha(native)
        inputs = load(root/'evidence/executed_input_hashes.json')
        check(arm+':mapping_input_hashes', all(sha(p)==v for p,v in inputs.items()))
        tcl = root/'evidence/actual_map.tcl'
        text = tcl.read_bytes().decode('ascii')
        check(arm+':mapping_options', 'dev_map -force_to_run -input_db_file {'+(root/'synthesize/map03_twoff_probe_syn.adf').as_posix()+'} -override_pcf true -devmap_remove_dups 0 -devmap_const_prop 0 -devmap_control_set_num 0' in text)
        check(arm+':mapping_done_in_log', b'Process "Device Map" done.' in (root/'evidence/mapping.log').read_bytes())
        m = dict(adf_sha256=sha(adf), graph_sha256=sha(root/'evidence/mapping/analysis/graph.json'), native_sha256=sha(native), receipt=receipt, cells=[])
        check(arm+':claim_adf_graph_hashes', m['adf_sha256']==claim['results'][arm]['adf_sha256'] and m['graph_sha256']==claim['results'][arm]['graph_sha256'])
        # Exact buffer type and FULL effective parameter set, not only roots.
        m['clock_buffer'] = expected(g,'clkbufg_0/gopclkbufg','gopCLKBUFG',dict(SOURCE_CLK='CLK0'))
        check(arm+':clock_buffer_full_parameters', m['clock_buffer']['effective_parameters'] == dict(SOURCE_CLK='CLK0'))
        for inp in ['clk','rst','d']:
            i0 = inp+'_ibuf/opit_0'; i1 = inp+'_ibuf/opit_1'
            check(arm+':'+inp+':exact_input_buffer_types', g['primitives'][i0]['type']=='gopIBUF' and g['primitives'][i1]['type']=='gopIOL_Cell_2')
            check(arm+':'+inp+':input_path', g['pin_net'][i0+'/I']=='/@'+inp and connected(g,i0+'/O',i1+'/DI'))
            ip = params(g['primitives'][i1])
            check(arm+':'+inp+':input_passthrough', ip['BUF_MODE']=='IBUF' and ip['CP_D_POL0']=='FALSE' and ip['CP_D_SEL4']=='01' and ip['CP_IDLY_EN']=='FALSE' and ip['CP_ZHOLD_EN']=='FALSE')
            m[inp+'_input_parameters'] = ip
        check(arm+':clock_buffer_input_path', connected(g,'clk_ibuf/opit_1/DI_TO_CLK','clkbufg_0/gopclkbufg/CLK'))
        targets = ['ff0/opit_0','ff1/opit_0'] if arm=='site' else ['ff0/opit_0_srl']
        check(arm+':target_exact_whitelist', {c for c in g['primitives'] if c.startswith('ff')}==set(targets))
        for c in targets:
            values = {**common, **(dict(IMPL_MODE='Q', FF_RS='RESET', FF_INIT='0', QMUX_SEL='MX') if arm=='site' else dict(FF0_RS='RESET',FFAPP0_RS='RESET',FF0_INIT='0',FFAPP0_INIT='0'))}
            m['cells'].append(expected(g,c,'gopQ' if arm=='site' else 'gopSRL2',values))
            check(arm+':'+c+':actual_clock_reset', connected(g,c+'/CLK','clkbufg_0/gopclkbufg/CLKOUT') and connected(g,c+'/RS','rst_ibuf/opit_1/DI_TO_CLK'))
            check(arm+':'+c+':CE_disabled', params(g['primitives'][c])['LCE_EN']=='FALSE' and c+'/CE' not in g['pin_net'])
        check(arm+':D_original_input', connected(g,targets[0]+'/D','d_ibuf/opit_1/DI_TO_CLK'))
        check(arm+':GRS_default_input', g['pin_net']['GRS_INST/grs_ccs/GRS_N_I']=='/@$constant_1')
        if arm=='site':
            check(arm+':Q0_D1_direct', connected(g,targets[0]+'/Q',targets[1]+'/D','q0_obuf/opit_1/TX_DATA[0]'))
            check(arm+':Q1_output', connected(g,targets[1]+'/Q','q1_obuf/opit_1/TX_DATA[0]'))
            pcf = root/'device_map/map03_twoff_probe.pcf'
            m['pcf_sha256'] = sha(pcf)
            check(arm+':claim_pcf_hash', m['pcf_sha256']==claim['results'][arm]['pcf_sha256'])
            rows = [tkinter.Tcl().splitlist(line) for line in pcf.read_text().splitlines() if line.strip().startswith('def_inst_site')]
            m['bindings'] = []
            for c,site in zip(targets,['CLMA_33_450','CLMA_45_462']):
                loc = [scalar(a[2]) for a in allnodes(g['primitives'][c]['attributes']+g['primitives'][c]['cdb_entries'],'ATTRIBUTE') if a[1]=='PAP_LOC']
                found = [r for r in rows if r[1].lstrip('\\')==c]
                check(c+':native_PCF_and_ADIF_location', len(found)==1 and found[0][2]==site and loc==[site],dict(pcf=found,adif=loc))
                m['bindings'].append(dict(cell=c,site=site,pcf=found,adif=loc))
        else:
            check('baseline:actual_two_stage_outputs', connected(g,targets[0]+'/Q0','q0_obuf/opit_1/TX_DATA[0]') and connected(g,targets[0]+'/CR0','q1_obuf/opit_1/TX_DATA[0]') and not connected(g,targets[0]+'/Q0',targets[0]+'/CR0'))
            check('baseline:PCF_absent', not (root/'device_map/map03_twoff_probe.pcf').exists())
            m['interpretation'] = 'One exact gopSRL2: D input, Q0 first-stage tap, CR0 second-stage output; two FF resources packed, not missing ff1. Distinct-cell anti-pack criterion fails as intended.'
        result['mapping'][arm] = m
    # Verify official documentation directly, not an earlier extracted/audit claim.
    import pymupdf
    pdf = Path('C:/pango/PDS_2022.2-SP6.4/doc/User_Constraint_Editor_User_Guide.pdf')
    doc = pymupdf.open(pdf)
    pages = [dict(pdf_page=n+1,text=doc[n].get_text()) for n in [68,69,93,94,105,106]]
    result['UCE_basis'] = dict(pdf=str(pdf),sha256=sha(pdf),pages=pages)
    inventory = load(H.parent/'production60_target_prepare01/target_inventory.json')
    names = [t['actual_synthesized_instance'] for t in inventory['targets']]
    check('production60:inventory_60_unique', len(names)==60 and len(set(names))==60)
    result['production60_target_names_basis'] = 'existing synthesis inventory only; no production mapping run or release'
    result['UCE_target_examples'] = []
    for name in names:
        # Slash is structural hierarchy from graph. Dot in cameras[N].source is literal generate external name.
        integrated = name.replace('/','.')
        result['UCE_target_examples'].append(dict(actual_synthesis=name, integrated_fdc_object='i:'+integrated, backend_lcf_object='i:'+name,
            integrated_query='[get_cells -hierarchical -hsc {.} -regexp {^'+re.escape(integrated)+'$}]',
            backend_query='[get_cells -hierarchical -hsc {/} -regexp {^'+re.escape(name)+'$}]'))
    plan = load(H.parent/'production60_target_prepare01/site_candidate_plan.json')
    check('production60:candidate_plan_inventory_binding', plan['inventory_sha256']==sha(H.parent/'production60_target_prepare01/target_inventory.json') and {r['target'] for r in plan['rows']}==set(names))
    sites = {r['target']:r['site'] for r in plan['rows']}
    check('production60:candidate_sites_unique', len(set(sites.values()))==60)
    proposal = dict(status='SYNTAX_REFERENCE_ONLY_NOT_EXECUTED', production_gate='BLOCKED',
        integrated_fdc=['define_attribute {i:'+n.replace('/','.')+'} {PAP_LOC} {'+sites[n]+'}' for n in names],
        backend_lcf=['define_attribute {i:'+n+'} {PAP_LOC} {'+sites[n]+'}' for n in names])
    proposal_path = OUT/'production60_syntax_reference.json'
    proposal_path.write_text(json.dumps(proposal,ensure_ascii=False,indent=2),encoding='utf8')
    result['production60_syntax_reference_sha256'] = sha(proposal_path)
    check('map12:original_files_unchanged', all(sha(p)==v for p,v in original.items()))
    result['checks'] = checks
    result['failed_checks'] = [r for r in checks if not r['passed']]
    result['status'] = 'PASS_METHOD_ONLY' if not result['failed_checks'] else 'FAIL_INDEPENDENT_REVIEW'
    result['limitations'] = 'No new DB export: independently reconstructed existing native export and verified hashes/receipts. Native dmr.db hashed for custody; no native DB parsing. No PNR, timing closure, production60 mapping, board or bit verification.'
    result['baseline_semantic_passed_field_note'] = 'Existing field false is the distinct-FF structural gate, not evidence of lost two-cycle sequential behavior; actual SRL2 has both stage taps and reset/init parameters.'
    result['evidence_hashes'] = hashes
    dest = OUT/'independent_result.json'
    dest.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
    (OUT/'result_sha256.json').write_text(json.dumps(dict(file=str(dest),sha256=sha(dest),review_script_sha256=sha(Path(__file__))),indent=2),encoding='utf8')
    print(json.dumps(dict(status=result['status'],checks=len(checks),failed=result['failed_checks'],result_sha256=sha(dest)),ensure_ascii=False))
if __name__ == '__main__':
    main()
