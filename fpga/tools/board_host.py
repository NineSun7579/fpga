"""board_host.py -- resolve the RK3568 board IP for all ov56401 host tools.

Resolution order:
    1. $OV5640_BOARD_HOST           (explicit override)
    2. tools/board_host.txt         (checked-in lease value)
    3. built-in default

The board's wired iface (end1) is DHCP, so the lease can change after a reboot.
Update tools/board_host.txt (or export OV5640_BOARD_HOST) instead of editing
every tool.
"""
import os
from pathlib import Path

_DEFAULT = '192.168.10.203'
_CFG = Path(__file__).resolve().parent / 'board_host.txt'


def board_host():
    h = (os.environ.get('OV5640_BOARD_HOST') or '').strip()
    if h:
        return h
    try:
        t = _CFG.read_text(encoding='utf-8').strip()
    except OSError:
        t = ''
    return t or _DEFAULT


def ssh_connect(**kw):
    """Connect to the board over SSH, returning a live paramiko client."""
    import paramiko
    cli = paramiko.SSHClient()
    cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    kw.setdefault('username', 'linaro')
    kw.setdefault('password', '123456')
    kw.setdefault('allow_agent', False)
    kw.setdefault('look_for_keys', False)
    kw.setdefault('timeout', 15)
    cli.connect(board_host(), **kw)
    return cli
