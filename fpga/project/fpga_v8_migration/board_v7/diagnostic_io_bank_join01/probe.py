"""Read-only original artifact join; never waives bank metadata failures."""
from pathlib import Path
import hashlib,json,re,xml.etree.ElementTree as ET
from collections import Counter
H=Path(__file__).resolve().parent
ROOT=H.parent/'source_diagnostics_timing_build_01/route_attempt_03/evidence'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def rows(path):
    root=ET.fromstring(path.read_bytes())
    return [[d.text or '' for d in r.findall('data')] for r in root.findall('row')]
def main():
    output=H/'join_result.json';assert not output.exists()
    paths=[ROOT/'final_export/routed_dump.txt',ROOT/'evidence/place_route_pnr_io_report.xml',ROOT/'evidence/place_route_pnr_pinout_report.xml']
    raw=paths[0].read_bytes();io=rows(paths[1]);pins=rows(paths[2]);assert len(io)==112
    placed={}
    for m in re.finditer(rb'\(INSTANNOTATE\s+\(INSTREF\s+(\S+)\s*\)\s*\(PLACE\s+\S+\s+\(DEVINSTREF\s+(IOBD|IOBS|IOLHR|IOLHL)\s+\(SITEREF\s+(\d+)\s+(\d+)\)\)\)',raw):
        placed.setdefault(m[1],[]).append(tuple(v.decode('ascii') for v in m.groups()[1:]))
    # Each INSTANCE ends before the next INSTANCE, NET or enclosing cell boundary;
    # exact attribute extraction uses balanced parentheses respecting quoted text.
    byloc={}
    for match in re.finditer(rb'\(INSTANCE\s+(\S+)',raw):
        start=match.start();depth=0;quoted=False;escape=False;end=None
        for i in range(start,len(raw)):
            byte=raw[i]
            if quoted:
                if escape:escape=False
                elif byte==92:escape=True
                elif byte==34:quoted=False
            elif byte==34:quoted=True
            elif byte==40:depth+=1
            elif byte==41:
                depth-=1
                if depth==0:end=i+1;break
        assert end is not None
        block=raw[start:end]
        loc=re.search(rb'\(ATTRIBUTE PAP_IO_LOC \(STRING ([^)]+)\)\)',block)
        if loc:byloc.setdefault(loc[1].decode('ascii').strip('"'),[]).append(match[1])
    bypin={}
    for p in pins:bypin.setdefault(p[0],[]).append(p)
    records=[];errors=[];banks=Counter()
    for row in io:
        port,direction,loc,bank=row[:4]
        matches=[p for p in bypin.get(loc,[]) if len(p)>4 and p[4]==port]
        if len(matches)!=1:errors.append({'port':port,'error':'pinout join ambiguous/missing','count':len(matches)});continue
        p=matches[0];fn=re.search(r'(?:DIFFIO|IO)_([LR]\d+)(?:_|$)',p[3])
        derived='BANK'+fn[1] if fn else None;sites=[]
        for inst in byloc.get(loc,[]):
            for place in placed.get(inst,[]):
                if place[0] in {'IOBD','IOBS'} and '_'.join(place)==p[1]:sites.append({'instance':inst.decode('ascii').lstrip('\\'),'actual_PLACE':place})
        if not sites or derived is None:errors.append({'port':port,'error':'missing primitive PLACE/function bank','loc':loc})
        banks[derived]+=1
        records.append({'port':port,'loc':loc,'report_bank':bank,'pinout_bank':p[2],'function_name':p[3],
                        'function_derived_bank':derived,'package_site':p[1],'primitive_places':sites})
    output.write_text(json.dumps({'status':'PHYSICAL_JOIN_ONLY_NOT_BANK_ACCEPTANCE','inputs':{str(p):sha(p) for p in paths},
        'rows':records,'port_count':len(io),'joined_count':len(records),'errors':errors,
        'function_derived_counts':dict(banks),'physical_join_complete':len(records)==112 and not errors,
        'internal_bank_metadata_verified':False,'IO_gate_passed':False},indent=2),encoding='ascii')
    print(json.dumps({'joined':len(records),'errors':len(errors),'banks':dict(banks),'IO_gate_passed':False}))
if __name__=='__main__':main()
