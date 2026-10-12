"""Bind static bank definitions and inspect binary strings; no acceptance."""
from pathlib import Path
import re,json,hashlib
H=Path(__file__).resolve().parent
BASE=Path('C:/pango/PDS_2022.2-SP6.4/arch/vendor/pango/logos2')
def main():
    out=H/'scan_result.json';assert not out.exists()
    paths=[BASE/'pg2l100h/package/fbg484.eval',BASE/'pg2l100h/db/arch_schm.eadf',
           BASE/'pg2l100h/db/arch_lp.eadf',BASE/'common/valence/device/grid/IOBD/IOBD.eval',
           BASE/'pg2l100h/data/io_standard/bankrefpins.txt']
    wanted=re.compile(rb'BANK|bank|DIFFIO_[LR]|IOBD_0_624|IOBD_372_468|PAP_IO|bankId|bank_id')
    rows=[]
    for path in paths:
        if not path.exists():rows.append({'path':str(path),'exists':False});continue
        data=path.read_bytes();hits=[]
        for m in re.finditer(rb'[\x20-\x7e]{4,}',data):
            if wanted.search(m[0]):hits.append({'byte_offset':m.start(),'length':len(m[0]),'text_preview':m[0][:500].decode('ascii')})
        rows.append({'path':str(path),'exists':True,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest(),
                     'header_hex':data[:32].hex(),'matching_ascii_strings':hits,
                     'complete_text':data.decode('ascii') if path.suffix=='.txt' else None})
    out.write_text(json.dumps({'status':'STATIC_DIAGNOSTIC_ONLY','files':rows,'internal_used_io_bank_verified':False,
                              'IO_gate_passed':False,'limitation':'No ASCII hit does not establish absent bank data; reference pins do not define full bank boundary.'},indent=2),encoding='ascii')
    print([(r['path'],len(r.get('matching_ascii_strings',[])),r.get('bytes')) for r in rows])
if __name__=='__main__':main()
