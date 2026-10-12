"""Actual new ADIF CDB: all364 clock pairs and each surviving complement leaf."""
import re
from preflight import HERE, load, sha, require

def parse_cdb(path):
    raw=path.read_bytes();pos=raw.find(b'(CDB ');require(pos>=0,'No actual CDB in new export')
    stack=[];root=None
    for m in re.finditer(r'"(?:[^"\\]|\\.)*"|\\[^\s]+|[()]|[^\s()]+',raw[pos:].decode('ascii',errors='backslashreplace')):
        t=m[0]
        if t=='(':stack.append([])
        elif t==')':
            n=stack.pop()
            if stack:stack[-1].append(n)
            else:root=n;break
        else:stack[-1].append(t)
    require(root and root[0]=='CDB','Malformed actual CDB')
    return root
def field(e,key,default=None):
    n=next((x for x in e[1:] if isinstance(x,list) and x[0]==key),None)
    return n[1] if n and len(n)>1 else default
def prove(stage,dump,graph,coverage=None):
    from physical_flow import EVIDENCE,record
    proof=load(EVIDENCE/'coverageproof_synthesis.json');expected={tuple(p) for p in proof['retained_clock_pairs']}
    cdb=parse_cdb(dump);pairs=[];budgets=[];errors=[]
    for e in cdb[1:]:
        if not isinstance(e,list):continue
        if e[0]=='FP' and field(e,'FCK') is not None and field(e,'TCK') is not None:
            a=field(e,'FCK').strip('"');b=field(e,'TCK').strip('"')
            pairs.append({'pair':[a,b],'setup':field(e,'SU'),'hold':field(e,'HD'),'line':field(e,'LN'),'cdbid':field(e,'CDBID')})
            if field(e,'SU')!='1' or field(e,'HD')!='1':errors.append({'wrong_setup_hold':e})
        if e[0]=='MMD':budgets.append({'delay_ps':field(e,'DELAY'),'datapath_only':field(e,'DATAPATH_ONLY'),'line':field(e,'LN'),'cdbid':field(e,'CDBID')})
    actual={tuple(p['pair']) for p in pairs}
    if actual!=expected or len(pairs)!=364:errors.append({'missing_clockpairs':sorted(expected-actual),'unexpected_clockpairs':sorted(actual-expected),'clockpair_record_count':len(pairs)})
    if len(budgets)!=4 or any(e['delay_ps']!='15238' or e['datapath_only']!='1' for e in budgets):errors.append({'bad_mailbox_budgets':budgets})
    constraints=HERE/'constraints_live/clock.fdc';lines=constraints.read_text().splitlines();inheritance=[]
    binding={b['logical']:b for b in coverage['bindings']} if coverage is not None else {}
    for camera in proof['cameras']:
        allowed=set(camera['compile_complement'])|set(camera['synthesis_complement'])
        for logical in camera['synthesis_complement']:
            b=binding.get(logical,{'physical':[logical],'status':'synthesis_exact'})
            if b['status']=='tool_cleanup':
                require(b.get('cleanup_evidence'),'Missing actual cleanup proof')
                inheritance.append({'camera':camera['camera'],'logical':logical,'eliminated_by_actual_tool':b['cleanup_evidence']});continue
            for physical in b['physical']:
                cell,port=physical.rsplit('/',1);entries=[]
                if cell not in graph['primitives']:errors.append({'missing_physical_leaf':physical});continue
                for e in graph['primitives'][cell].get('cdb_entries',[]):
                    if field(e,'PINNAME')!=port:continue
                    if field(e,'FILENAME','').strip('"')!=constraints.as_posix():continue
                    ln=int(field(e,'LINENUM'));text=lines[ln-1]
                    if not text.startswith('set_false_path -from ') or not text.endswith('-to [get_clocks {ddrphy_sysclk}]'):continue
                    origin=field(e,'HIER','').lstrip('\\')+'/'+port
                    if origin in allowed:entries.append({'cdbid':field(e,'CDBID'),'line':ln,'actual_source_pin':origin})
                if not entries:errors.append({'missing_actual_complement_inheritance':physical,'logical':logical})
                inheritance.append({'camera':camera['camera'],'logical':logical,'physical':physical,'entries':entries})
    result={'stage':stage,'passed':not errors,'clockpair_count':len(pairs),'clockpair_records':pairs,
            'mailbox_maxdelay_records':budgets,'complement_inheritance':inheritance,'errors':errors,
            'dump_path':str(dump),'dump_sha256':sha(dump),'constraint_sha256':sha(constraints)}
    record('actual_cdb_'+stage+'_proof.json',result)
    require(not errors,'New actual364 CDB/complement inheritance gate failed: '+stage)
    return result
