# -*- coding: utf-8 -*-
"""mcp_call.py -- lan-opencode MCP 客户端 (HTTP JSON-RPC)
用法: python mcp_call.py <tool> [json参数]"""
import sys, os, json, urllib.request

URL = 'http://127.0.0.1:7777/mcp'
TOK = 'Bearer DSW52m3AksDiXULMielVdnDxMIcI2VjhX1pqz-5dz_Q'
SID_FILE = os.path.join(os.environ.get('TEMP', '.'), 'lan_mcp_session.txt')


def post(payload, sid=None, timeout=180):
    req = urllib.request.Request(URL, data=json.dumps(payload).encode('utf-8'), method='POST')
    req.add_header('Content-Type', 'application/json')
    req.add_header('Accept', 'application/json, text/event-stream')
    req.add_header('Authorization', TOK)
    if sid:
        req.add_header('mcp-session-id', sid)
    r = urllib.request.urlopen(req, timeout=timeout)
    return r.headers.get('mcp-session-id'), r.read().decode('utf-8', errors='replace')


def get_sid():
    try:
        return open(SID_FILE).read().strip()
    except Exception:
        return None


def ensure_init():
    sid = get_sid()
    if sid:
        return sid
    sid, body = post({"jsonrpc": "2.0", "id": 1, "method": "initialize",
                      "params": {"protocolVersion": "2024-11-05", "capabilities": {},
                                 "clientInfo": {"name": "zcode-bridge", "version": "1.0"}}})
    if sid:
        open(SID_FILE, 'w').write(sid)
        post({"jsonrpc": "2.0", "method": "notifications/initialized"}, sid)
    return sid


def parse_body(body):
    if body.startswith('{'):
        obj = json.loads(body)
    else:
        obj = None
        for ln in body.splitlines():
            if ln.startswith('data:'):
                try:
                    obj = json.loads(ln[5:].strip()); break
                except Exception:
                    pass
    if obj is None:
        return body[:4000]
    res = obj.get('result', obj)
    if 'content' in res:
        return '\n'.join(c.get('text', json.dumps(c, ensure_ascii=False)[:300]) for c in res['content'])
    return json.dumps(res, ensure_ascii=False)[:4000]


if __name__ == '__main__':
    tool = sys.argv[1]
    args = json.loads(sys.argv[2]) if len(sys.argv) > 2 else {}
    sid = ensure_init()
    sid2, body = post({"jsonrpc": "2.0", "id": 99, "method": "tools/call",
                       "params": {"name": tool, "arguments": args}}, sid, timeout=600)
    if sid2 and sid2 != sid:
        open(SID_FILE, 'w').write(sid2)
    print(parse_body(body))
