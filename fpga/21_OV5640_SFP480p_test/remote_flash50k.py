# -*- coding: utf-8 -*-
"""remote_flash50k.py v2 -- 对方电脑远程烧录 50K, -EncodedCommand 防 $ 插值"""
import sys, base64
sys.path.insert(0, r'C:\Users\NineSun\Desktop\ov56401\ov5640_sfp480p_test')
from mcp_call import post, parse_body, ensure_init

PEER = 'opencode-lan-mcp@LAPTOP-AJQHFMKI'
TCL  = 'D:/Documents/Code/Embedded_completion_Github/21_OV5640_SFP480p_test/flash_50k_rev44.tcl'
LOG  = 'D:/Documents/Code/Embedded_completion_Github/21_OV5640_SFP480p_test/flash50k_rev44_out.log'

ps = (
 "Get-Process cdt_cfg,cdt_js -EA SilentlyContinue | Stop-Process -Force\n"
 "Start-Process -FilePath 'E:/pango/PDS_2022.2-SP6.4/bin/cdt_js.exe' -ArgumentList '-port','65470' -WindowStyle Hidden\n"
 "Start-Sleep 6\n"
 "Start-Process -FilePath 'E:/pango/PDS_2022.2-SP6.4/bin/cdt_cfg.exe' -ArgumentList '-ip','127.0.0.1','-port','65470','-file','" + TCL + "' "
 "-RedirectStandardOutput '" + LOG + "' -RedirectStandardError '" + LOG + ".err' -WindowStyle Hidden\n"
 "$ok=0\n"
 "foreach($i in 1..30){\n"
 "  Start-Sleep 3\n"
 "  $t = Get-Content '" + LOG + "' -Raw -EA SilentlyContinue\n"
 "  if($t -match 'Program. execute successfully'){ $ok=1; break }\n"
 "}\n"
 "if($ok){ 'FLASH_OK' } else { 'FLASH_TIMEOUT' }\n"
 "Get-Content '" + LOG + "' -EA SilentlyContinue | Select-String -Pattern 'PGL|PG2L|done bit|E:|uccess' | ForEach-Object { $_.Line }\n"
 "Get-Process cdt_cfg,cdt_js -EA SilentlyContinue | Stop-Process -Force\n")

enc = base64.b64encode(ps.encode('utf-16-le')).decode()
cmd = 'powershell -NoProfile -EncodedCommand ' + enc

sid = ensure_init()
_, body = post({"jsonrpc": "2.0", "id": 230, "method": "tools/call",
                "params": {"name": "peer_call", "arguments": {
                    "peer": PEER, "tool": "oc_shell", "arguments": {"command": cmd}}}},
               sid, timeout=600)
print(parse_body(body))
