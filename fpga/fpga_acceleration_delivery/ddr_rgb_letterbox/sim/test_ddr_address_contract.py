"""Native HMIC word-address model; reproduce the hardware padding signature."""
from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from run_tests import oracle


def store(payload, beats):
    memory = bytearray([0xA5]) * (len(payload) * 2 + 512)
    for offset in range(0, len(payload), beats * 16):
        # Bus base addresses advance in the deployed nominal-byte units;
        # IP interprets each base as a 16-bit DDR word address.
        block = payload[offset:offset + beats * 16]
        memory[offset * 2:offset * 2 + len(block)] = block
    return memory


def host_read(memory, size):
    result = bytearray()
    for offset in range(0, size, 256):
        count = min(256, size - offset)
        result.extend(memory[offset * 2:offset * 2 + count])
    return result


def main():
    repo = ROOT.parents[1]
    wr = (repo / 'ipcore/ddr3/example_design/rtl/test_wr_ctrl_v1_0.v').read_bytes()
    rd = (repo / 'ipcore/ddr3/example_design/rtl/test_rd_ctrl_v1_0.v').read_bytes()
    top = (ROOT / 'integrated/source/top.v').read_bytes()  # GBK: byte inspection
    assert b'normal_wr_addr <= normal_wr_addr + 8;' in wr
    assert b'normal_rd_addr <= normal_rd_addr + 8;' in rd
    assert b'axi_awaddr <= axi_awaddr + 8\'d128;' in wr
    assert b'ddr3_aw_addr <= ddr_axi_awaddr[27:0];' in top
    assert b'ddr3_ar_addr <= ddr_axi_araddr[27:0];' in top
    padding = bytes([114]) * 153600
    old = host_read(store(padding, 1), len(padding))
    expected_written = [i % 2 == 0 for i in range(len(padding) // 16)]
    assert [old[i:i+16] == bytes([114])*16 for i in range(0, len(old), 16)] == expected_written
    capture = repo / 'v8_acceleration_compare/hardware_mismatch/mismatch.fpga.rgb'
    if capture.exists():
        observed = capture.read_bytes()[:len(padding)]
        assert len(observed) == len(padding)
        assert [observed[i:i+16] == bytes([114])*16 for i in range(0, len(observed), 16)] == expected_written
    for frame in range(2):
        payload = oracle(640, 480, 640, 80, frame)
        assert host_read(store(payload, 16), len(payload)) == payload
    report = {'native_address_unit_bytes': 2, 'physical_beat_bytes': 16,
              'deployed_bus_burst_stride': 256, 'burst_beats': 16,
              'old_singlebeat_signature_reproduced_blocks': 9600,
              'hardware_capture_signature_checked': capture.exists(),
              'new_burst16_full_frames_byte_exact': 2}
    (ROOT / 'artifacts/address_contract.json').write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
