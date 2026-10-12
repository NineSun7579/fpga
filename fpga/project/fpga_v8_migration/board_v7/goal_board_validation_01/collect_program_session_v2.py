"""Local time-boundary collector only; never launches programmer or board code.

Use --start before the separately authorized consumer command, --complete
immediately after it returns. Do not reconstruct times from old file mtimes.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
from new_program_candidate import sha, load, require


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--start', action='store_true')
    mode.add_argument('--complete', action='store_true')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--delivery', type=Path, required=True)
    parser.add_argument('--receipt', type=Path)
    parser.add_argument('--exit-code', type=int)
    parser.add_argument('--collector', required=True)
    args = parser.parse_args()
    now = datetime.now(timezone.utc).isoformat()
    raw = args.output.with_suffix('.raw.txt')
    if args.start:
        require(not args.output.exists() and not raw.exists(), 'Session output already exists')
        doc = {'contract': 'programSession/v1', 'collector': args.collector, 'started_utc': now,
               'delivery_manifest_sha256': sha(args.delivery)}
        raw.write_text('started_utc=' + now + '\ndelivery_manifest_sha256=' + doc['delivery_manifest_sha256'] + '\n', encoding='utf-8')
    else:
        doc = load(args.output)
        require('completed_utc' not in doc and doc['delivery_manifest_sha256'] == sha(args.delivery),
                'Completed session or delivery changed')
        require(args.receipt is not None and args.exit_code is not None, 'Actual receipt and command exit required')
        receipt = load(args.receipt)
        require(receipt.get('check_only') is False, 'Check-only is not programming')
        doc.update(completed_utc=now, receipt_sha256=sha(args.receipt), exit_code=args.exit_code)
        with raw.open('a', encoding='utf-8') as stream:
            for key in ('completed_utc', 'receipt_sha256', 'exit_code'):
                stream.write(f'{key}={doc[key]}\n')
    args.output.write_text(json.dumps(doc, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
