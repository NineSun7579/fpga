"""Serial routed target queries; retain all attempts and never change exceptions."""
from prepare_route import *

def tcl_list(items):return '{'+' '.join('{'+x+'}' for x in sorted(set(items)))+'}'

def main():
    assert json.loads((HERE/'pnr_result.json').read_bytes())['exit_code']==0
    m=json.loads((HERE/'actual/manifest.json').read_bytes())
    c=json.loads((HERE/'actual/classification.json').read_bytes())
    g=json.loads((HERE/'actual/graph.json').read_bytes())
    pairs=sorted(set((x['mapping']['launch_CLK'],x['mapping']['capture_D']) for x in m['resolved'] if x['mapping']['kind']=='register'))
    assert len(pairs)==1280
    reset_cells=[q.rsplit('/',1)[0] for x in c['reset'] for q in x['actual_Q']]
    reset_pins=[cell+'/'+p for cell in reset_cells for p in g['primitives'][cell]['ports'] if p in ('P','C','R','S')]
    assert len(reset_pins)==32
    queries=[('mailbox', [a for a,b in pairs],[b for a,b in pairs],2,10000),
             ('reset', [],reset_pins,10,200000)]
    route=HERE/'place_route/v7_sdt_top_pnr.adf';h=sha(route)
    for name,starts,ends,nworst,maximum in queries:
        idle('target_'+name)
        out=HERE/('routed_'+name);out.mkdir()
        command='report_timing -input_db_file {'+route.as_posix()+'} -force_to_run -delay_type min_max -nworst '+str(nworst)+' -max_path '+str(maximum)+' -input_pins TRUE -report_exception TRUE'
        if starts:command+=' -from '+tcl_list(starts)
        command+=' -to '+tcl_list(ends)
        script=out/'export.tcl';script.write_text('set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG484\n'+command+'\n',encoding='ascii')
        (out/'targets.json').write_text(json.dumps({'starts':starts,'ends':ends,'pairs':pairs if name=='mailbox' else None,'route_sha256':h},indent=2))
        with (out/'shell.log').open('xb') as log:
            result=subprocess.run([str(PDS),'-file',str(script),'-work_dir',str(out),'-project_name','route01_'+name],cwd=out,stdout=log,stderr=subprocess.STDOUT)
        (out/'result.json').write_text(json.dumps({'exit_code':result.returncode,'route_unchanged':sha(route)==h}))
        assert result.returncode==0 and sha(route)==h
        print('TARGET EXPORT COMPLETE',name,flush=True)
if __name__=='__main__':main()
