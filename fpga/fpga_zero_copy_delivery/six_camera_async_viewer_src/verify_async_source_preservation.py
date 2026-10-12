"""Verify the immutable copy baseline and safety-critical byte preservation."""
import hashlib
import json
from pathlib import Path

root = Path(__file__).resolve().parent
baseline = root.parent / 'six_camera_batch_viewer_src'
hashes = json.loads((root / 'async_baseline_hashes.json').read_text())
allowed = {'main.cpp', 'detview.pro', 'six_dma_layout.h',
           'thumbnail_delivery_selftest.cpp', 'six_batch_transport_selftest.cpp'}
changed = []
for name, expected in hashes.items():
    before = (baseline / name).read_bytes()
    assert hashlib.sha256(before).hexdigest() == expected, ('baseline changed', name)
    if (root / name).read_bytes() != before:
        assert name in allowed, ('unexpected copied-file change', name)
        changed.append(name)

before = (baseline / 'main.cpp').read_bytes()
after = (root / 'main.cpp').read_bytes()
def section(data, start, end):
    begin = data.index(start)
    return data[begin:data.index(end, begin)]

checks = {}
for label, start, end in [
    ('camera_worker_and_raw_detection_flow', b'class CameraWorker', b'class InferenceThread'),
    ('inference_thread', b'class InferenceThread', b'class DetView :'),
    ('raw_transfer_guards_and_copy', b'        uint32_t a = 0, b = 0;', b'    // '),
    ('dma_range_timeout_quarantine', b'    int ioctlTmo(', b'    void close()'),
]:
    checks[label] = section(before, start, end) == section(after, start, end)
checks['reader_entire_byte_exact'] = (root / 'thumbnail_delivery.h').read_bytes() == (baseline / 'thumbnail_delivery.h').read_bytes()
start = b'        bool readSnapshot('
end = b'        bool write('
method = section(after, start, end)
test = (root / 'six_batch_transport_selftest.cpp').read_bytes()
checks['snapshot_test_exact_production_method'] = method in test
checks['one_device_open'] = after.count(b'::open("/dev/pango_pci_driver"') == 1
transport = section(after, b'    struct ThumbnailTransport {', b'    bool cameraTagLocked(')
checks['transport_dma_guards_all_five_operations'] = transport.count(b'auto lock = dev.endpointLocks_.dma();') == 5
checks['borrow_callback_lock_order'] = b'auto locks = endpointLocks_.borrow();' in section(after, b'    template<class Callback>', b'    bool regWrite(')
checks['raw_no_lease_acquisition'] = b'endpointLocks_.lease()' not in section(after, b'    int cameraRead(', b'    int thumbnailRead(')
checks['thumbnail_keeps_lease_through_reader'] = b'auto lock = endpointLocks_.lease();' in section(after, b'    int thumbnailRead(', b'    const char *lastErr()')
assert all(checks.values()), checks
report = {'baseline_files_unchanged': len(hashes), 'changed_candidate_files': changed,
          'critical_sections': checks,
          'note': 'Immutable baseline hash snapshot includes all copied files; no device access.'}
(root / 'async_source_preservation.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report, indent=2))
