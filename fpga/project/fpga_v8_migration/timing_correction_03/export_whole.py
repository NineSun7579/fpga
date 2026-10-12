"""Reuse the audited V4 exporter with explicit V5 binding and pin baseline."""
from pathlib import Path
import hashlib
from run_whole import M


def main():
    from audit_binding import main as audit_binding
    audit_binding()
    original = M / 'timing_correction_02/export_whole.py'
    source = original.read_bytes()
    edits = [
        (b"'block_motion_detector_tc01','ovreg_axil_decode_tc01'",
         b"'block_motion_detector_tc03','ovreg_axil_decode_tc01','ov5640_cdc_tc03','fpga_v8_ddr_adapter_tc03'"),
        (b"'fpga_v8_pcie_fifo_h2f_rfg01'}&elaborated",
         b"'fpga_v8_pcie_fifo_h2f_rfg01','block_motion_detector_tc01','ov5640_cdc','fpga_v8_ddr_adapter'}&elaborated"),
        (b"BASE/'evidence_02/stage_tables.json'", b"BASE/'evidence/stage_tables.json'"),
        (b"previous['place_route']['tables']['pnr_io_report']['rows']",
         b"previous['place_route']['pnr_io_report']['rows']"),
    ]
    for old, new in edits:
        assert source.count(old) == 1, old
        source = source.replace(old, new)
    from run_whole import save
    save('exporter_reuse.json', {'source': str(original),
         'source_sha256': hashlib.sha256(original.read_bytes()).hexdigest(),
         'executed_sha256': hashlib.sha256(source).hexdigest(),
         'changes': [old.decode() for old, new in edits], 'programming_performed': False})
    scope = {'__name__': 'v5_exporter', '__file__': str(original)}
    exec(compile(source, str(original), 'exec'), scope)
    scope['main']()


if __name__ == '__main__':
    main()
