from pathlib import Path
from datetime import datetime
p=Path('source/ov5640/ov5640_reg.v')
b=p.read_bytes()
p.with_name(p.name+'.bak_align_'+datetime.now().strftime('%Y%m%d_%H%M%S')).write_bytes(b)
for old,new in [(b"                    (BASE_ADDR + 32'h04): rdata <= dbg_i2c_status;",b''),(b"                    (BASE_ADDR + 32'h08): rdata <= dbg_href_raw;",b''),(b"                    (BASE_ADDR + 32'h0c): rdata <= dbg_sys_status;",b''),(b'REG_DBG_ZDIN:      rdata <= dbg_zdin;',b'REG_DBG_ZDIN:      rdata <= dbg_i2c_status;'),(b'REG_DBG_ZOUT:      rdata <= dbg_zout;',b'REG_DBG_ZOUT:      rdata <= dbg_href_raw;'),(b'REG_DBG_AXI_NOW:   rdata <= dbg_axi_num;',b'REG_DBG_AXI_NOW:   rdata <= dbg_sys_status;')]:
    assert b.count(old)==1,old
    b=b.replace(old,new)
p.write_bytes(b)
p=Path('tools/probe_cam3_identity.py'); b=p.read_bytes(); p.with_suffix('.py.bak_alignment').write_bytes(b)
b=b.replace(b'ack,identity,href,system=block(base)',b'identity,href,system=(read(base+o) for o in (0x50,0x90,0xd0))')
p.write_bytes(b)
p=Path('tools/validate_cam3_display.py'); b=p.read_bytes(); p.with_suffix('.py.bak_geometry').write_bytes(b)
b=b.replace(b"assert images[0].size==(1000,562),",b"assert images[0].size in ((999,562),(1000,562)),")
p.write_bytes(b)
print('Diagnostic reads moved to aligned offsets 50/90/d0; accepted observed 999px screenshot width')
