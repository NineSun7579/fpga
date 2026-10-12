"""Site-only experiment using hash-bound actual map09 synthesis artifacts."""
from pathlib import Path
import ctypes,json,shutil,traceback,re,tkinter
import audit_library as a

H=Path(__file__).resolve().parent
OLD=H.parent/'diagnostic_sync_register_map09'
a.H=H
a.E=H/'evidence'

def project_semantics(p):
    text=p.read_bytes().decode('ascii')
    fields={}
    for tag,pattern in [('comment',r'\(_comment "[^"\r\n]*"\)'),
                        ('timespec',r'\(_timespec "[^"\r\n]*"\)'),
                        ('gci_state',r'\(_gci_state \(_integer [0-9]+\)\)')]:
        fields[tag]=re.findall(pattern,text)
        text=re.sub(pattern,'('+tag+'_RECORDED_METADATA)',text)
    # PDS changed only whitespace outside quoted strings; preserve quoted tokens.
    tokens=re.findall(r'"(?:\\.|[^"\\])*"|[^\s()]+|[()]',text)
    return tokens,fields

def location_entries(rec):
    entries=[]
    def visit(node):
        if not isinstance(node,list):return
        if len(node)==3 and node[0]=='ATTRIBUTE' and node[1]=='PAP_LOC':
            value=node[2]
            if isinstance(value,list) and len(value)==2 and value[0]=='STRING':
                entries.append({'entry':node,'value':value[1].strip('"')})
        for item in node:
            if isinstance(item,list):visit(item)
    visit(rec.get('attributes',[]));visit(rec.get('cdb_entries',[]))
    return entries

def main():
    a.check_prepared();a.check_protected()
    assert not (H/'execution').exists()
    a.idle()
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.CreateMutexW.argtypes=[ctypes.c_void_p,ctypes.c_bool,ctypes.c_wchar_p]
    kernel.CreateMutexW.restype=ctypes.c_void_p
    kernel.CloseHandle.argtypes=[ctypes.c_void_p]
    handle=kernel.CreateMutexW(None,True,'Global\\ov56401_PDS_single_instance')
    assert handle and ctypes.get_last_error()!=183
    try:
        assert not [p for p in a.processes() if p['Name'].lower() in {'pds.exe','pds_shell.exe','ta.exe'}]
        work=H/'execution';work.mkdir()
        shutil.copy2(OLD/'execution/parse_objects.py',work/'parse_objects.py')
        provenance=[];results={}
        for name in ['baseline','site']:
            source=OLD/'execution'/name
            arm=work/name;shutil.copytree(H/name,arm);(arm/'evidence').mkdir()
            for p in (H/name).rglob('*'):
                if p.is_file() and p.relative_to(H/name).as_posix()!='constraints/site.lcf':
                    q=source/p.relative_to(H/name)
                    if p.name=='project.pds':
                        left,lmeta=project_semantics(p);right,rmeta=project_semantics(q)
                        assert left==right,('Reused project semantic mismatch',p)
                        provenance.append({'arm':name,'prepared_project_sha256':a.sha(p),
                                           'executed_project_sha256':a.sha(q),
                                           'metadata_only_difference':True,
                                           'prepared_metadata':lmeta,'executed_metadata':rmeta})
                    else:
                        assert a.sha(p)==a.sha(q),('Reused synthesis input mismatch',p)
            for stage in ['compile','synthesis']:
                artifact=json.loads((source/'evidence'/(stage+'_artifact.json')).read_bytes())
                folder,suffix,native=('compile','comp','cmr.db') if stage=='compile' else ('synthesize','syn','snr.db')
                assert Path(artifact['adf']).resolve()==(source/folder/('map03_twoff_probe_'+suffix+'.adf')).resolve()
                assert Path(artifact['native_db']).resolve()==(source/folder/native).resolve()
                assert a.sha(artifact['adf'])==artifact['adf_sha256']
                assert a.sha(artifact['native_db'])==artifact['native_db_sha256']
                graphfile=source/'evidence'/stage/'analysis/graph.json'
                hashes=json.loads((source/'evidence'/stage/'hashes.json').read_bytes())
                assert hashes['adf_sha256']==artifact['adf_sha256']
                assert a.sha(source/'evidence'/stage/'synthesis_export/synthesis_dump.txt')==hashes['dump_sha256']
                assert a.sha(source/'evidence'/stage/'analysis/parse_objects.py')==hashes['parser_sha256']
                assert a.sha(graphfile)==hashes['graph_sha256']
                audit=a.audit_graph(json.loads(graphfile.read_bytes()),stage)
                assert audit['passed']
                provenance.append({'arm':name,'stage':stage,'artifact':artifact,
                                   'graph_sha256':a.sha(graphfile),'reaudit':audit})
            # These constraints are read during mapping, not during synthesis.
            oldclock=source/'constraints/clock.fdc'
            assert a.sha(oldclock)==a.sha(arm/'constraints/clock.fdc')
            shutil.copytree(source/'synthesize',arm/'synthesize')
            assert a.sha(arm/'synthesize/map03_twoff_probe_syn.adf')==a.sha(source/'synthesize/map03_twoff_probe_syn.adf')
            assert a.sha(arm/'synthesize/snr.db')==a.sha(source/'synthesize/snr.db')
            a.save('reuse_provenance.json',provenance)
            syn=arm/'synthesize/map03_twoff_probe_syn.adf'
            script=arm/'evidence/actual_map.tcl'
            script.write_text('set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG484\nadd_constraint {'+(arm/'constraints/clock.fdc').as_posix()+'}\nadd_constraint {'+(arm/'constraints/site.lcf').as_posix()+'}\ndev_map -force_to_run -input_db_file {'+syn.as_posix()+'} -override_pcf true -devmap_remove_dups 0 -devmap_const_prop 0 -devmap_control_set_num 0\n',encoding='ascii')
            execution_inputs={str(p):a.sha(p) for p in [script,syn,arm/'synthesize/snr.db',arm/'constraints/site.lcf',arm/'constraints/clock.fdc']}
            assert a.sha(arm/'constraints/site.lcf')==a.sha(H/name/'constraints/site.lcf')
            (arm/'evidence/executed_input_hashes.json').write_text(json.dumps(execution_inputs,indent=2),encoding='ascii')
            raw=a.tool(arm,'mapping',[a.PDS,'-file',script,'-work_dir',arm,'-project_name','map03_twoff_probe'])
            assert all(a.sha(p)==v for p,v in execution_inputs.items()),'Executed mapping input drift'
            assert b'Process "Device Map" done.' in raw
            db=arm/'device_map/map03_twoff_probe_map.adf'
            graph=a.exported(arm,'mapping',db)
            audit=a.audit_graph(graph,'mapping')
            pcf=arm/'device_map/map03_twoff_probe.pcf'
            lines=pcf.read_text(encoding='ascii',errors='backslashreplace').splitlines() if pcf.exists() else []
            bindings=[]
            if name=='site':
                assert pcf.is_file(),'Site arm must produce native PCF'
                tcl=tkinter.Tcl()
                for row,site in zip(audit['rows'],['CLMA_33_450','CLMA_45_462']):
                    cell=row.get('actual_cell','MISSING')
                    matching=[]
                    locations=[]
                    for line in lines:
                        if not line.strip().startswith('def_inst_site'):continue
                        parts=tcl.splitlist(line)
                        if len(parts) in {3,4} and parts[0]=='def_inst_site' and parts[1].lstrip('\\')==cell:
                            locations.append(parts[2])
                            if parts[2]==site:matching.append(line)
                    rec=graph['primitives'].get(cell,{})
                    entries=location_entries(rec)
                    retained=[e['entry'] for e in entries if e['value']==site]
                    bindings.append({'target':row['target'],'cell':cell,'site':site,
                                     'pcf_lines':matching,'mapped_entries':retained,
                                     'passed':bool(matching and retained) and set(locations)=={site} and {e['value'] for e in entries}=={site}})
            results[name]={'mapping':audit,'bindings':bindings,'adf_sha256':a.sha(db),
                           'graph_sha256':a.sha(arm/'evidence/mapping/analysis/graph.json'),
                           'pcf_sha256':a.sha(pcf) if pcf.exists() else None,
                           'pcf_required':name=='site'}
            a.save('partial_results.json',results)
        passed=results['site']['mapping']['passed'] and all(r['passed'] for r in results['site']['bindings'])
        baseline_graph=json.loads((work/'baseline/evidence/mapping/analysis/graph.json').read_bytes())
        packed_cells=[{'cell':c,'type':r['type']} for c,r in baseline_graph['primitives'].items() if c.startswith('ff') and r['type']=='gopSRL2']
        baseline_packed=bool(packed_cells) and not results['baseline']['mapping']['distinct_cells']
        a.save('actual_final_result.json',{'status':'PASS_METHOD_ONLY' if passed else 'FAIL',
               'results':results,'anti_packing_effect_demonstrated':passed and baseline_packed,
               'baseline_packed_cells':packed_cells,'baseline_semantic_passed':results['baseline']['mapping']['passed'],
               'production_gate':'BLOCKED','scope':'twoFF site-only method; not production60 or delivery'})
        a.check_prepared();a.check_protected()
    finally:
        kernel.CloseHandle(handle)

if __name__=='__main__':
    try:main()
    except BaseException:
        a.save('actual_failure.json',{'status':'FAIL','traceback':traceback.format_exc(),'production_gate':'BLOCKED'})
        raise
