"""Summarize existing execution receipts; performs no board actions."""
import difflib
import json
from pathlib import Path
import controller as c

roots=sorted(c.HERE.glob('execution_*/actual_result.json'),key=lambda p:p.stat().st_mtime)
root=roots[-1].parent
result=json.loads((root/'actual_result.json').read_bytes())
summary=dict(result=result,execution_directory=str(root),accepted=False,goal_complete=False)
cancel=root/'cancel-before-reboot'
proof=cancel/'qualified_v7_sram.binding.json'
if proof.exists():
    binding=json.loads(proof.read_bytes()); receipt=Path(binding['original_receipt'])
    summary['vendor_binding']=binding
    summary['vendor_receipt']=json.loads(receipt.read_bytes())
for name in ('cancel_reset','post_sram_command','admission_after_sram'):
    path=cancel/(name+'.stdout.txt')
    if path.exists(): summary[name]=path.read_text()
post=root/'post-reboot'
rebuilt=post/'rebuilt.prepare.json'
if rebuilt.exists():
    summary['rebuilt']=json.loads(rebuilt.read_bytes())
    summary['current_binding']=json.loads((post/'post_reboot/binding.json').read_bytes())
    summary['current_driver_raw_path']=str(post/'post_reboot/identity.stdout.txt')
    summary['admission_post_reboot']=json.loads((post/'admission_post_reboot.stdout.txt').read_bytes())
for name in ('controller.py','admission_guard.py'):
    src=c.GOAL/'recovery_execution_prepare05'/name
    (root/(name+'.diff')).write_text(''.join(difflib.unified_diff(src.read_text().splitlines(True),(c.HERE/name).read_text().splitlines(True),fromfile='prepare05/'+name,tofile='actual06/'+name)),encoding='utf-8')
summary['runtime_sha256']={name:c.sha(c.HERE/name) for name in ('controller.py','admission_guard.py','run_actual.py')}
c.save(root/'actual_summary.json',summary)
print(json.dumps(summary,ensure_ascii=False,indent=2))
