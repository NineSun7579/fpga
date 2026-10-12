"""Select distinct historical legal CLMA FF sites, not a placement acceptance."""
from pathlib import Path
import hashlib,json,re
H=Path(__file__).resolve().parent
B=H.parent
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    output=H/'site_candidate_plan.json';assert not output.exists()
    inventory=H/'target_inventory.json'
    dump=B/'source_diagnostics_timing_build_01/route_attempt_03/evidence/final_export/routed_dump.txt'
    raw=dump.read_bytes()
    pattern=rb'\(INSTANNOTATE\s+\(INSTREF\s+([^\s)]+)\s*\)\s*\(PLACE\s+(impl_\w+)\s+\(DEVINSTREF\s+(CLMA|CLMS)\s+\(SITEREF\s+(\d+)\s+(\d+)\)'
    annotations=[]
    for m in re.finditer(pattern,raw):
        name,impl,family,x,y=[v.decode('ascii') for v in m.groups()]
        annotations.append({'instance':name.lstrip('\\'),'impl':impl,'family':family,
                            'x':int(x),'y':int(y),'site':f'{family}_{x}_{y}',
                            'dump_byte_offset':m.start()})
    byname={r['instance']:r for r in annotations}
    available={r['site']:r for r in annotations if r['family']=='CLMA' and re.fullmatch(r'impl_dev[ABCD]Q0',r['impl'])}
    assert len(available)>=60,'Not enough actual historical independent CLMA FF site evidence'
    # A site bound elsewhere by an existing explicit physical constraint is not a candidate.
    fixed=set();bindings={}
    source=B/'source_diagnostics_timing_build_03'
    for folder in ['constraints_templates','inputs']:
        for p in (source/folder).rglob('*'):
            if p.is_file() and p.suffix.lower() in {'.fdc','.lcf','.pcf'}:
                data=p.read_bytes()
                for line in data.splitlines():
                    if line.lstrip().startswith(b'#'):continue
                    if b'PAP_LOC' in line or b'def_inst_site' in line:
                        sites=re.findall(rb'CLM[AS]_\d+_\d+',line)
                        if sites:
                            fixed.update(v.decode('ascii') for v in sites)
                            bindings[str(p)]=sha(p)
    for site in fixed:available.pop(site,None)
    used=set();rows=[]
    for target in json.loads(inventory.read_bytes())['targets']:
        c,chain,bit=target['camera'],target['chain'],target['bit']
        prefix=f'source_diagnostics/cameras[{c}].'+('' if chain=='reset_pipe' else 'source/')
        direct=[r for name,r in byname.items() if name.startswith(prefix+f'{chain}[{bit}]/')]
        if not direct:
            direct=[r for name,r in byname.items() if name.startswith(prefix+f'{chain}[')]
        assert direct,(target['actual_synthesized_instance'],'No actual historical role location')
        anchor=min(direct,key=lambda r:r['instance'])
        choices=[r for site,r in available.items() if site not in used]
        chosen=min(choices,key=lambda r:(abs(r['x']-anchor['x'])+abs(r['y']-anchor['y']),r['site']))
        used.add(chosen['site'])
        rows.append({'target':target['actual_synthesized_instance'],'site':chosen['site'],
                     'source_legal_FF_annotation':chosen,'historical_role_anchor':anchor,
                     'site_only':True,'physical_PASS':False})
    assert len(rows)==len(used)==60
    output.write_text(json.dumps({'status':'PREPARATORY_DISTINCT_SITE_CANDIDATES_ONLY',
                                 'inventory_sha256':sha(inventory),'historical_route_dump_sha256':sha(dump),
                                 'actual_legal_CLMA_FF_sites':len(available),'explicit_constraint_hashes':bindings,
                                 'excluded_fixed_sites':sorted(fixed),'rows':rows,
                                 'limitation':'Historical placement proves site existence only. New full synthesis must bind each target. UCE target parsing, mapping consumption, endpoint semantics and new placement/timing remain unproven.'},indent=2),encoding='ascii')
    print('Prepared 60 distinct historical CLMA FF site candidates, excluding explicit fixed sites; no physical PASS')

if __name__=='__main__':main()
