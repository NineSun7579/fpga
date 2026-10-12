"""Archive only the failed isolated missing-descriptor attempt, then retry serially."""
import json
import shutil
import time
import traceback
from physical_flow import HERE, EVIDENCE, wait_idle, protected, main, status
from preflight import load, require, verify

def recover():
    result = load(EVIDENCE / 'compile_result.json')
    require(result['exit_code'] == 0 and len(result['errors']) == 1
            and 'FileSystem-0003' in result['errors'][0] and 'hsst_sfp.pds' in result['errors'][0],
            'Recovery is restricted to the evidenced missing frozen descriptor failure')
    require(not (EVIDENCE / 'synthesize_launch.json').exists(), 'Unexpected later stage exists')
    status('WAITING_TO_ARCHIVE_FAILED_COMPILE')
    wait_idle(); protected(); verify()
    archive = HERE / 'attempts/tool_01_missing_hsst_descriptor'
    require(not archive.exists(), 'Failure archive exists; do not duplicate runner')
    archive.mkdir()
    for name in ['evidence', 'compile', 'constraint_check', 'project.pds', 'analysis_tools',
                 'constraints_candidate', 'controller.log', 'controller_status.json', 'flow.log',
                 'run.log', 'impl.tcl', 'logbackup', 'multiseed_summary.csv']:
        if (HERE / name).exists():
            # The current controller log is distinct from archived original log.
            shutil.move(str(HERE / name), str(archive / name))
    (archive / 'archive_receipt.json').write_text(json.dumps({
        'time': time.time(), 'failure': result, 'PDS_idle_verified': True,
        'correction': 'copy exact frozen .pds IP descriptor side-assets; no IP edits',
        'remote_or_program': False}, indent=2), encoding='ascii')
    main()

if __name__ == '__main__':
    try:
        recover()
    except BaseException:
        EVIDENCE.mkdir(exist_ok=True)
        (EVIDENCE / 'recovery_failure.txt').write_text(traceback.format_exc(), encoding='utf8')
        status('RECOVERY_FAILED_EVIDENCE_PRESERVED')
        raise
