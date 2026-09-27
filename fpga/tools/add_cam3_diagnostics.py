from pathlib import Path
from datetime import datetime
p=Path('source/ov5640/ov5640_reg.v')
b=p.read_bytes()
p.with_name(p.name+'.bak_cam3diag_'+datetime.now().strftime('%Y%m%d_%H%M%S')).write_bytes(b)
old=b'                    REG_DBG_CAM_WORDS: rdata <= dbg_cam_words;'
assert b.count(old)==1
nl=b'\r\n' if b'\r\n' in b else b'\n'
new=nl.join([b"                    (BASE_ADDR + 32'h04): rdata <= dbg_i2c_status;",b"                    (BASE_ADDR + 32'h08): rdata <= dbg_href_raw;",b"                    (BASE_ADDR + 32'h0c): rdata <= dbg_sys_status;",old])
p.write_bytes(b.replace(old,new))
print('Added I2C/HREF/system words to first 16-byte register read')
