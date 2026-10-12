"""Read ELF metadata and verify saved artifacts; do not execute binaries."""
import hashlib
import json
from pathlib import Path
from elftools.elf.elffile import ELFFile

HERE = Path(__file__).resolve().parent
OLD = HERE.parent / 'viewer_build_provenance04'

def digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def elf_metadata(p):
    with p.open('rb') as f:
        elf = ELFFile(f)
        sections = {s.name: dict(bytes=s['sh_size'], sha256=hashlib.sha256(s.data()).hexdigest())
                    for s in elf.iter_sections() if s.name and s['sh_type'] != 'SHT_NOBITS'}
        symbols = {}
        symtab = elf.get_section_by_name('.symtab')
        if symtab:
            for s in symtab.iter_symbols():
                if s['st_info']['type'] == 'STT_FUNC' and s['st_shndx'] != 'SHN_UNDEF':
                    symbols[s.name] = s['st_size']
        return dict(sections=sections, functions=symbols)

downloads = json.loads((HERE / 'download_receipt05.json').read_text())
checks = [dict(file=r['local'], matched=digest(HERE/r['local']) == r['sha256']
               and (HERE/r['local']).stat().st_size == r['bytes']) for r in downloads]
objects = []
for new in HERE.glob('generated05__*.o'):
    old = OLD / ('source04__' + new.name.removeprefix('generated05__'))
    if not old.exists():
        continue
    nm, om = elf_metadata(new), elf_metadata(old)
    names = set(nm['sections']) | set(om['sections'])
    fnames = set(nm['functions']) | set(om['functions'])
    objects.append(dict(object=new.name.removeprefix('generated05__'),
        new_sha256=digest(new), old_sha256=digest(old), byte_identical=digest(new)==digest(old),
        changed_sections=[dict(section=n,old=om['sections'].get(n),new=nm['sections'].get(n))
                          for n in sorted(names) if om['sections'].get(n)!=nm['sections'].get(n)],
        changed_function_sizes=[dict(symbol=n,old_bytes=om['functions'].get(n),new_bytes=nm['functions'].get(n))
                                for n in sorted(fnames) if om['functions'].get(n)!=nm['functions'].get(n)]))
moc = []
for name in ['main.moc', 'moc_vision_pipeline.cpp', 'moc_calibration_capture.cpp', 'moc_predefs.h']:
    old, new = OLD/('source04__'+name), HERE/('generated05__'+name)
    if old.exists() and new.exists():
        moc.append(dict(file=name,old_sha256=digest(old),new_sha256=digest(new),byte_identical=digest(old)==digest(new)))
old = OLD/'deploy04__detview-driving-demo'
new = HERE/'generated05__detview'
elf = None
if new.exists():
    nm, om = elf_metadata(new), elf_metadata(old)
    names = set(nm['functions']) | set(om['functions'])
    elf=dict(old_sha256=digest(old),new_sha256=digest(new),byte_identical=digest(old)==digest(new),
             changed_function_sizes=[dict(symbol=n,old_bytes=om['functions'].get(n),new_bytes=nm['functions'].get(n))
                                     for n in sorted(names) if om['functions'].get(n)!=nm['functions'].get(n)])
tools_begin=json.loads((HERE/'tools_begin05.json').read_text())
tools_end=json.loads((HERE/'tools_end05.json').read_text())
result=dict(download_checks=checks,all_downloads_matched=all(x['matched'] for x in checks),
            toolchain_start_end_matched=tools_begin==tools_end,objects=objects,moc=moc,elf=elf,
            limitation='Section/function metadata comparisons identify differences, not their semantic cause.')
(HERE/'artifact_comparison05.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
assert result['all_downloads_matched']
print(json.dumps(dict(downloads=len(checks),all_matched=result['all_downloads_matched'],
    tools_unchanged=result['toolchain_start_end_matched'],
    objects_identical=sum(x['byte_identical'] for x in objects),objects_compared=len(objects),
    moc=moc,elf=elf),indent=2))
