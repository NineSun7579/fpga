"""Compile and run actual standalone C++ tests locally; no hardware access."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

root=Path(__file__).resolve().parent
parser=argparse.ArgumentParser()
parser.add_argument('--compiler',default=shutil.which('g++') or r'C:\gcc\mingw64\bin\g++.exe')
args=parser.parse_args()
units={
    'c5-runtime':[root/'tests/c5_transaction_test.cpp'],
    'camera-dma':[root/'tests/camera_dma_test_main.cpp',root/'viewer/camera_dma_selftest.cpp'],
}
outputs={}
with tempfile.TemporaryDirectory(prefix='c5-host-test-') as tmp:
    flags=['-std=c++11','-DNDEBUG','-Wall','-Wextra','-Werror','-static','-pthread']
    for name,sources in units.items():
        binary=Path(tmp)/(name+'.exe')
        command=[args.compiler]+flags+[str(p) for p in sources]+['-o',str(binary)]
        subprocess.run(command,check=True)
        result=subprocess.run([str(binary)],check=True,capture_output=True,text=True)
        outputs[name]=result.stdout
        print(result.stdout,end='')
    subprocess.run([sys.executable,str(root/'audit_candidate.py')],check=True)
    report=dict(status='passed',scope='standalone C5 transaction and candidate camera DMA; fresh native GUI compile pending',
        compiler=args.compiler,flags=flags,output=outputs,
        sources={p.relative_to(root).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
                 for p in sorted(set(p for group in units.values() for p in group) | {
                     root/'c5_runtime_selftest.h',root/'c5_transaction.h',root/'runtime_camera_geometry.h',
                     root/'viewer/camera_dma.h',root/'viewer/fair_dma.h',root/'viewer/runtime_camera_geometry.h'})})
    (root/'test_results.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
