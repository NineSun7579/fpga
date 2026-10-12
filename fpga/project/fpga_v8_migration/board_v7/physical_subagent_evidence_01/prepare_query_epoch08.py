"""Create isolated constraint epochs without editing the active fixed06 inputs."""
from pathlib import Path
import re, json, shutil, hashlib
from native_query08 import idle
BASE=Path(__file__).resolve().parent
HERE=BASE.parent/'source_diagnostics_route_02'
OUT=BASE/'fixed_06'/'query_epoch08'
def main(out=OUT, query_file=BASE/'query_objects08.fdc'):
    OUT=out
    idle()
    OUT.mkdir(exist_ok=False)
    source=HERE/'standard_flow_fixed.pds'
    raw=source.read_bytes()
    # The project stays next to its RTL; only constraints are new absolute paths.
    for f in (HERE/'physical_constraints').glob('*.fdc'):
        dest=OUT/f.name
        data=f.read_bytes()
        if f.name=='clock.fdc':
            data=data.split(b'# Exact real-object CDC complement and mailbox absolute budget',1)[0]
            # Query only the current compiled design in the real constraint importer.
            data+=b'\n'+query_file.read_bytes()
        dest.write_bytes(data)
        old=('physical_constraints/'+f.name).encode('ascii')
        assert raw.count(old)==1
        raw=raw.replace(old,dest.resolve().as_posix().encode('ascii'))
    # Preserve all fixed06 failure outputs: use an independent project/work directory.
    def absolute_file(match):
        path=Path(match.group(2).decode('ascii'))
        if path.is_absolute(): return match.group(0)
        stage=path.parts[0]
        root=OUT if stage in {'compile','synthesize','device_map','place_route','constraint_check','bitstream'} else HERE
        return b'('+match.group(1)+b' "'+(root/path).resolve().as_posix().encode('ascii')+b'"'
    raw=re.sub(rb'\((_file|_ip|_ip_source_item) "([^"\r\n]+)"',absolute_file,raw)
    paths=re.findall(rb'\((?:_file|_ip|_ip_source_item) "([^"\r\n]+)"',raw)
    missing=[p.decode('ascii') for p in paths if not Path(p.decode('ascii')).exists() and not Path(p.decode('ascii')).is_relative_to(OUT)]
    assert not missing, missing
    shutil.copytree(HERE/'compile',OUT/'compile')
    project=OUT/'query_epoch08.pds'
    assert not project.exists()
    project.write_bytes(raw)
    (OUT/'identity.json').write_text(json.dumps({'original':str(source),'original_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'query_project':str(project),'bit_permitted':False},indent=2))
    print(project)
if __name__=='__main__':main()
