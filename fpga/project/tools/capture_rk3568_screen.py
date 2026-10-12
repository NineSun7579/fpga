"""Capture the real RK3568 X11 desktop, retaining the original XWD."""
import argparse
import json
from pathlib import Path
import struct
from datetime import datetime, timezone

import numpy as np
from PIL import Image
from board_host import ssh_connect, board_host


def convert_xwd(source, target):
    content = source.read_bytes()
    header = struct.unpack('>25I', content[:100])
    size, version, fmt, depth, width, height = header[:6]
    byte_order, bpp, stride = header[7], header[11], header[12]
    masks, colors = header[14:17], header[19]
    if version != 7 or fmt != 2 or bpp not in (24, 32):
        raise ValueError(f'Unsupported XWD: version={version}, format={fmt}, bpp={bpp}')
    data = content[size + colors * 12:]
    if len(data) != height * stride:
        raise ValueError('Incomplete XWD pixel data')
    if bpp == 32:
        pixels = np.frombuffer(data, dtype=('<' if byte_order == 0 else '>') + 'u4')
        pixels = pixels.reshape(height, stride // 4)[:, :width]
    else:
        packed = np.frombuffer(data, dtype='u1').reshape(height, stride)
        packed = packed[:, :width * 3].reshape(height, width, 3).astype('uint32')
        shifts = (0, 8, 16) if byte_order == 0 else (16, 8, 0)
        pixels = sum(packed[:, :, i] << shift for i, shift in enumerate(shifts))
    channels = []
    for mask in masks:
        if not mask:
            raise ValueError('Missing TrueColor mask')
        shift = (mask & -mask).bit_length() - 1
        channels.append(((pixels & mask) >> shift) * 255 // (mask >> shift))
    Image.fromarray(np.stack(channels, axis=-1).astype('uint8')).save(target)
    return {'width': width, 'height': height, 'depth': depth}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    original = args.output.with_suffix('.xwd')
    remote = '/tmp/ov5640_desktop_capture.xwd'
    client = ssh_connect()
    try:
        command = ('sudo -S env DISPLAY=:0 XAUTHORITY=/var/run/lightdm/root/:0 '
                   f'xwd -root -silent -out {remote} && '
                   f'sudo -n chmod 644 {remote}')
        stdin, stdout, stderr = client.exec_command(command, timeout=20)
        stdin.write('123456\n')
        stdin.flush()
        output, errors = stdout.read(), stderr.read()
        code = stdout.channel.recv_exit_status()
        if code:
            raise RuntimeError(f'Desktop capture failed ({code}): {errors.decode(errors="replace")}')
        with client.open_sftp() as transfer:
            transfer.get(remote, str(original))
    finally:
        client.close()
    metadata = convert_xwd(original, args.output)
    metadata.update(host=board_host(), captured_utc=datetime.now(timezone.utc).isoformat(),
                    source='RK3568 X11 :0 root window', png=str(args.output), xwd=str(original))
    args.output.with_suffix('.json').write_text(json.dumps(metadata, indent=2), encoding='utf8')
    print(json.dumps(metadata, indent=2))


if __name__ == '__main__':
    main()
