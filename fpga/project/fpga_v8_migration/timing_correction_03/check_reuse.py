"""Check exact inherited-script anchors without running PDS or editing evidence."""
from run_whole import M


def main():
    directory = M / 'timing_correction_02'
    anchors = {
        'export_whole.py': [
            b"'block_motion_detector_tc01','ovreg_axil_decode_tc01'",
            b"'fpga_v8_pcie_fifo_h2f_rfg01'}&elaborated",
            b"BASE/'evidence_02/stage_tables.json'",
            b"previous['place_route']['tables']['pnr_io_report']['rows']",
        ],
        'generate_bitstream.py': [b'tests=Path(__file__).resolve().parent'],
        'verify_delivery.py': [b'# FPGA cooperative V4 bitstream'],
        'audit_acceptance.py': [b"BASE / 'evidence_02/stage_tables.json'",
                               b"baseline['place_route']['tables']['pnr_io_report']['rows']"],
    }
    for name, keys in anchors.items():
        data = (directory / name).read_bytes()
        for key in keys:
            assert data.count(key) == 1, (name, key)
    print('PASS exact inherited exporter/generator/verifier/auditor anchors', flush=True)


if __name__ == '__main__':
    main()
