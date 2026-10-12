"""Read live ioctl arguments without opening the DMA device or modifying the viewer."""
import glob
import json
import os
import struct
import sys
import time

pid = int(sys.argv[1])
result = {'pid': pid, 'scope': 'read-only /proc syscall and process memory snapshot', 'samples': []}
memory = os.open(f'/proc/{pid}/mem', os.O_RDONLY)
try:
    deadline = time.monotonic() + 3
    seen = set()
    while time.monotonic() < deadline and len(result['samples']) < 12:
        for path in glob.glob(f'/proc/{pid}/task/*/syscall'):
            try:
                fields = open(path).read().split()
                if len(fields) < 4 or fields[0] != '29':
                    continue
                command = int(fields[2], 16)
                if command not in (0xc0045304, 0xc0045305):
                    continue
                pointer = int(fields[3], 16)
                first = os.pread(memory, 40, pointer)
                second_fields = open(path).read().split()
                if fields != second_fields or first != os.pread(memory, 40, pointer):
                    continue
                values = struct.unpack('<IIIII4xQQ', first)
                if values[2] not in (0, 1, 2) or not 0 < values[4] <= 4194304:
                    continue
                key = (command, values)
                if key in seen:
                    continue
                seen.add(key)
                result['samples'].append({'tid': int(path.split('/')[-2]), 'ioctl': hex(command),
                                         'current_len': values[0], 'offset_addr': hex(values[1]),
                                         'cmd': values[2], 'ddr3_addr': hex(values[3]),
                                         'total_length': values[4],
                                         'data_pointers': [hex(v) for v in values[5:]],
                                         'raw_40bytes': first.hex()})
            except (OSError, ValueError, struct.error):
                continue
        time.sleep(.005)
finally:
    os.close(memory)
print(json.dumps(result, indent=2))
