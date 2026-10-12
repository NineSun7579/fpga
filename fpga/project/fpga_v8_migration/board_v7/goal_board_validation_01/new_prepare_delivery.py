"""Offline assembler of REAL reviewed artifacts. Missing files reject by default.

Does not generate acceptance, alter build artifacts, or execute vendor/PDS tools.
--check is the default; --write publishes only beneath this script's directory.
"""
import argparse
import json
from pathlib import Path
import sys
from new_program_candidate import HERE, BUILD, VENDOR, absolute, delivery_build, load, require, sha, verify_document
from endpoint_recompute import ROLES as ENDPOINT_ROLES

ARTIFACTS = ('route', 'sta_raw', 'sta_summary', 'mailbox_raw', 'mailbox_audit',
             'reset_raw', 'reset_audit', 'reset_targets', 'reset_bindings', 'mapping',
              'routed_graph', 'routed_endpoint_audit', 'sync_pairs', 'reset_mpw_raw', 'reset_mpw_audit',
              'sync_later_raw', 'sync_later_audit',
             'io_audit', 'hsst', 'motion', 'routed_dump', 'routed_verilog',
             'coverage', 'protected_before', 'protected_after', 'inputs_before', 'inputs_after', 'acceptance')
AUDIT_ROLES = {'audit_fixed', 'verify_routed11', 'summarize', 'raw_audit', 'consumer', 'routed_connection',
               'endpoint_recompute', *ENDPOINT_ROLES}


def entry(value):
    path = absolute(value)
    require(path.is_file() and path.stat().st_size > 0, 'Missing/empty source artifact')
    return {'path': str(path), 'sha256': sha(path), 'bytes': path.stat().st_size}


def assemble(sources):
    require(sources.get('contract') == 'deliverySources/v1', 'deliverySources/v1 required')
    build = delivery_build(sources)
    require(sources.get('candidate_id') and set(ARTIFACTS) <= set(sources['artifacts']),
            'Concrete candidate and complete actual evidence paths required')
    artifacts = {k: entry(v) for k, v in sources['artifacts'].items()}
    require(AUDIT_ROLES <= sources['audit_sources'].keys(), 'Actual audit source paths by role required')
    audits = {k: entry(v) for k, v in sources['audit_sources'].items()}
    # Hashes are calculated from disk, then checked against external review.
    # accepted/reviewer are NEVER manufactured by this assembler.
    review = load(artifacts['acceptance']['path'])
    require(review.get('contract') == 'validatedDeliveryAcceptance/v1' and review.get('accepted') is True and
            review.get('reviewer') and review.get('artifact_sha256') ==
            {k: v['sha256'] for k, v in artifacts.items() if k != 'acceptance'},
            'Actual independent acceptance and exact reviewed artifact hashes required')
    manifest = {'contract': 'validatedDelivery/v1', 'status': 'validated',
                'candidate_id': sources['candidate_id'], 'build_root': str(build),
                'target': 'PG2L100H', 'mode': 'sram', 'programming_performed': False, 'board_verified': False,
                'bitstream': entry(sources['bit']), 'programmer': entry(str(VENDOR.resolve())),
                 'artifacts': artifacts, 'audit_sources': audits,
                 'target_logs': sources['target_logs'],
                'mailbox_expected_pairs': sources['mailbox_expected_pairs'],
                'mapping_difference_reason': sources.get('mapping_difference_reason'),
                'limitations': sources['limitations']}
    verify_document(manifest)
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sources', type=Path, default=HERE / 'delivery_sources.prepare.json')
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--check', action='store_true')
    mode.add_argument('--write', action='store_true')
    parser.add_argument('--output', type=Path, default=HERE / 'delivery_manifest.json')
    args = parser.parse_args()
    try:
        source_hash = sha(args.sources)
        manifest = assemble(load(args.sources))
        require(sha(args.sources) == source_hash, 'Sources descriptor changed during verification')
        output = args.output.resolve()
        require(output.parent == HERE.resolve(), 'Assembler output must stay in goal_board_validation_01')
        if args.write:
            require(not output.exists(), 'Output exists; choose a new local filename for review')
            with output.open('x', encoding='utf-8') as stream:
                json.dump(manifest, stream, ensure_ascii=False, indent=2)
        print(json.dumps({'status': 'written_validated_delivery' if args.write else 'validated_only',
                          'output': str(output) if args.write else None,
                          'bit_sha256': manifest['bitstream']['sha256'], 'sources_sha256': source_hash}))
        return 0
    except Exception as error:
        print(json.dumps({'status': 'blocked', 'error_type': type(error).__name__,
                          'error': str(error) if isinstance(error, ValueError) else 'Missing/malformed delivery evidence'}))
        return 1


if __name__ == '__main__':
    sys.exit(main())
