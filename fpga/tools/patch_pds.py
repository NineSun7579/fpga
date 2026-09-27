# -*- coding: utf-8 -*-
"""patch_pds.py -- register the new KF source files in a project.pds copy.
Usage: python tools/patch_pds.py <path-to-project.pds>
"""
import sys

PDS = sys.argv[1]


def patch(old, new):
    d = open(PDS, "rb").read()
    O = old.encode("ascii")
    N = new.encode("ascii")
    if N in d:
        print("SKIP (already) :: %s" % new[:52])
        return
    c = d.count(O)
    assert c == 1, "count=%d for %s" % (c, old[:60])
    open(PDS, "wb").write(d.replace(O, N, 1))
    print("ok :: %s" % new[:52])


ENTRY = lambda path, ts: (
    '                (_file "%s"\r\n'
    '                    (_format verilog)\r\n'
    '                    (_timespec "%s")\r\n'
    '                )' % (path, ts)
)

# axi_dma_read.v after stream_pipe.v
patch('                (_file "../source/axi_dma/stream_pipe.v"\r\n'
      '                    (_format verilog)\r\n'
      '                    (_timespec "2026-08-20T06:06:50")\r\n'
      '                )',
      '                (_file "../source/axi_dma/stream_pipe.v"\r\n'
      '                    (_format verilog)\r\n'
      '                    (_timespec "2026-08-20T06:06:50")\r\n'
      '                )\r\n' +
      ENTRY("../source/axi_dma/axi_dma_read.v", "2026-09-25T02:00:00"))

# vip_kf.v + vip_kf_stream.v after vip.v
patch('                (_file "../source/ov5640/vip.v"\r\n'
      '                    (_format verilog)\r\n'
      '                    (_timespec "2026-09-21T10:38:54")\r\n'
      '                )',
      '                (_file "../source/ov5640/vip.v"\r\n'
      '                    (_format verilog)\r\n'
      '                    (_timespec "2026-09-21T10:38:54")\r\n'
      '                )\r\n' +
      ENTRY("../source/ov5640/vip_kf.v", "2026-09-25T02:00:00") + "\r\n" +
      ENTRY("../source/ov5640/vip_kf_stream.v", "2026-09-25T02:00:00"))

print("PDS REGISTERED")
