"""Build only: stage six-camera parity sources; never open or execute hardware."""
from pathlib import Path
import hashlib
import json
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import board_ssh

root = Path(__file__).resolve().parent
background = '--background' in sys.argv
name_prefix = 'background_thumbnail_parity' if background else 'thumbnail_six_parity'
remote = '/userdata/linaro/fpga-zero-copy-host'+('-background' if background else '')
sources = {
    name_prefix+'.cpp': root / ('host/'+name_prefix+'.cpp'),
    'pcie_session.hpp': root / 'host/pcie_session.hpp',
    'bound_rknn.hpp': root / 'host/bound_rknn.hpp',
    'shared_consumer.hpp': root / 'host/shared_consumer.hpp',
    'rknn_api.h': root.parent / 'display_latency_delivery/src/rknn_api.h',
    'pango_zc_uapi.h': root / 'driver/pango_zc_uapi.h',
    'cooperative_linux_transport/driver_abi.hpp': Path(
        'D:/race/ov56401/project/fpga_v8_migration/cooperative_linux_transport/driver_abi.hpp'),
}
if background:
    sources['background_thumbnail_reader.hpp'] = root / 'host/background_thumbnail_reader.hpp'
command = ('cd ' + remote + ' && g++ -std=c++17 -O2 -Wall -Wextra -Werror '
           +name_prefix+'.cpp -lrknnrt -pthread -o '+name_prefix)
client = board_ssh.connect()
try:
    rc, out, err = board_ssh.run(client, 'mkdir -p ' + remote + '/cooperative_linux_transport')
    if rc:
        raise RuntimeError(out + err)
    with client.open_sftp() as sftp:
        for name, source in sources.items():
            sftp.put(str(source), remote + '/' + name)
        # Verify uploaded bytes before compiling, including the current session header.
        for name, source in sources.items():
            with sftp.open(remote + '/' + name, 'rb') as staged:
                if staged.read() != source.read_bytes():
                    raise RuntimeError('Staged source differs: ' + name)
    rc, out, err = board_ssh.run(client, command, timeout=90)
    (root / (name_prefix+'_build.log')).write_text(out + err, encoding='utf-8')
    print('return_code', rc, out, err)
    if rc:
        raise SystemExit(rc)
    if background:
        rc, out, err = board_ssh.run(client, 'cd '+remote+' && ./'+name_prefix+' --self-test', timeout=30)
        (root / (name_prefix+'_target_selftest.log')).write_text(out+err,encoding='utf-8')
        if rc:
            raise RuntimeError('Background parity pure selftest failed: '+out+err)
    # Compile current legacy callers without executing or replacing their binaries.
    rc, out, err = board_ssh.run(client, 'mkdir -p ' + remote + '/six-parity-compat')
    if rc:
        raise RuntimeError(out + err)
    with client.open_sftp() as sftp:
        for name in ('thumbnail_parity.cpp', 'paired_pointer.cpp'):
            sftp.put(str(root / 'host' / name), remote + '/six-parity-compat/' + name)
    compatibility_commands = [
        'g++ -std=c++17 -O2 -Wall -Wextra -Werror -I. -fsyntax-only six-parity-compat/thumbnail_parity.cpp',
        'g++ -std=c++17 -O2 -Wall -Wextra -Werror -I. -fsyntax-only six-parity-compat/paired_pointer.cpp',
        'g++ -std=c++17 -O2 -Wall -Wextra -Werror -I. -DOFFLOAD_SHARED_INPUT -fsyntax-only six-parity-compat/paired_pointer.cpp',
    ]
    compatibility_log = []
    for check in compatibility_commands:
        rc, out, err = board_ssh.run(client, 'cd ' + remote + ' && ' + check, timeout=90)
        compatibility_log.append(check + '\nreturn_code=' + str(rc) + '\n' + out + err)
        (root / (name_prefix+'_compat_build.log')).write_text(
            '\n'.join(compatibility_log), encoding='utf-8')
        if rc:
            raise RuntimeError(out + err)
    with client.open_sftp() as sftp:
        with sftp.open(remote + '/'+name_prefix, 'rb') as binary:
            binary_bytes = binary.read()
    manifest = {
        'executable': remote + '/'+name_prefix,
        'command': command, 'build_return_code': rc, 'hardware_executed': False,
        'compatibility_compile_commands': compatibility_commands,
        'executable_sha256': hashlib.sha256(binary_bytes).hexdigest(),
        'sources_sha256': {name: hashlib.sha256(path.read_bytes()).hexdigest()
                           for name, path in sources.items()},
        'contract_sha256': {name: hashlib.sha256((root / name).read_bytes()).hexdigest()
                            for name in (
                                'integrated_six/source/delivery/delivery_regs.v',
                                'integrated_six/source/display/display_thumbnail_ddr.v',
                                'integrated_six/source/display/rgb565_display_decimator.v',
                                'six_camera_viewer_src/thumbnail_delivery.h')},
    }
    if background:
        manifest['contract_sha256'] = {
            name: hashlib.sha256((root/name).read_bytes()).hexdigest()
            for name in ('BACKGROUND_PROTOCOL.md',
                         'integrated_six_background/source/delivery/delivery_regs.v',
                         'integrated_six_background/source/delivery/background_six.v',
                         'integrated_six_background/source/delivery/background_producer.v',
                         'integrated_six_background/source/pcie_dma/pcie_fifo.v')}
        manifest['pure_target_selftest_passed'] = True
    (root / (name_prefix+'_build_manifest.json')).write_text(
        json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(manifest, indent=2))
finally:
    client.close()
