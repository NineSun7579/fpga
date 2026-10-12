"""Pure marker/lock check. Deliberately contains no workload command."""
import json
import shlex
from certify import HERE, call

stage=json.loads((HERE/'remote_stage.json').read_text())['remote_root']
command='test -f '+shlex.quote(stage+'/workload_success')+' && test -d '+shlex.quote(stage+'/workload_started')+' && if mkdir '+shlex.quote(stage+'/workload_started')+' 2>/dev/null; then echo GUARD_BROKEN; exit 1; else echo REFUSE_REPEAT_CONFIRMED_NO_INFERENCE; fi'
call('repeat_guard_pure',command,sudo=True)
