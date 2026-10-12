# -*- coding: utf-8 -*-
"""stop_remote.py -- 通知对方 opencode 停止过时的 50K 构建"""
import sys, json, urllib.request, os

URL = 'http://127.0.0.1:7777/mcp'
TOK = 'Bearer DSW52m3AksDiXULMielVdnDxMIcI2VjhX1pqz-5dz_Q'
SID_FILE = os.path.join(os.environ.get('TEMP', '.'), 'lan_mcp_session.txt')

def post(payload, sid=None, timeout=60):
    req = urllib.request.Request(URL, data=json.dumps(payload).encode('utf-8'), method='POST')
    req.add_header('Content-Type', 'application/json')
    req.add_header('Accept', 'application/json, text/event-stream')
    req.add_header('Authorization', TOK)
    if sid: req.add_header('mcp-session-id', sid)
    r = urllib.request.urlopen(req, timeout=timeout)
    return r.headers.get('mcp-session-id'), r.read().decode('utf-8', errors='replace')

def get_sid():
    try: return open(SID_FILE).read().strip()
    except Exception: return None

sid = get_sid()
if not sid:
    sid, _ = post({"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"z","version":"1"}}})
    open(SID_FILE,'w').write(sid)
    post({"jsonrpc":"2.0","method":"notifications/initialized"}, sid)

prompt = (
"【任务变更:50K 工程已转移到另一台电脑, 请停止本机所有 50K 构建活动】\n\n"
"背景: 50K 工程目录已整体转移到另一台机器并在那边做了进一步精简改造(注释 DDR3+HDMI 显示链, "
"SFP 直连 cam2_merge)。你机器上 D 盘的 21_OV5640_SFP480p_test 代码和正在跑的 pds 构建已经过时。\n\n"
"请立即:\n"
"1. 停止/终止正在运行的 pds.exe / pds_shell.exe(如果还在跑)\n"
"2. 不要再启动新的构建\n"
"3. 回复确认已停止即可, 不需要其他操作\n\n"
"感谢配合, Rev3.1 恢复+LED 面板+TX 修复的工作你完成得很干净, 这些都已带到新机器。")

_, body = post({"jsonrpc":"2.0","id":200,"method":"tools/call","params":{"name":"peer_call","arguments":{"peer":"opencode-lan-mcp@LAPTOP-AJQHFMKI","tool":"oc_prompt","arguments":{"prompt": prompt, "session_id": "ses_f14c01f66ffeUpyQTskjjcFViV"}}}}, sid)
print(body[:400])
