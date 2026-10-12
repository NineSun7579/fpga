"""Expose DDR site candidates without claiming unverified port connectivity."""
from pathlib import Path
import json,re,hashlib
H=Path(__file__).resolve().parent
def main():
    source=H/'join_result.json';output=H/'site_reverse_candidates.json';assert not output.exists()
    result=json.loads(source.read_bytes())
    dump=Path(next(k for k in result['inputs'] if k.endswith('routed_dump.txt')))
    raw=dump.read_bytes();by_site={}
    pattern=rb'\(INSTANNOTATE\s+\(INSTREF\s+(\S+)\s*\)\s*\(PLACE\s+(\S+)\s+\(DEVINSTREF\s+(IOBD|IOBS)\s+\(SITEREF\s+(\d+)\s+(\d+)\)\)\)'
    for m in re.finditer(pattern,raw):
        instance,impl,family,x,y=[v.decode('ascii') for v in m.groups()]
        site='_'.join([family,x,y])
        by_site.setdefault(site,[]).append({'instance':instance.lstrip('\\'),'impl':impl,'byte_offset':m.start()})
    rows=[]
    for row in result['rows']:
        candidates=by_site.get(row['package_site'],[])
        rows.append({'port':row['port'],'loc':row['loc'],'site':row['package_site'],
                     'direct_LOC_attribute_join':bool(row['primitive_places']),
                     'site_reverse_candidates':candidates,'port_net_connectivity_verified':bool(row['primitive_places'])})
    output.write_text(json.dumps({'join_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
        'dump_sha256':hashlib.sha256(raw).hexdigest(),'rows':rows,
        'ports_with_actual_site_candidates':sum(bool(r['site_reverse_candidates']) for r in rows),
        'limitation':'Reverse site lookup alone does not prove DDR primitive-to-port net connectivity or internal bank metadata.',
        'IO_gate_passed':False},indent=2),encoding='ascii')
    print('Actual site candidates:',sum(bool(r['site_reverse_candidates']) for r in rows),'of',len(rows))
if __name__=='__main__':main()
