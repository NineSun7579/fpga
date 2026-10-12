"""Append-only correction for copied baseline Python cache; no source edit or failed evidence reset."""
from preflight import *
import shutil,time
E=HERE/'evidence/runtime'
m=load(HERE/'manifest.json')
require(not (E/'controller_launch.json').exists(),'Cannot revise after actual PDS launch')
archive=E/'preparation_revision01';archive.mkdir()
for n in ['manifest.json']:
    shutil.copy2(HERE/n,archive/n)
for n in ['full_copy.json','producer_provenance.json','initial_project_binding.json']:
    shutil.copy2(E/n,archive/n)
m['full_source_copy_hashes']={p.relative_to(HERE).as_posix():sha(p) for d in ['rtl','inputs'] for p in (HERE/d).rglob('*') if p.is_file()}
for n,h in m['full_source_copy_hashes'].items():require((HERE/n).read_bytes()==(Path(m['baseline_root'])/n).read_bytes(),'Baseline byte comparison failed')
m['immutable_hashes']={p.relative_to(HERE).as_posix():sha(p) for d in ['rtl','inputs','constraints_templates','constraints_live','runtime'] for p in (HERE/d).rglob('*') if p.is_file() and ('__pycache__' not in p.parts or d in ['rtl','inputs'])}
for n in ['project.pds','project_template.pds','sourcehash.json','source04hash.json']:m['immutable_hashes'][n]=sha(HERE/n)
(HERE/'manifest.json').write_text(json.dumps(m,indent=2)+'\n',encoding='ascii')
save('preparation_revision01.json',{'time':time.time(),'reason':'Full copy contains baseline inputs/source/__pycache__/patch_top_sfp.cpython-312.pyc; source inventory remains 741 and full source copy is 742','prior_manifest_sha256':sha(archive/'manifest.json'),'manifest_sha256':sha(HERE/'manifest.json'),'full_copy_hashes':m['full_source_copy_hashes'],'source741_byte_identical':True,'producer_hashes':{n:h for n,h in m['immutable_hashes'].items() if n.startswith('runtime/')},'failure_preserved':True})
verify();print('严格build04验证PASS：741源库存、742完整源树文件、186登记；首次失败原样保留',flush=True)
