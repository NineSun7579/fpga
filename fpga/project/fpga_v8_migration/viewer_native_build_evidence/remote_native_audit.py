"""Capture actual compile/link dependencies without running the candidate."""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tarfile

ROOT=Path.cwd().resolve()
assert ROOT.name.startswith('fpga_v8_viewer_native_build_20261005'),ROOT
BUILD=ROOT/'artifacts/viewer_build'


def dump(name,value):
    (ROOT/name).write_text(json.dumps(value,indent=2)+'\n')


def info(p):
    p=Path(p); h=hashlib.sha256()
    with p.open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    return {'path':str(p),'realpath':str(p.resolve()),'bytes':p.stat().st_size,
            'sha256':h.hexdigest(),'symlink':os.readlink(p) if p.is_symlink() else None}


def command(args,cwd=ROOT):
    p=subprocess.run(args,cwd=cwd,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    return {'argv':args,'rc':p.returncode,'stdout':p.stdout,'stderr':p.stderr}


def loader_paths(text):
    return {Path(p) for p in re.findall(r'(?:=>\s+|^\s*)(/[^\s()]+)',text,re.M) if Path(p).is_file()}


def snapshot(paths,prefix):
    records=[]
    (ROOT/prefix).mkdir(exist_ok=True)
    for p in sorted(set(Path(p) for p in paths)):
        if not p.is_file(): continue
        record=info(p);dest=ROOT/prefix/str(p).lstrip('/')
        dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,dest);records.append(record)
    dump(prefix+'_manifest.json',records)
    return records


def preflight():
    versions={name:command(args) for name,args in {
        'qmake_version':['/usr/lib/qt5/bin/qmake','-v'],'qmake_query':['/usr/lib/qt5/bin/qmake','-query'],
        'gxx_version':['g++','-v'],'gxx_search_dirs':['g++','-print-search-dirs'],
        'gxx_specs':['g++','-dumpspecs'],'opencv_version':['pkg-config','--modversion','opencv4'],
        'opencv_flags':['pkg-config','--cflags','--libs','opencv4'],'make_version':['make','--version'],
        'ld_version':['ld','--version'],'uname':['uname','-a'],
    }.items()}
    dump('toolchain_versions.json',versions)
    keys=['PATH','LANG','LC_ALL','LC_CTYPE','LD_LIBRARY_PATH','LIBRARY_PATH','CPATH','CPLUS_INCLUDE_PATH',
          'C_INCLUDE_PATH','QMAKESPEC','QMAKEPATH','PKG_CONFIG_PATH','QT_SELECT','SOURCE_DATE_EPOCH','CFLAGS','CXXFLAGS','LDFLAGS']
    dump('build_environment.json',{k:os.environ.get(k) for k in keys})
    tools={Path(shutil.which(n)) for n in ['gcc','g++','as','ld','make','pkg-config','readelf','objdump','objcopy','ar']}
    tools|={Path('/usr/lib/qt5/bin/qmake'),Path('/usr/lib/qt5/bin/moc')}
    for name in ['cc1plus','collect2','lto-wrapper','as','ld']:
        value=command(['g++','-print-prog-name='+name])['stdout'].strip()
        tools.add(Path(value) if '/' in value else Path(shutil.which(value)))
    runtime={}
    for p in sorted(tools):
        result=command(['ldd',str(p)]);runtime[str(p)]=result;tools|=loader_paths(result['stdout'])
    dump('toolchain_runtime_ldd.json',runtime)
    records=snapshot(tools,'toolchain_snapshot')
    accelerator={}
    for name in ['librknnrt.so','librga.so']:
        path=command(['g++','-print-file-name='+name])['stdout'].strip()
        if Path(path).is_file():accelerator[name]=info(path)
    dump('accelerator_libraries_before.json',accelerator)
    print(json.dumps({'toolchain_files':len(records),'accelerator_libraries':accelerator}))


def collect():
    rc=int((ROOT/'build_return_code.txt').read_text())
    products={p.name:info(p) for p in sorted(BUILD.glob('*.o'))}
    if (BUILD/'detview-native-candidate').is_file():products['detview-native-candidate']=info(BUILD/'detview-native-candidate')
    dump('product_manifest.json',products)
    deps=set();units={}
    for p in BUILD.glob('*.d'):
        text=p.read_text().replace('\\\n',' ')
        names=text.split(':',1)[1].split()
        paths=[str((BUILD/n).resolve()) if not n.startswith('/') else n for n in names]
        units[p.name]=paths;deps|=set(paths)
    dump('compiler_dependencies_by_unit.json',units)
    compiler_records=snapshot(deps,'compiler_dependency_snapshot')
    log=(ROOT/'compile_link.log').read_text(errors='replace')
    inputs={Path(line.strip()) for line in log.splitlines() if line.startswith('/') and Path(line.strip()).is_file()}
    link_records=snapshot(inputs,'linker_input_snapshot')
    runtime=command(['ldd',str(BUILD/'detview-native-candidate')]) if rc==0 else {}
    dump('candidate_runtime_ldd.json',runtime)
    runtime_records=snapshot(loader_paths(runtime.get('stdout','')),'runtime_library_snapshot')
    config=set()
    if (BUILD/'Makefile').is_file():
        text=(BUILD/'Makefile').read_text().replace('\\\n',' ')
        config|={Path(p) for p in re.findall(r'/[^\s\\]+\.(?:prf|conf|pri)',text)}
    config|={Path('/usr/lib/aarch64-linux-gnu/pkgconfig/opencv4.pc'),Path('/usr/bin/qtchooser'),
             Path('/usr/lib/aarch64-linux-gnu/qt5/mkspecs/features/data/dummy.cpp')}
    config_records=snapshot(config,'qmake_config_snapshot')
    elf={}
    if rc==0:
        for name,args in {
            'header':['readelf','-h','detview-native-candidate'],'sections':['readelf','-SW','detview-native-candidate'],
            'dynamic':['readelf','-dW','detview-native-candidate'],'notes':['readelf','-nW','detview-native-candidate'],
            'comment':['readelf','-p','.comment','detview-native-candidate'],
            'symbols':['readelf','-sW','detview-native-candidate'],'disassembly':['objdump','-d','detview-native-candidate'],
        }.items():
            result=command(args,cwd=BUILD)
            (ROOT/('elf_'+name+'.txt')).write_text(result['stdout']+result['stderr'])
            elf[name]={'rc':result['rc'],'file':'elf_'+name+'.txt'}
    dump('elf_evidence.json',elf)
    warnings=[line for line in log.splitlines() if re.search(r'warning:|error:|Warning:|Error:|No relevant classes|parse error|Failure to find',line)]
    dump('build_diagnostics.json',{'warning_lines':warnings,'build_return_code':rc})
    with tarfile.open(ROOT/'dependency_snapshots.tar.gz','w:gz') as tar:
        for name in ['compiler_dependency_snapshot','linker_input_snapshot','runtime_library_snapshot','toolchain_snapshot','qmake_config_snapshot']:
            tar.add(ROOT/name,arcname=name)
    dump('dependency_archive_identity.json',info(ROOT/'dependency_snapshots.tar.gz'))
    (ROOT/'rebuilt').mkdir(exist_ok=True)
    for name in products:shutil.copyfile(BUILD/name,ROOT/'rebuilt'/name)
    generated=ROOT/'generated';generated.mkdir(exist_ok=True)
    for p in BUILD.iterdir():
        if p.is_file() and (p.suffix=='.d' or p.name in ['Makefile','.qmake.stash','main.moc','moc_predefs.h','moc_vision_pipeline.cpp','moc_calibration_capture.cpp']):
            shutil.copyfile(p,generated/p.name)
    files=sorted(p.name for p in ROOT.iterdir() if p.is_file() and
                 (p.suffix in ['.json','.log','.txt'] or p.name=='dependency_snapshots.tar.gz'))
    files+=['rebuilt/'+name for name in products]
    files+=['generated/'+p.name for p in generated.iterdir() if p.is_file()]
    print(json.dumps({'build_return_code':rc,'products':products,'warning_lines':warnings,'download_files':files,
                      'compiler_dependencies':len(compiler_records),'linker_inputs':len(link_records),
                      'runtime_libraries':len(runtime_records),'qmake_inputs':len(config_records)}))


if __name__=='__main__':{'preflight':preflight,'collect':collect}[sys.argv[1]]()
