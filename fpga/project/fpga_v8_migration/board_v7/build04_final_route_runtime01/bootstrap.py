"""Copy reviewed offline algorithms only; never import an old controller."""
from pathlib import Path
import difflib, hashlib, json
HERE=Path(__file__).resolve().parent
BOARD=HERE.parent
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
    dest=HERE/'runtime';dest.mkdir(exist_ok=True)
    ledger=[]
    for name in ['graph_adapter.py','resolve_manifest.py','derive_new_constraints.py','endpoint_logic.py','endpoint_detail.py','endpoints.py']:
        src=BOARD/'build04_mailbox_clock_review01/analysis'/name
        raw=src.read_bytes();text=raw.decode('utf8')
        if name=='graph_adapter.py':
            old="allowed=r['type'].startswith(('bmsWIDEDFF','GTP_DFF','GTP_DRM','gopQ','gopSRL2','gopLUT5','gopLUT6','gopLUT7','gopLUT8','gopDRM18K','gopDRM36K'))"
            exact={'GTP_DFF','GTP_DFF_C','GTP_DFF_CE','GTP_DFF_E','GTP_DFF_P','GTP_DFF_PE','GTP_DFF_R','GTP_DRM18K_E1','bmsWIDEDFFCPE','bmsWIDEDFFCPE_Cell_1','bmsWIDEDFFCPE_Cell_14','bmsWIDEDFFCPE_Cell_16','bmsWIDEDFFCPE_Cell_17','bmsWIDEDFFCPE_Cell_18','bmsWIDEDFFCPE_Cell_2','bmsWIDEDFFCPE_Cell_3','bmsWIDEDFFCPE_Cell_7','bmsWIDEDFFCPE_Cell_8','bmsWIDEDFFCPE_Cell_9','bmsWIDEDFFRSE','bmsWIDEDFFRSE_Cell_1','bmsWIDEDFFRSE_Cell_12','bmsWIDEDFFRSE_Cell_5'}
            assert old in text
            text=text.replace(old,"allowed=r['type'] in "+repr(tuple(sorted(exact))))
        if name=='derive_new_constraints.py':
            text=text.replace('from graph_adapter import Resolver, classify, require','from graph_adapter import Resolver, classify, require\nfrom contract import validate_mapping, CONTRACT')
            text=text.replace("classify(cg);classified=classify(sg)","validate_mapping(m,sg); classify(cg);classified=classify(sg)")
            text=text.replace("require(len(pairs)==330,'Actual mapping must be re-evaluated; legacy 320/camera (1280 total) not accepted')","require(len(pairs)==CONTRACT['expected']['per_camera']['uniquePhysical'],'Exact candidate per-camera physical contract failed')")
            text=text.replace("require(len(allpairs)==1320,'Actual 1320 unique mailbox mapping required')","require(len(allpairs)==CONTRACT['expected']['uniquePhysical1280'],'Exact candidate physical contract failed')")
            text=text.replace("'physical_pairs':1320","'physical_pairs':CONTRACT['expected']['uniquePhysical1280']")
            text=text.replace("'legacy_1280_fallback':False","'candidate_specific_contract':True")
        out=dest/name
        if out.exists() and out.read_bytes()!=text.encode('utf8'):
            previous=json.loads((HERE/'reuse_ledger.json').read_bytes())
            assert any(x['destination']==str(out) and x['after_sha256']==sha(out) for x in previous),'Untracked local runtime drift'
        out.write_bytes(text.encode('utf8'))
        diff=''.join(difflib.unified_diff(raw.decode('utf8').splitlines(True),text.splitlines(True),fromfile=str(src),tofile=str(out)))
        (HERE/(name+'.diff')).write_text(diff or '# byte-identical reuse\n',encoding='utf8')
        ledger.append({'source':str(src),'destination':str(out),'before_sha256':sha(src),'after_sha256':sha(out),'modified':bool(diff),'diff':name+'.diff'})
    src=BOARD/'build04_mailbox_clock_review02/candidate_specific_expectation_contract.json'
    out=HERE/'candidate_specific_expectation_contract.json'
    if out.exists():assert out.read_bytes()==src.read_bytes()
    else:out.write_bytes(src.read_bytes())
    (HERE/'reuse_ledger.json').write_text(json.dumps(ledger,indent=2)+'\n',encoding='utf8')
    src=BOARD/'source_diagnostics_timing_build_03/runtime/targeted_reports.py'
    text=src.read_text(encoding='utf8');start=text.index('def records(');end=text.index('\ndef list_tcl(',start)
    out=dest/'report_records.py';raw='"""Reviewed streaming parser, byte-identical records() function."""\nimport re\nfrom pathlib import Path\nfrom contract import require\n\n'+text[start:end]+'\n'
    out.write_text(raw,encoding='utf8')
    ledger.append({'source':str(src),'destination':str(out),'before_sha256':sha(src),'after_sha256':sha(out),'modified':True,'scope':'records() body byte-identical; dependency imports local','diff':'report_records.py.diff'})
    (HERE/'report_records.py.diff').write_text(''.join(difflib.unified_diff(text.splitlines(True),raw.splitlines(True),fromfile=str(src),tofile=str(out))),encoding='utf8')
    (HERE/'reuse_ledger.json').write_text(json.dumps(ledger,indent=2)+'\n',encoding='utf8')
if __name__=='__main__':main()
