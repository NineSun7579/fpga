from pathlib import Path
import hashlib, json, re, shutil, subprocess
from pypdf import PdfReader
HERE=Path(__file__).resolve().parent
BUILD=HERE.parent/'source_diagnostics_build_01'
PDS=Path('C:/pango/PDS_2022.2-SP6.4/bin/pds_shell.exe')
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def save(n,x): (HERE/n).write_text(json.dumps(x,indent=2,ensure_ascii=False),encoding='utf8')
def idle(label):
    x=subprocess.run(['powershell','-NoProfile','-Command',"ConvertTo-Json -InputObject @(Get-Process | Where-Object { $_.ProcessName -match '^(pds|pds_shell|ta)$' } | Select-Object Id,ProcessName) -Compress"],capture_output=True,check=True)
    items=json.loads(x.stdout);save('processes_'+label+'.json',items);assert not items,items
def main():
    idle('prepare');assert not (HERE/'project.pds').exists()
    protected={str(p):sha(p) for folder in ['inputs','rtl','synthesize','synthesis_export_02','sta_ab_01'] for p in (BUILD/folder).rglob('*') if p.is_file()}
    protected[str(BUILD/'project.pds')]=sha(BUILD/'project.pds')
    save('build01_guard.json',protected)
    for folder in ['inputs','rtl']:shutil.copytree(BUILD/folder,HERE/folder)
    project=(BUILD/'project.pds').read_bytes()
    project=re.sub(rb'\(_gci_state \(_integer \d+\)\)',b'(_gci_state (_integer 0))',project)
    (HERE/'project.pds').write_bytes(project)
    changes=[]
    for p in (HERE/'rtl').rglob('*.v'):
        raw=p.read_bytes()
        new,n=re.subn(rb'\(\*\s*ASYNC_REG\s*=\s*"TRUE"\s*\*\)',b'(* syn_preserve=1, syn_allow_retiming=0 *)',raw)
        if n:p.write_bytes(new);changes.append({'file':str(p.relative_to(HERE)),'attributes':n,'before':sha(BUILD/p.relative_to(HERE)),'after':sha(p)})
    save('attribute_changes.json',changes)
    docs=Path('C:/pango/PDS_2022.2-SP6.4/doc')
    reader=PdfReader(docs/'ADS_Synthesis_User_Guide.pdf')
    (HERE/'legal_attributes.txt').write_text('\n'.join('PDF PAGE '+str(i+1)+'\n'+reader.pages[i].extract_text() for i in [52,53,55,83,84,91,92,93]),encoding='utf8')
    dst=HERE/'actual';dst.mkdir()
    for n in ['parse_objects.py','resolve_manifest.py','classify_paths.py','derive_sta_sdc.py','derive_exact_complement.py']:
        raw=(BUILD/'sta_ab_01'/n).read_bytes().replace(b"synthesis_export_02/synthesis_dump.txt",b"synthesis_export/synthesis_dump.txt")
        (dst/n).write_bytes(raw)
    save('input_hashes.json',{str(p.relative_to(HERE)):sha(p) for folder in ['inputs','rtl'] for p in (HERE/folder).rglob('*') if p.is_file()})
    assert all(sha(Path(p))==h for p,h in protected.items())
    print('Prepared route01; legal HDL attributes only; original physical FDC retained for initial synthesis',flush=True)
if __name__=='__main__':main()
