"""Audit real protected registers and derive physical FDC without editing inputs."""
from prepare_route import *

def main():
    idle('physical_prepare')
    guard=json.loads((HERE/'build01_guard.json').read_bytes())
    assert all(sha(Path(p))==h for p,h in guard.items())
    a=HERE/'actual'
    g=json.loads((a/'graph.json').read_bytes())
    c=json.loads((a/'classification.json').read_bytes())
    prim,pn,np=g['primitives'],g['pin_net'],g['netpins']
    rows=[]
    cells=[x['cell'] for x in c['chains']]
    resets=[q.rsplit('/',1)[0] for x in c['reset'] for q in x['actual_Q']]
    assert len(cells)==len(set(cells))==28
    assert len(resets)==len(set(resets))==32
    for cell in cells+resets:
        attrs={x[1]:x[2] for x in prim[cell]['attributes']}
        assert attrs['PAP_PRESERVE']==['BOOL','TRUE'],cell
        assert attrs['PAP_ALLOW_RETIMING']==['BOOL','FALSE'],cell
        q=cell+'/Q'
        sinks=[p for p in np[pn[q]] if p!=q]
        rows.append({'cell':cell,'attributes':attrs,'D_drivers':[p for p in np[pn[cell+'/D']] if prim[p.rsplit('/',1)[0]]['ports'][p.rsplit('/',1)[1]]['direction']=='OUTPUT'],'Q_sinks':sinks})
    for x in c['chains']:
        last={'req_sync':2,'ack_sync':1,'overrun_sync':1}[x['signal']]
        if x['stage']<last:
            target=x['cell'].rsplit('[',1)[0]+'['+str(x['stage']+1)+']/D'
            assert set(np[pn[x['cell']+'/Q']])=={x['cell']+'/Q',target}
    for camera in range(4):
        root=f'source_diagnostics/cameras[{camera}].source/'
        for signal,width in [('cr',2),('hr',2),('reset_pipe',4)]:
            # reset_pipe belongs to the top controller and is resolved by classification.
            matches=[x for x in c['reset'] if x['camera']==camera and x['logical'].startswith(signal+'[')]
            assert len(matches)==width,(camera,signal,matches)
            for x in matches:
                stage=int(x['logical'].split('[')[1].split(']')[0])
                if stage<width-1:
                    nxt=next(y for y in matches if y['logical']==f'{signal}[{stage+1}]')
                    q=x['actual_Q'][0];d=nxt['actual_Q'][0].rsplit('/',1)[0]+'/D'
                    assert set(np[pn[q]])=={q,d},(q,np[pn[q]])
    save('protection_topology_audit.json',{'passed':True,'chain_registers':28,'reset_registers':32,'no_merged_reset':True,'actual_attributes':rows,'ordinary_pairs':c['ordinary_pairs']})
    baseline=(a/'baseline_timing_only.sdc').read_text().splitlines()
    retained=[s for s in baseline if not re.match(r'set_clock_groups -name (cmos[1-4]_pclk|ddrphy_sysclk) ',s)]
    assert len(baseline)-len(retained)==5
    exact=(a/'B_exact_grouped.sdc').read_text().splitlines()
    assert exact[:len(retained)]==retained
    suffix=exact[len(retained):]
    out=HERE/'physical_constraints';out.mkdir()
    project=(HERE/'project.pds').read_bytes()
    audit=[]
    for token in re.findall(rb'\(_file "([^"]+\.fdc)"',project):
        source=HERE/token.decode('ascii');raw=source.read_bytes();lines=raw.splitlines(keepends=True)
        removed=[];kept=[]
        for line in lines:
            if re.match(rb'\s*set_clock_groups -name (cmos[1-4]_pclk|ddrphy_sysclk) ',line):removed.append(line.decode('ascii').strip())
            else:kept.append(line)
        data=b''.join(kept)
        if removed:
            assert len(removed)==5
            data+=b'\n# Exact real-object CDC complement and mailbox absolute budget\n'+'\n'.join(suffix).encode('ascii')+b'\n'
        target=out/source.name;target.write_bytes(data)
        project=project.replace(token,('physical_constraints/'+source.name).encode('ascii'))
        audit.append({'source':str(source.relative_to(HERE)),'original_sha256':sha(source),'candidate_sha256':sha(target),'removed':removed,'all_other_bytes_preserved':True})
    assert sum(len(x['removed']) for x in audit)==5
    (HERE/'project_before_physical.pds').write_bytes((HERE/'project.pds').read_bytes())
    (HERE/'project.pds').write_bytes(project)
    save('physical_constraint_audit.json',{'files':audit,'new_commands':suffix,'budget_ns':15.238,'protection':'actual PAP_PRESERVE TRUE / PAP_ALLOW_RETIMING FALSE; no guessed FDC attribute'})
    assert all(sha(Path(p))==h for p,h in guard.items())
    print('PASS real protection/topology and exact physical FDC',flush=True)

if __name__=='__main__':main()
