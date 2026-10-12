"""Extract the actual PangoDev acquisition code for a syscall-contract test.

No production replacements: only this local test executable wraps device calls.
"""
from pathlib import Path
root = Path(__file__).resolve().parent
source = (root / "main.cpp").read_text(encoding="utf-8-sig")
def section(start, end):
    return source[source.index(start):source.index(end)]
prefix = r'''
#include <QMutex>
#include <QElapsedTimer>
#include <QThread>
#include <algorithm>
#include <atomic>
#include <cerrno>
#include <csignal>
#include <cstring>
#include <cstddef>
#include <cstdio>
#include <memory>
#include <fcntl.h>
#include <sys/ioctl.h>
#include <sys/mman.h>
#include <sys/syscall.h>
#include <unistd.h>
#include "camera_dma.h"
#include "fpga_infer_input.h"
#include "scheme2_uapi.h"
#include "scheme2_verify.h"
'''
result = prefix
result += section('[[noreturn]] static void scheme2Quarantine', '#include <rga/im2d.h>')
result += section('static const int IMG_W', '/* ---------------- dma-heap')
result += section('struct DmaOp {', 'struct ModelInfo {')
result += section('class PangoDev {', '/* ---------------- 四路采集')
result += '\n#include "scheme2_protocol_test_body.h"\n'
(root / 'local_build').mkdir(exist_ok=True)
(root / 'local_build' / 'protocol.cpp').write_text(result, encoding='utf-8')
print('Generated protocol unit from actual candidate PangoDev code')
