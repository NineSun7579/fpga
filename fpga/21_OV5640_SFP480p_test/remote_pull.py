# -*- coding: utf-8 -*-
"""remote_pull.py -- 对方电脑经 HTTP 拉取比特流并校验 md5"""
import sys
sys.path.insert(0, r'C:\Users\NineSun\Desktop\ov56401\ov5640_sfp480p_test')
from mcp_call import post, parse_body, ensure_init

PEER = 'opencode-lan-mcp@LAPTOP-AJQHFMKI'
RDIR = 'D:/Documents/Code/Embedded_completion_Github/21_OV5640_SFP480p_test/ov5640_sfp480p_test/generate_bitstream'

cmd = (
 "powershell -NoProfile -Command \""
 "Invoke-WebRequest -Uri http://192.168.0.184:8765/hdmi_ddr_ov5640_top.sbit "
 f"-OutFile {RDIR}/hdmi_ddr_ov5640_top.sbit -UseBasicParsing; "
 f"(Get-Item {RDIR}/hdmi_ddr_ov5640_top.sbit).Length; "
 f"(Get-FileHash {RDIR}/hdmi_ddr_ov5640_top.sbit -Algorithm MD5).Hash\"")

sid = ensure_init()
_, body = post({"jsonrpc": "2.0", "id": 210, "method": "tools/call",
                "params": {"name": "peer_call", "arguments": {
                    "peer": PEER, "tool": "oc_shell", "arguments": {"command": cmd}}}},
               sid, timeout=300)
print(parse_body(body))
print('expect md5: 783da66260fc0241fc9b9d663660805a (local, lowercase)')
