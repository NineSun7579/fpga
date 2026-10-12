"""Actual parser/schema calibration and synthetic reject-only gate tests."""
from pathlib import Path
import ast, copy, json, re, sys, tempfile
from preflight import HERE, BOARD, MAP, load, sha, require, gate_header, map_gate, log_errors
from queue_policy import classify_processes

def check():
    negatives={}
    def rejects(name,call):
        try:call()
        except (RuntimeError,AssertionError,OSError,KeyError,ValueError) as exc:negatives[name]=str(exc)
        else:raise RuntimeError('Reject-only unit unexpectedly accepted: '+name)
    # A fabricated header can NEVER return PASS or authorize a tool; only the
    # full real-disk map_gate audit can set physical_start_allowed=true.
    for label,doc in [('finalFAIL',{'status':'FAIL'}),('syn_only',{'status':'PASS','stages':{'synthesis':{'status':'PASS'}}}),
                      ('missing_independent',{'status':'PASS','all_verified_checks_passed':True})]:
        state,reason=gate_header(doc)
        require(state in {'PENDING','BLOCKED'},'Gate unit falsely authorized physical start')
        negatives['gate_'+label]={'state':state,'reason':reason,'unit_reject_only':True}
    import preflight
    with tempfile.TemporaryDirectory(prefix='build03_reject_',dir=HERE/'evidence/runtime') as td:
        root=Path(td);(root/'evidence').mkdir()
        original=preflight.MAP
        try:
            preflight.MAP=root
            pending=map_gate();require(pending['status']=='PENDING' and pending['physical_start_allowed'] is False,'Missing mapping final incorrectly released')
            (root/'evidence/final_result.json').write_text(json.dumps({'status':'FAIL'}))
            failed=map_gate();require(failed['status']=='BLOCKED' and failed['physical_start_allowed'] is False,'Map final FAIL incorrectly released')
            negatives['disk_absent_and_FAIL']={'pending':pending,'failed':failed,'unit_reject_only':True}
        finally:preflight.MAP=original
    for raw in [b'E: Flow-0013 phase conflict',b'unknown option -packingdisable',b'W: ignored attribute syn_fake',b'E: Timing-4003 unsupported argument']:
        require(log_errors(raw),'Tool errors/unknown options must reject')
    negatives['unknown_option_attribute_phaseDB_error']={'all_rejected':True,'unit_reject_only':True}
    fixture=[{'ProcessId':1,'ParentProcessId':0,'Name':'python.exe','CommandLine':'python project/fpga_v8_migration/board_v7/diagnostic_sync_register_map02/controller.py'},
             {'ProcessId':2,'ParentProcessId':0,'Name':'python.exe','CommandLine':'python project/fpga_v8_migration/board_v7/source_diagnostics_timing_build_02/runtime/controller02.py'},
             {'ProcessId':3,'ParentProcessId':0,'Name':'pds.exe','CommandLine':'GUI'},
             {'ProcessId':4,'ParentProcessId':0,'Name':'powershell.exe','CommandLine':'Wait-Process -Id 99; python prior.py'},
             {'ProcessId':99,'ParentProcessId':0,'Name':'python.exe','CommandLine':'python controller03.py --run'},
             {'ProcessId':5,'ParentProcessId':0,'Name':'python.exe','CommandLine':'python unrelated.py'}]
    busy,observers=classify_processes(fixture,99)
    require({p['ProcessId'] for p in busy}=={1,2,3} and {p['ProcessId'] for p in observers}=={4},'Queue controller lifetime/GUI/self-wait guard broken')
    from targeted_reports import records
    actual=BOARD/'source_diagnostics_timing_build_01/evidence/routed_sync_later/report_timing/v7_sdt_top.rtr'
    before=sha(actual);rows=list(records(actual))
    require(rows and all(x['start'] and x['end'] and x['slack'] is not None for x in rows),'Real record parser calibration failed')
    require({x['corner'] for x in rows}=={'Slow','Fast'} and {x['check'] for x in rows}=={'Setup','Hold'},'Real max/min suffix and setup/hold calibration failed')
    require(sha(actual)==before,'Read-only timing calibration changed')
    with tempfile.TemporaryDirectory(prefix='build03_parser_reject_',dir=HERE/'evidence/runtime') as td:
        p=Path(td)/'incomplete.rtr';p.write_text('Startpoint : fake/CLK\nEndpoint : fake/D\nPath Type : max (slow corner)\n')
        rejects('incomplete_record_without_slack',lambda:list(records(p)))
    # Offline clock universe must process the actual indented frozen FDC.
    raw=(HERE/'inputs/source/constraints/clock.fdc').read_text()
    clocks={re.search(r'-name\s+\{([^}]+)\}',l.strip())[1] for l in raw.splitlines() if l.strip().startswith(('create_clock ','create_generated_clock '))}
    groups={re.search(r'-group\s+\[get_clocks\s+\{?(\w+)',l.strip())[1] for l in raw.splitlines() if l.strip().startswith('set_clock_groups ')}
    u={(a,b) for a in clocks for b in clocks if a!=b and (a in groups or b in groups)}
    carved={(f'cmos{i+1}_pclk','ddrphy_sysclk') for i in range(4)}
    require(len(u)==368 and carved<=u and len(u-carved)==364,'Actual frozen U-B cardinality broken')
    from prepare_local_delivery import audit_sources, vendor_generated_sbit_check, bound
    audits=audit_sources();roles={'audit_fixed','verify_routed11','summarize','raw_audit','consumer','routed_connection',
         'endpoint_recompute','endpoint_graph','endpoint_logic','endpoint_parameters','endpoint_checker'}
    require(roles<=audits.keys() and all(Path(p).is_file() for p in audits.values()),'Actual producer AUDIT roles incomplete')
    assembler=BOARD/'goal_board_validation_01/new_prepare_delivery.py'
    tree=ast.parse(assembler.read_text(encoding='utf-8'))
    helper_tree=ast.parse((BOARD/'goal_board_validation_01/endpoint_recompute.py').read_bytes())
    endpoint_roles=next(ast.literal_eval(n.value) for n in helper_tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='ROLES' for t in n.targets))
    role_node=next(n.value for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='AUDIT_ROLES' for t in n.targets))
    require(isinstance(role_node,ast.Set) and all(isinstance(n,ast.Constant) or (isinstance(n,ast.Starred) and isinstance(n.value,ast.Name) and n.value.id=='ENDPOINT_ROLES') for n in role_node.elts),'Unsupported assembler role definition; review required')
    required={n.value for n in role_node.elts if isinstance(n,ast.Constant)}
    if any(isinstance(n,ast.Starred) for n in role_node.elts):required.update(endpoint_roles)
    require(required<=audits.keys(),'Main assembler role schema is not satisfied by producer')
    expected_endpoints={'endpoint_recompute':BOARD/'goal_board_validation_01/endpoint_recompute.py',
         'endpoint_graph':HERE/'runtime/analysis_tools/graph_adapter.py',
         'endpoint_logic':HERE/'runtime/libraries/endpoint_logic.py',
         'endpoint_parameters':HERE/'runtime/libraries/endpoint_detail.py',
         'endpoint_checker':HERE/'runtime/libraries/endpoints.py'}
    require(all(Path(audits[k]).resolve()==p.resolve() for k,p in expected_endpoints.items()),'New exact endpoint role paths mismatch')
    from prepare_local_delivery import delivery_sources
    producer_tree=ast.parse((HERE/'runtime/prepare_local_delivery.py').read_text())
    producer_fn=next(n for n in producer_tree.body if isinstance(n,ast.FunctionDef) and n.name=='delivery_sources')
    path_assign=next(n for n in producer_fn.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='paths' for t in n.targets))
    producer_paths=eval(compile(ast.Expression(body=path_assign.value),'local_producer_paths','eval'),
         {'EVIDENCE':HERE/'evidence/runtime','route':HERE/'place_route/v7_sdt_top_pnr.adf',
          'analysis':HERE/'evidence/runtime/actual_post_constraints/analysis'})
    mandatory=next(ast.literal_eval(n.value) for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='ARTIFACTS' for t in n.targets))
    require(set(mandatory)-{'acceptance'}<=producer_paths.keys(),'Main assembler mandatory artifact schema missing')
    require(producer_paths['sync_pairs']==HERE/'evidence/runtime/sync_bindings.json','sync_pairs must bind actual sync_bindings, not fabricated pairs')
    rawproducer=(HERE/'runtime/prepare_local_delivery.py').read_text()
    require("'candidate_id': 'source_diagnostics_timing_build_03'" in rawproducer,'Producer still binds old variant')
    require('assembler.assemble' not in rawproducer and 'module.verify' not in rawproducer,'Producer must leave acceptance/consumer to main')
    require("'accepted': False" in rawproducer and "'reviewer': None" in rawproducer and "'accepted': True" not in rawproducer,'Producer creates independent acceptance')
    with tempfile.TemporaryDirectory(prefix='build03_bit_reject_',dir=HERE/'evidence/runtime') as td:
        p=Path(td)/'fake.sbit';p.write_bytes(b'not a vendor bitstream')
        rejects('renamed_fake_bit',lambda:vendor_generated_sbit_check(p))
        rejects('missing_delivery_artifact',lambda:bound(Path(td)/'missing.adf'))
    return {'status':'PASS_OFFLINE_RUNTIME_ONLY','root':str(HERE),'candidate_id':'source_diagnostics_timing_build_03',
            'negative_checks':negatives,'real_report_calibration':{'path':str(actual),'sha256':before,'records':len(rows),'calibration_only':True,'build03_physical_pass':False},
            'actual_clock_universe':{'clocks':sorted(clocks),'U':368,'U_minus_B':364,'carved':sorted(carved),'source_sha256':sha(HERE/'inputs/source/constraints/clock.fdc')},
            'producer_audit_sources':{k:{'path':p,'sha256':sha(p)} for k,p in audits.items()},
            'main_consumer_extension':'Pending main review; no ALLOWED_BUILDS mutation','main_assembler_roles':sorted(required),
            'main_artifact_schema':sorted(mandatory),'sync_pairs_actual_path':str(producer_paths['sync_pairs']),
            'pds_started':False,'physical_signoff':False,'synthetic_positive_proof':False}
