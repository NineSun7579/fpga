"""Strict offline boardValidation/v2; no board or programmer operations.

Hashes bind supplied files, not acquisition authenticity. Visual/integrity and
diagnostic source reviews remain human. v1 is outside final acceptance.
"""
import argparse
import ast
from datetime import datetime
import json
import math
from pathlib import Path
import re
import struct
import sys
from new_program_candidate import bound, load, require, sha, VENDOR


def utc(value):
    dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
    require(dt.tzinfo is not None, 'Timezone required for timestamp')
    return dt.timestamp()


def number(value):
    require(type(value) in (int, float) and math.isfinite(value), 'Invalid numeric timestamp')
    return value


def vendor_parser():
    # Execute only actual pure parser/constants; never import device code.
    tree = ast.parse(VENDOR.read_text(encoding='utf-8-sig'))
    nodes = [n for n in tree.body if
             (isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and
              t.id in ('TARGET', 'ERROR') for t in n.targets)) or
             (isinstance(n, ast.FunctionDef) and n.name == 'parse_log')]
    scope = {'re': re}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(VENDOR), 'exec'), scope)
    return scope['parse_log'], scope['ERROR']


def program_gate(doc, files):
    receipt, delivery, pre = (load(files[k]) for k in ('program_receipt', 'delivery', 'owner_preflight'))
    require(receipt.get('status') == 'success' and receipt.get('mode') == 'sram' and
            receipt.get('target') == 'PG2L100H' and receipt.get('check_only') is False,
            'Actual successful SRAM receipt required')
    require(delivery.get('contract') == 'validatedDelivery/v1' and delivery.get('status') == 'validated' and
            receipt.get('bit_sha256') == doc['bit_sha256'] == delivery['bitstream']['sha256'] and
            receipt.get('bit_bytes') == delivery['bitstream']['bytes'] and
            receipt.get('candidate_id') == delivery['candidate_id'] and
            receipt.get('delivery_manifest_sha256') == sha(files['delivery']) and
            receipt.get('owner_preflight_sha256') == sha(files['owner_preflight']) and
            receipt.get('programmer_sha256') == sha(VENDOR), 'Receipt/delivery/preflight binding mismatch')
    require(pre.get('accepted') is True and pre.get('contract') == 'boardOwnerPreflight/v1' and pre.get('reviewer') and
            pre.get('bit_sha256') == doc['bit_sha256'] and pre.get('delivery_manifest_sha256') == sha(files['delivery']),
            'Accepted owner preflight required')
    require({str(files[k].resolve()) for k in ('cfg_log', 'server_log', 'client_log')} ==
            {str(Path(p).resolve()) for p in receipt['logs']}, 'Receipt log paths mismatch')
    parse, error = vendor_parser()
    stages, errors = parse(files['cfg_log'].read_bytes().decode('gb18030').replace('\r\n', '\n'), 'sram')
    require(not errors and stages == receipt.get('stages') and all(stages.values()) and not receipt.get('stage_errors'),
            'Raw cfg stages do not prove receipt success')
    for k in ('server_log', 'client_log'):
        require(not error.search(files[k].read_bytes().decode('gb18030')), 'Programmer log error: ' + k)
    return program_time_gate(load(files['program_session']), receipt, pre, files)


def program_time_gate(session, receipt, pre, files):
    require(session.get('contract') == 'programSession/v1' and session.get('collector') and
            session.get('receipt_sha256') == sha(files['program_receipt']) and
            session.get('delivery_manifest_sha256') == sha(files['delivery']) and session.get('exit_code') == 0,
            'Actual program completion collection required')
    start, end = utc(session['started_utc']), utc(session['completed_utc'])
    require(start < end and 0 <= start - number(pre['captured_unix']) <= 300, 'Program/preflight chronology invalid')
    # Candidate lacks updated; legacy vendor uses local wall clock. No guessed timezone.
    if 'updated' in receipt:
        updated = utc(receipt['updated'].replace(' ', 'T') + session['receipt_timezone'])
        require(start <= updated <= end, 'Receipt timestamp outside program session')
    transcript = files['program_session_raw'].read_text(encoding='utf-8-sig').splitlines()
    for key in ('started_utc', 'completed_utc', 'receipt_sha256', 'delivery_manifest_sha256', 'exit_code'):
        require(f'{key}={session[key]}' in transcript, 'Program raw timestamp/hash missing: ' + key)
    return end


def identity_gate(snapshot, expected, program_end):
    require(snapshot.get('contract') == 'viewerProcSnapshot/v1', 'Actual /proc snapshot required')
    captured = utc(snapshot['captured_utc'])
    require(snapshot['board_id'] == expected['board_id'] and snapshot['host'] == expected['host'] and
            snapshot['boot_id'] == expected['boot_id'], 'Board/host/boot identity mismatch')
    require(type(snapshot['pid']) is int and snapshot['pid'] > 0 and snapshot['exe'] == expected['exe'] and
            snapshot['exe_sha256'] == expected['exe_sha256'], 'Viewer executable identity mismatch')
    argv = bytes.fromhex(snapshot['cmdline_hex']).rstrip(b'\0').split(b'\0')
    require([a.decode('utf-8') for a in argv] == expected['argv'], 'Actual viewer argv mismatch')
    raw = snapshot['proc_stat']
    require(int(raw.split(' ', 1)[0]) == snapshot['pid'], 'Raw /proc PID mismatch')
    fields = raw.rsplit(')', 1)[1].split()
    ticks = int(fields[19])  # suffix field 3 -> actual field 22
    require(snapshot['clk_tck'] > 0 and ticks > 0, 'Invalid process start ticks')
    start = number(snapshot['boot_unix']) + ticks / snapshot['clk_tck']
    require(program_end < start <= captured, 'Viewer start must be after actual programming')
    require(snapshot['models'] == expected['models'] and expected['models'], 'Actual model path/hash mismatch')
    require(all(re.fullmatch('[0-9a-f]{64}', v) for v in snapshot['models'].values()), 'Invalid model hash')
    return captured, start


def screenshot_gate(entry, files, expected, program_end, viewer_start):
    import numpy as np
    from PIL import Image
    png, xwd, metadata = (files[entry[k]] for k in ('png', 'xwd', 'metadata'))
    meta = load(metadata)
    captured = utc(meta['captured_utc'])
    require(program_end < viewer_start < captured, 'Screenshot predates program/viewer')
    require(meta['host'] == expected['host'] and meta['source'] == 'RK3568 X11 :0 root window',
            'Actual RK desktop metadata required')
    for key, path in (('png', png), ('xwd', xwd)):
        require(Path(meta[key]).name == path.name, 'Capture metadata filename mismatch')
    content = xwd.read_bytes()
    require(len(content) >= 100, 'Truncated XWD header')
    h = struct.unpack('>25I', content[:100])
    size, version, fmt, depth, width, height = h[:6]
    order, bpp, stride, colors = h[7], h[11], h[12], h[19]
    require(version == 7 and fmt == 2 and depth == 24 and bpp in (24, 32) and order in (0, 1) and
            size >= 100 and width > 0 and height > 0 and stride >= width * (bpp // 8),
            'Unsupported XWD geometry/depth/storage')
    require((width, height, depth) == (meta['width'], meta['height'], meta['depth']),
            'Metadata/XWD geometry or depth mismatch')
    require((width, height) == tuple(expected['screen_geometry']), 'Unexpected desktop geometry')
    data = content[size + colors * 12:]
    require(len(data) == height * stride, 'Incomplete XWD pixel storage')
    packed = np.frombuffer(data, dtype='u1').reshape(height, stride)
    packed = packed[:, :width * (bpp // 8)].reshape(height, width, bpp // 8).astype('uint32')
    shifts = range(0, bpp, 8) if order == 0 else range(bpp - 8, -1, -8)
    pixels = sum(packed[:, :, i] << shift for i, shift in enumerate(shifts))
    channels = []
    for mask in h[14:17]:
        require(mask != 0, 'Missing XWD TrueColor mask')
        shift = (mask & -mask).bit_length() - 1
        channels.append(((pixels & mask) >> shift) * 255 // (mask >> shift))
    converted = np.stack(channels, axis=-1).astype('uint8')
    with Image.open(png) as image:
        require(image.format == 'PNG' and image.size == (width, height) and image.mode == 'RGB' and
                np.array_equal(np.asarray(image), converted), 'PNG differs from original XWD conversion')
    return captured, {'width': width, 'height': height, 'color_depth': depth, 'storage_bpp': bpp,
                      'png_sha256': sha(png), 'xwd_sha256': sha(xwd), 'metadata_sha256': sha(metadata)}


CAPTURE = re.compile(r'^\[capture\] camera=([1-6]) delivered_fps=([0-9.]+) tag_advance_rate=([0-9.]+) '
                     r'read_ms=([0-9.]+) frame_dma_ms=([0-9.]+) copy_ms=([0-9.]+) unstable=(\d+)$')


def progress_gate(path, identity, start, end):
    rows = {str(i): [] for i in range(1, 7)}
    messages = []
    for line in path.read_text(encoding='utf-8-sig').splitlines():
        event = json.loads(line)  # actual journalctl -o json, current viewer stderr MESSAGE
        require(str(event['_PID']) == str(identity['pid']) and event['_EXE'] == identity['exe'] and
                event['_BOOT_ID'].replace('-', '') == identity['boot_id'].replace('-', ''),
                'Viewer journal PID/exe/boot mismatch')
        t = int(event['__REALTIME_TIMESTAMP']) / 1000000
        require(start <= t <= end, 'Viewer journal timestamp outside captured runtime window')
        message = event['MESSAGE']
        require(isinstance(message, str), 'Malformed journal message')
        messages.append(message)
        require(not re.search(r'\[recover\]|timeout|stale|pango_ioctl.*(?:rc=-|alarm=1)', message, re.I),
                'Viewer runtime failure evidence')
        match = CAPTURE.fullmatch(message)
        if match:
            values = [float(v) for v in match.groups()[1:6]]
            require(all(math.isfinite(v) and v > 0 for v in values[:2]) and
                    all(math.isfinite(v) and v >= 0 for v in values[2:]) and int(match[7]) == 0,
                    'False/unstable camera frame progress')
            rows[match[1]].append((t, message))
    return rows, messages


def reviewed_reference(item, files, label):
    require(item.get('status') == 'reviewed' and item.get('reviewer') and item.get('note') and item.get('references'),
            'Pending evidence: ' + label)
    for ref in item['references']:
        lines = files[ref['artifact']].read_text(encoding='utf-8-sig').splitlines()
        require(type(ref['line']) is int and 1 <= ref['line'] <= len(lines) and ref['text'] and
                ref['text'] == lines[ref['line'] - 1], 'Raw evidence reference mismatch: ' + label)


def screenshot_series(shots, files, expected, end, start, t0, t1):
    require(isinstance(shots, list) and len(shots) >= 2, 'At least two real post-program screenshots required')
    results = [screenshot_gate(s, files, expected, end, start) for s in shots]
    times = [r[0] for r in results]
    require(times == sorted(set(times)) and t0 <= times[0] < times[-1] <= t1,
            'Screenshots must be distinct captures within identity window')
    require(len({r[1]['xwd_sha256'] for r in results}) >= 2, 'Duplicate original screenshots cannot show progression')
    return results


def verify_document(doc):
    require(doc.get('contract') == 'boardValidation/v2', 'Final scope requires boardValidation/v2; v1 rejected')
    require(doc.get('accepted') is True and doc.get('reviewer') and doc.get('scope') == 'final_board_validation',
            'Unaccepted template/non-final scope')
    files = {k: bound(v) for k, v in doc['artifacts'].items()}
    needed = {'program_receipt', 'delivery', 'owner_preflight', 'cfg_log', 'server_log', 'client_log',
              'program_session', 'program_session_raw', 'identity_before', 'identity_after', 'viewer_journal',
              'driver_before', 'driver_after', 'viewer_elf', 'viewer_source', 'viewer_readonly_identity',
              'model_readonly_identity', 'baseline_identity'}
    require(needed <= files.keys(), 'Required runtime raw evidence missing')
    end = program_gate(doc, files)
    expected = doc['expected_runtime']
    models_identity = load(files['model_readonly_identity'])
    model_hashes = dict((path, digest) for digest, path in
                        re.findall(r'^([0-9a-f]{64})\s+(.+)$', models_identity['stdout'], re.M))
    require(models_identity.get('exit_code') == 0 and not models_identity.get('stderr') and
            models_identity.get('host') == expected['host'] and model_hashes == expected['models'],
            'Current read-only model identity mismatch')
    readonly = load(files['viewer_readonly_identity'])
    require(any(a['remote'] == expected['exe'] and a['sha256'] == expected['exe_sha256'] == sha(files['viewer_elf'])
                for a in readonly['artifacts']) and
            any(a['sha256'] == sha(files['viewer_source']) and a['remote'].endswith('/main.cpp')
                for a in readonly['artifacts']), 'Current read-only viewer source/ELF binding mismatch')
    before, after = load(files['identity_before']), load(files['identity_after'])
    t0, start = identity_gate(before, expected, end)
    t1, start1 = identity_gate(after, expected, end)
    require(t0 < t1 and start == start1 and before['pid'] == after['pid'], 'Viewer replaced/restarted during evidence')
    results = screenshot_series(doc.get('screenshots', []), files, expected, end, start, t0, t1)
    rows, messages = progress_gate(files['viewer_journal'], before, start, t1)
    for camera in ('1', '2', '3', '4'):
        during = [r for r in rows[camera] if t0 <= r[0] <= t1]
        require(len(during) >= 2 and during[0][0] <= results[0][0] and during[-1][0] >= results[-1][0],
                'Primary four-camera progress must span both screenshot captures: ' + camera)
    for model in expected['models']:
        require(any(m.startswith('[model] ' + model + ' OK ') or m.startswith('[rotate-load] ' + model + ' OK ')
                    for m in messages), 'Model not loaded in actual viewer journal: ' + model)
    session_rows = {'viewer_journal': rows}
    runtime_end = t1
    # driving-demo HDMI can reserve C5/C6. Supplemental capture sessions may
    # use different argv, each with its own real process/boot/hash/log binding.
    for session in doc.get('supplemental_capture_sessions', []):
        ex = session['expected_runtime']
        require(all(ex[k] == expected[k] for k in ('board_id', 'host', 'boot_id', 'exe', 'exe_sha256', 'models')),
                'Supplemental capture identity/model mismatch')
        first, last = load(files[session['identity_before']]), load(files[session['identity_after']])
        a, s = identity_gate(first, ex, end)
        b, s2 = identity_gate(last, ex, end)
        require(a < b and s == s2 and first['pid'] == last['pid'] and a > t1,
                'Supplemental capture session replaced or overlaps primary viewer')
        key = session['journal']
        require(key not in session_rows, 'Duplicate capture session journal')
        session_rows[key], _ = progress_gate(files[key], first, s, b)
        runtime_end = max(runtime_end, b)
    observations = doc['capture_observations']
    require(set(observations) == {str(i) for i in range(1, 7)}, 'Six-camera scope observations required')
    for camera, item in observations.items():
        reviewed_reference(item, files, 'camera ' + camera)
        key = item['journal']
        require(key in session_rows, 'Unknown capture session journal')
        camera_rows = session_rows[key][camera]
        require(len(camera_rows) >= 2 and camera_rows[0][0] < camera_rows[-1][0], 'Pending camera progress logs: ' + camera)
        refs = item['references']
        require(all(ref['artifact'] == key for ref in refs), 'Camera references from wrong session')
        capture_refs = [json.loads(ref['text']) for ref in refs]
        require(len(capture_refs) >= 2 and all(CAPTURE.fullmatch(r['MESSAGE']) and
                CAPTURE.fullmatch(r['MESSAGE'])[1] == camera for r in capture_refs) and
                len({r['__REALTIME_TIMESTAMP'] for r in capture_refs}) >= 2,
                'Camera observations require two matching progress samples')
    require(set(doc['diagnostic_sources']) == {'1', '2', '3', '4'}, 'Four diagnostic source reviews required')
    for camera, item in doc['diagnostic_sources'].items():
        reviewed_reference(item, files, 'diagnostic source ' + camera)
        require(all(ref['artifact'] == 'diag' + camera + '_raw' for ref in item['references']),
                'Diagnostic source requires its own raw log')
        require(item.get('bit_sha256') == doc['bit_sha256'] and item.get('board_id') == expected['board_id'] and
                item.get('boot_id') == expected['boot_id'], 'Diagnostic acquisition binding mismatch')
        meta = load(files['diag' + camera + '_metadata'])
        require(meta.get('contract') == 'diagnosticCapture/v1' and meta.get('collector') and
                str(meta.get('source_camera')) == camera and meta.get('bit_sha256') == doc['bit_sha256'] and
                meta.get('board_id') == expected['board_id'] and meta.get('boot_id') == expected['boot_id'] and
                meta.get('raw_sha256') == sha(files['diag' + camera + '_raw']) and
                end < utc(meta['captured_utc']) <= runtime_end, 'Diagnostic raw/time/source binding missing')
    for label in ('visual_normal', 'normal_frame_integrity', 'driver_no_new_errors', 'same_board_identity',
                  'exclusive_viewer_owner', 'program_delivery_check'):
        reviewed_reference(doc['reviews'][label], files, label)
    if doc.get('cold_reset_performed') is True:
        require({'cold_reset_action', 'boot_before', 'boot_after', 'pcie_reenumeration', 'driver_rebind'} <= files.keys(),
                'Cold reset raw action/boot/enumeration/rebind evidence required')
        require(files['boot_before'].read_bytes().strip() != files['boot_after'].read_bytes().strip() and
                files['boot_after'].read_text().strip() == expected['boot_id'], 'Cold reset boot binding mismatch')
    require(doc['reviews']['visual_normal'].get('reviewed_png_sha256') == [r[1]['png_sha256'] for r in results],
            'Reviewer must inspect both exact PNG files')
    integrity_refs = [ref for ref in doc['reviews']['normal_frame_integrity']['references']
                      if ref['artifact'] == 'viewer_journal']
    require(len(integrity_refs) >= 2 and all(CAPTURE.fullmatch(json.loads(ref['text'])['MESSAGE'])
                for ref in integrity_refs) and
            len({json.loads(ref['text'])['__REALTIME_TIMESTAMP'] for ref in integrity_refs}) >= 2,
            'Frame integrity needs actual runtime capture references, not screenshots alone')
    require(any(ref['artifact'] == 'driver_before' for ref in doc['reviews']['driver_no_new_errors']['references']) and
            any(ref['artifact'] == 'driver_after' for ref in doc['reviews']['driver_no_new_errors']['references']),
            'Before/after driver review required')
    require({'baseline_identity', 'identity_before', 'identity_after'} <=
            {ref['artifact'] for ref in doc['reviews']['same_board_identity']['references']},
            'Same-board review must reference baseline and current identities')
    require({'delivery', 'program_receipt', 'cfg_log'} <=
            {ref['artifact'] for ref in doc['reviews']['program_delivery_check']['references']},
            'Delivery/receipt/raw cfg review required')
    return {'status': 'reviewed_evidence_complete', 'contract': 'boardValidation/v2', 'bit_sha256': doc['bit_sha256'],
            'screenshots': [r[1] for r in results], 'automatic_visual_validation': False,
            'automatic_dma_full_completion_proof': False,
            'scope': 'offline consistency checks plus human reviews; acquisition authenticity not proven'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence', required=True)
    args = parser.parse_args()
    try:
        result = verify_document(load(args.evidence))
        result['evidence_sha256'] = sha(args.evidence)
        print(json.dumps(result))
        return 0
    except Exception as error:
        print(json.dumps({'status': 'blocked', 'error_type': type(error).__name__,
                          'error': str(error) if isinstance(error, ValueError) else 'Missing/malformed runtime evidence'}))
        return 1


if __name__ == '__main__':
    sys.exit(main())
