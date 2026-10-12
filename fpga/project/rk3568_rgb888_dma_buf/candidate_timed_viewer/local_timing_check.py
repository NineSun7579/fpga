"""Native syscall fixtures for the actual PangoDev telemetry; no board access."""
from pathlib import Path
import os
import re
import subprocess
import sys

root = Path(__file__).resolve().parent
build = root / 'local_build'
subprocess.run([sys.executable, str(root / 'local_protocol_check.py')], check=True)
source = (build / 'protocol.cpp').read_text()
# Count only telemetry clock calls, leaving the existing DMA/deadline timers intact.
counter = '''
struct TimingClockProbe {
    static inline int starts = 0, reads = 0, monotonicChecks = 0;
    QElapsedTimer timer;
    static bool isMonotonic() { ++monotonicChecks; return QElapsedTimer::isMonotonic(); }
    void start() { ++starts; timer.start(); }
    qint64 nsecsElapsed() { ++reads; return timer.nsecsElapsed(); }
};
'''
source = source.replace('class PangoDev {', counter + '\nclass PangoDev {', 1)
begin = source.index('    struct FpgaReadTiming {')
end = source.index('    bool failOpen()', begin)
instrumented = source[begin:end].replace('QElapsedTimer::', 'TimingClockProbe::').replace(
    'QElapsedTimer clock;', 'TimingClockProbe clock;')
source = source[:begin] + instrumented + source[end:]
fixture = (root / 'scheme2_protocol_test_body.h').read_text()
fixture = fixture.replace('bool held = false;', '''bool held = false;
uint64_t protocolHash = 1469598103934665603ULL;
void trace(uint64_t value) { protocolHash = (protocolHash ^ value) * 1099511628211ULL; }
''')
fixture = fixture.replace('auto* op = static_cast<DmaOp*>(data);', '''auto* op = static_cast<DmaOp*>(data);
    // Poll count depends on thread scheduling; compare every other DMA command.
    if (!(command == F2H_CMD && op->ddr3_addr == Base + 0x10)) {
        trace(command); trace(op->cmd); trace(op->ddr3_addr);
        trace(op->offset_addr); trace(op->total_length);
        if (command == H2F_CMD) { uint32_t value; memcpy(&value, tx.data(), 4); trace(value); }
    }''', 1)
fixture = fixture.replace('    std::puts("scheme2 actual PangoDev mode0', '''    const bool timing = qgetenv("DETVIEW_FPGA_INFER_TIMING") == "1";
    assert(TimingClockProbe::starts == (timing ? 14 : 0));
    assert(TimingClockProbe::reads == (timing ? 132 : 0));
    assert(TimingClockProbe::monotonicChecks == (timing ? 1 : 0));
    printf("TIMING_CLOCK starts=%d reads=%d monotonic_checks=%d protocol_hash=%llu\\n",
        TimingClockProbe::starts, TimingClockProbe::reads, TimingClockProbe::monotonicChecks,
        static_cast<unsigned long long>(protocolHash));
    std::puts("scheme2 actual PangoDev mode0''', 1)
source = source.replace('#include "scheme2_protocol_test_body.h"', fixture)
unit = build / 'timing_protocol.cpp'
unit.write_text(source)
qt = subprocess.check_output(['pkg-config', '--cflags', '--libs', 'Qt5Core', 'Qt5Gui'], text=True).split()
binary = build / 'timing_protocol_test'
subprocess.run(['g++', '-std=c++17', '-O2', '-fPIC', '-pthread', '-I' + str(root),
                str(unit), '-o', str(binary), *qt,
                '-Wl,--wrap=open,--wrap=close,--wrap=raise,--wrap=mmap,--wrap=munmap,--wrap=ioctl'], check=True)
phases = ['acquisition_ns', 'hold_command_issue_ns', 'hold_validated_ns', 'raw_f2h_tag_ns',
          'converter_start_ns', 'converter_done_ns', 'release_verified_ns', 'raw_cpu_copy_ns',
          'publish_ready_ns', 'total_read_ns']
hashes = {}
for name, timing, verify in [('off', None, False), ('zero', '0', False), ('invalid', 'true', False),
                              ('on', '1', False), ('verify_off', None, True), ('verify_on', '1', True)]:
    env = dict(os.environ)
    env['DETVIEW_FPGA_INFER_RGB'] = '1'
    env.pop('DETVIEW_FPGA_INFER_TIMING', None)
    env.pop('DETVIEW_FPGA_INFER_VERIFY', None)
    if timing is not None:
        env['DETVIEW_FPGA_INFER_TIMING'] = timing
    if verify:
        env['DETVIEW_FPGA_INFER_VERIFY'] = '1'
    run = subprocess.run([str(binary)], env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    (build / ('timing_' + name + '.log')).write_text(run.stdout)
    assert run.returncode == 0, (name, run.stdout)
    lines = [line for line in run.stdout.splitlines() if '[fpga-infer-timing]' in line]
    assert len(lines) == (13 if timing == '1' else 0), (name, lines)
    for line in lines:
        assert 'clock=QElapsedTimer_monotonic' in line
        fields = {key: int(value) for key, value in re.findall(r'(\w+)=([0-9]+)', line)}
        offsets = [fields[key] for key in phases]
        assert offsets[0] >= 0 and offsets == sorted(offsets), line
        hold = fields['hold_command_to_release_ack_wall_ns']
        assert hold == fields['release_verified_ns'] - fields['hold_command_issue_ns'], line
        assert 0 < hold <= fields['total_read_ns'], line
        # Fixture deliberately waits for disjoint metadata service during hold.
        if fields['generation'] == 7:
            assert fields['hold_validated_ns'] - fields['hold_command_issue_ns'] >= 1_000_000, line
        assert fields['total_read_ns'] < 3_000_000_000, line
    hashes[name] = re.search(r'protocol_hash=(\d+)', run.stdout).group(1)
    print(name + ': PASS clocks, log gating, phase ordering/bounds, actual lease/copy protocol')
assert len(set(hashes.values())) == 1, hashes
print('TIMING_NATIVE_PASS identical non-poll DMA command trace for OFF/ON and verification; 6 cameras, 480/640')
