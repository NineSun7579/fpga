"""Seal this local review delivery and pycompile only its Python tools."""
from pathlib import Path
import difflib, hashlib, json, py_compile
HERE=Path(__file__).resolve().parent
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    analysis=HERE/'analysis_tools';diffs=[];patches=[]
    for p in sorted(analysis.glob('*.py')):
        old=HERE/'review_templates/analysis_tools'/p.name
        before=old.read_bytes() if old.exists() else b'';after=p.read_bytes()
        diffs.append(''.join(difflib.unified_diff(before.decode('latin1').splitlines(True),after.decode('latin1').splitlines(True),
                     fromfile='build01/analysis_tools/'+p.name if old.exists() else '/dev/null',
                     tofile='build02/analysis_tools/'+p.name)))
        patches.append({'path':p.relative_to(HERE).as_posix(),'before_sha256':sha(old) if old.exists() else None,
                        'after_sha256':sha(p),'actual_graph_validated':False})
    (HERE/'analysis_patch.diff').write_bytes(''.join(diffs).encode('latin1'))
    compiled=[]
    for p in [HERE/'preflight.py',HERE/'seal_delivery.py']+sorted(analysis.glob('*.py')):
        py_compile.compile(str(p),doraise=True);compiled.append(p.relative_to(HERE).as_posix())
    (HERE/'analysis_patch_manifest.json').write_bytes((json.dumps({'status':'PYCOMPILE_PASS_GRAPH_VALIDATION_PENDING',
        'patches':patches,'compiled':compiled,'patch_sha256':sha(HERE/'analysis_patch.diff'),
        'old_name_assertions_deleted':False,'physical_runner_included':False},indent=2)+'\n').encode('ascii'))
    from preflight import verify
    receipt=verify()
    files=[p for p in HERE.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.name!='delivery_hashes.json']
    (HERE/'delivery_hashes.json').write_bytes((json.dumps({p.relative_to(HERE).as_posix():sha(p) for p in sorted(files)},indent=2)+'\n').encode('ascii'))
    print('DELIVERY_SEALED_PYCOMPILE_PASS; NO_TOOL_START; map_gate='+receipt['map_gate']['status'])
if __name__=='__main__':main()
