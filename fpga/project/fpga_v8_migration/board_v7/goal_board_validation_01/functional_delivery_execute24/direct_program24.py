"""Round 4: FPGA was power-cycled. Reburn the genbit sbit, then run the FPGA
NPU (YOLO accelerator) performance/health test on the board.

The NPU test measures: register liveness (0x5000_0000 layer count, 0x4000_0000
instruction queue window), the host->DDR bulk upload path (0x0200_0000 weights /
0x0600_0000 input frame / 0x0B_000000 loopback) which historically failed with
no MSI completion, and a register-level NPU probe. Real timestamps and timeouts
are recorded; nothing is claimed beyond what the hardware returns.
"""
import importlib.util
import json
import sys
import traceback
from pathlib import Path
from types import SimpleNamespace

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
GOAL = HERE.parent
BUILD = GOAL.parent / 'build04_functional_route04'

spec = importlib.util.spec_from_file_location(
    'preserved11_for_direct24', GOAL/'functional_delivery_execute10/runner_corrected11.py')
pres = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pres)
r = pres.r
r.HERE = HERE

NPU_TEST = r'''
import ctypes, fcntl, json, mmap, os, signal, struct, time

def _al(s, f):
    raise TimeoutError('dma alarm')
signal.signal(signal.SIGALRM, _al)

class O(ctypes.Structure):
    _fields_ = [('cur', ctypes.c_uint32), ('off', ctypes.c_uint32), ('cmd', ctypes.c_uint32),
                ('ddr', ctypes.c_uint32), ('ln', ctypes.c_uint32),
                ('rb', ctypes.c_void_p), ('wb', ctypes.c_void_p)]

def I(n):
    return 0xC0000000 | (4 << 16) | (0x53 << 8) | n

FD = os.open('/dev/pango_pci_driver', os.O_RDWR | os.O_SYNC)
for c in (0, 1):
    o = O(); o.cmd = c; o.ln = 4194304
    signal.alarm(8); fcntl.ioctl(FD, I(2), o, True); signal.alarm(0)
RX = mmap.mmap(FD, 4194304, prot=mmap.PROT_READ | mmap.PROT_WRITE, flags=mmap.MAP_SHARED, offset=1048576)
TX = mmap.mmap(FD, 4194304, prot=mmap.PROT_READ | mmap.PROT_WRITE, flags=mmap.MAP_SHARED, offset=0)

def rd(a):
    t0 = time.time()
    try:
        signal.alarm(8)
        try:
            fcntl.ioctl(FD, I(5), o2(a), True)
        finally:
            signal.alarm(0)
        v = struct.unpack('<I', RX[0:4])[0]
        return dict(ok=True, value=v, ms=round((time.time()-t0)*1000, 3))
    except Exception as e:
        return dict(ok=False, error=repr(e), ms=round((time.time()-t0)*1000, 3))

def wr(a, v):
    t0 = time.time()
    TX[0:4] = struct.pack('<I', v)
    try:
        signal.alarm(8)
        try:
            fcntl.ioctl(FD, I(4), o2(a), True)
        finally:
            signal.alarm(0)
        return dict(ok=True, ms=round((time.time()-t0)*1000, 3))
    except Exception as e:
        return dict(ok=False, error=repr(e), ms=round((time.time()-t0)*1000, 3))

def o2(a):
    o = O(); o.off = 0; o.ddr = a; o.ln = 16
    return o

out = {}
# 1. NPU register liveness (M02 window)
out['npu_regs'] = {}
for a in [0x40000000, 0x40000004, 0x50000000, 0x50000004]:
    out['npu_regs']['0x%08X' % a] = rd(a)
# 2. Motion snapshot window (bonus evidence)
out['motion'] = {}
for a in [0x20000800, 0x20000804]:
    out['motion']['0x%08X' % a] = rd(a)
# 3. Host->DDR bulk write path (weights / input frame / loopback regions)
out['ddr_write'] = {}
for a, marker in [(0x02000000, 0xA5A50001), (0x06000000, 0xA5A50002), (0x0B000000, 0xA5A50003)]:
    key = '0x%08X' % a
    w = wr(a, marker)
    rec = dict(write=w)
    if w['ok']:
        rec['readback'] = rd(a)
        rec['match'] = rec['readback'].get('ok') and rec['readback'].get('value') == marker
    out['ddr_write'][key] = rec
# 4. Register write readback sanity (PREP window is known-good 16B ops)
out['reg_write'] = {}
w = wr(0x20000100, 0)
out['reg_write']['0x20000100'] = dict(write=w, readback=rd(0x20000100))
print('NPU_TEST_RESULT ' + json.dumps(out))
'''

r.remote_src_npu = NPU_TEST


def wait_controller():
    assert (r.BUILD/'functional_candidate01/generate_bitstream/v7_sdt_top.sbit').is_file()
    r.save('controller_wait.json', {'utc': r.c.utc(), 'direct_program_mode': True, 'round': 4, 'npu_test': True})


r.wait_controller = wait_controller


def main():
    assert not (HERE/'direct_program24_started.json').exists(), 'Never repeat direct program24'
    sbit = r.BUILD/'functional_candidate01/generate_bitstream/v7_sdt_top.sbit'
    assert sbit.is_file()
    digest = r.c.sha(sbit)
    receipt = json.loads((r.BUILD/'functional_genbit_receipt.json').read_bytes())
    assert receipt['rc'] == 0 and not receipt['errors']
    assert receipt['log_sha256'] == r.c.sha(r.BUILD/'functional_genbit.log')
    bit = dict(path=str(sbit), sha256=digest, size=sbit.stat().st_size)
    r.save('direct_program24_binding.json', dict(
        status='DIRECT_PROGRAM_AUTHORIZED_ROUND4_NPU_TEST',
        user_instruction='fpga断电了刚才 重烧 直接测npu性能', bit=bit,
        genbit_receipt_sha256=r.c.sha(r.BUILD/'functional_genbit_receipt.json'),
        flash_modified=False, program=True))
    print(r.c.utc(), 'Round4 NPU-test binding recorded', digest, flush=True)
    k, h = r.c.tool_lease(HERE)
    try:
        r.vendor.idle()
        r.reboot()
        r.snapshot('before_sram')
        directory = HERE/'sram_program'
        directory.mkdir()
        breceipt = {'status': 'blocked', 'target': 'PG2L100H', 'mode': 'sram', 'round': 4,
                    'bit': bit['path'], 'bit_sha256': digest, 'stages': {}, 'stage_errors': [],
                    'boot_id': r.BOOT,
                    'handoff_sha256': r.c.sha(HERE/'direct_program24_binding.json'),
                    'started_utc': r.c.utc()}
        try:
            r.vendor.run(SimpleNamespace(mode='sram', timeout=300), breceipt, directory, sbit, digest)
        finally:
            breceipt['ended_utc'] = r.c.utc()
            r.c.save(directory/'receipt.json', breceipt)
        assert breceipt['status'] == 'success' and all(breceipt['stages'].values())
        r.link_driver()
        raw = r.remote('npu_test', NPU_TEST)
        text = raw.decode('utf-8', 'replace') if isinstance(raw, (bytes, bytearray)) else str(raw)
        line = [l for l in text.splitlines() if l.startswith('NPU_TEST_RESULT ')]
        assert line, 'NPU test produced no result line: ' + text[-500:]
        result = json.loads(line[-1][len('NPU_TEST_RESULT '):])
        r.save('npu_test_result.json', result)
        print(r.c.utc(), 'NPU test recorded', json.dumps(result)[:600], flush=True)
        r.save('RESULT.json', {
            'status': 'DIRECT24_SRAM_PROGRAMMED_NPU_TESTED',
            'utc': r.c.utc(), 'boot_id': r.BOOT,
            'bit': bit['path'], 'bit_sha256': digest,
            'vendor_receipt': str(directory/'receipt.json'),
            'vendor_receipt_sha256': r.c.sha(directory/'receipt.json'),
            'npu_test_sha256': r.c.sha(HERE/'npu_test_result.json'),
            'goal_complete': False, 'functional_pass': False,
            'flash_modified': False})
    finally:
        k.ReleaseMutex(h)
        k.CloseHandle(h)


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        if r.BOOT:
            try:
                r.ledger_mode('failure_admission_rehold', 0o644)
            except Exception as cleanup:
                r.save('failure_admission_rehold_error.json', {'error': repr(cleanup)})
        r.save('FAIL.json', {'utc': r.c.utc(), 'error': repr(error),
                             'traceback': traceback.format_exc(),
                             'goal_complete': False, 'functional_pass': False,
                             'old_bit_fallback': False, 'flash_modified': False})
        traceback.print_exc()
        sys.exit(1)
