from pathlib import Path
import hashlib
import json
import re
import zipfile

OUT = Path(__file__).resolve().parent
PROJECT = OUT.parents[2]
REPLAY = OUT.parent
ARCHIVE = PROJECT / 'bitstream_six_recovery_20261002_192245'
FILES = ['source/top.v', 'source/sfp/sfp_rx_link.v',
         'source/sfp/sfp_video_rx.v', 'source/sfp/sfp_rx_cam_if.v',
         'source/sfp/video_async_fifo.v', 'ipcore/hsst_sfp/hsst_sfp.v']

def sha(b):
    return hashlib.sha256(b).hexdigest()

def main():
    manifest = json.loads((ARCHIVE / 'source_sha256.json').read_bytes())
    rows = []
    with zipfile.ZipFile(ARCHIVE / 'sources.zip') as z:
        assert all(sha(z.read(n)) == manifest[n] for n in z.namelist() if not n.endswith('/'))
        for n in FILES:
            b = z.read(n)
            assert sha(b) == manifest[n] == sha((PROJECT / n).read_bytes()), n
            dest = OUT / 'extracted' / n
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(b)
            rows.append(dict(file=n, sha256=sha(b), zip_manifest_current_identical=True))
    summary = json.loads((REPLAY / 'summary.json').read_bytes())
    golden = [int(l, 16) for l in (REPLAY / 'input.hex').read_text().splitlines()]
    assert len(golden) == 614400
    tests = []
    for row in summary['results']:
        name = f"{row['receiver']}_{row['kind']}_{row['offset']}"
        pix = REPLAY / (name + '.pixels')
        observed = [int(l, 16) for l in pix.read_text().splitlines()]
        assert observed == golden
        log = (REPLAY / (name + '.log')).read_text()
        match = re.search(r'RESULT pixels=(\d+) frame_pixels=(\d+) sof=(\d+) controls=(\d+) relocks=(\d+) overflow=(\d+)', log)
        actual = dict(zip(['pixels','frame_pixels','sof','controls','relocks','overflow'],map(int,match.groups())))
        assert all(actual[k] == row[k] for k in actual)
        assert row['exact'] and row['sof'] == 1 and row['overflow'] == 0
        if row['kind'] != 'baseline':
            assert row['events'] == 128 and row['relocks'] >= 128
        tests.append(dict(**row, pixels_file_sha256=sha(pix.read_bytes()), log_sha256=sha((REPLAY/(name+'.log')).read_bytes())))
    assert len(tests) == 24
    tested = json.loads((REPLAY / 'manifest.json').read_bytes())
    for n in ['source/sfp/sfp_rx_link.v', 'source/sfp/sfp_video_rx.v']:
        assert tested[str((PROJECT / n).resolve())] == manifest[n]
    bit = ARCHIVE / 'top.sbit'
    assert sha(bit.read_bytes()) == 'c3f07533e37e77ab734d37a5a4ba4ed8ebc8af0841e09fa43f2dcc076f16a44a'
    candidate = sha((REPLAY / 'candidate_sfp_video_tx.v').read_bytes())
    assert candidate == '29a637f725a48323b8f8351221183cf823afa5917a41098bc748cd61969793cc'
    report = dict(archive=str(ARCHIVE), bit_sha256=sha(bit.read_bytes()), bit_bytes=bit.stat().st_size,
                  source_zip_sha256=sha((ARCHIVE/'sources.zip').read_bytes()),
                  source_manifest_sha256=sha((ARCHIVE/'source_sha256.json').read_bytes()),
                  all_725_zip_entries_match_manifest=True, six_files=rows,
                  candidate_sha256=candidate, replay_results=tests,
                  exact_archive_receiver_reused_cases=12, conservative_old_receiver_cases=12,
                  guards=summary['guards'], payload_words=summary['data_words'],
                  provenance='Pre-build source snapshot in 192245 archive; archived project registers these sources; bit.log analyzes these source paths and generates top.sbit at 19:45:08. flash_six_verified_20261002.tcl assigns the archived C3F bit. No hardware query or fresh burn verification performed.',
                  limits=['Only wrapper/decoder are replayed; vendor HSST is stubbed. Splitter/FIFO/top/IP hashes are checked, not dynamically tested in these replays.',
                          'GE automatic transformations remain unverified.',
                          'Manifest project_build/generate_bitstream/top.sbit is a previous 44d6a5... bit (snapshot before build), not the final C3F bit; final C3F checksum is independently computed.',
                          'Archive association is documentary build provenance, not a cryptographic source-to-bit attestation or independent confirmation of current hardware contents.'])
    (OUT / 'evidence.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({k:report[k] for k in ['bit_sha256','bit_bytes','exact_archive_receiver_reused_cases','conservative_old_receiver_cases','guards','payload_words']},indent=2))

if __name__ == '__main__':
    main()
