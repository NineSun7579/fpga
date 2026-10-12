"""Serialized vendor help query; no design flow or hardware action."""
import os
import subprocess
from prepare import HERE
from build_later import idle, PDS

lock = HERE.parent / 'fpga/build.lock'
with lock.open('x') as stream:
    stream.write(str(os.getpid()))
try:
    idle()
    (HERE / 'query_help').mkdir(exist_ok=True)
    script = HERE / 'query_pnr.tcl'
    script.write_bytes(b'help pnr\n')
    result = subprocess.run([str(PDS), '-file', str(script), '-work_dir', str(HERE / 'query_help'),
                             '-project_name', 'query_help'], stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, check=False, cwd=HERE / 'query_help')
    (HERE / 'query_pnr.log').write_bytes(result.stdout)
    print(result.stdout.decode('gb18030', errors='replace'))
finally:
    lock.unlink()
