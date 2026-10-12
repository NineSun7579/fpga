"""Independent transaction/state oracle; never reads DUT hierarchy/state storage.

States are derived from admitted sensor frames, completed bus obligations and
consumer protocol events. Every public state-change snapshot is then checked.
All 128 bits are compared, including tag padding and abort data with STRB=0.
"""
from collections import Counter


def pixel(seed, index, width):
    return (seed*7919 + index*73 + (index//width)*1237 + ((index % width) ^ 0x55aa)) & 0xffff


def golden_word(seed, word_index, width):
    return sum(pixel(seed, word_index*8+lane, width) << (16*lane) for lane in range(8))


def verify(path, words, width, host_required, bad_cfg):
    bases = [0x01800000, 0x01a00000]
    length = words*16
    banks = [None, None]
    offers = {'C': None, 'H': None}
    rr = {'C': 0, 'H': 0}
    memory = {}
    frozen = {}
    pending_sensor = None
    capture = None
    burst = None
    last_response = None
    generation = 0
    next_seq = 1
    armed = False
    published = failed = rejected = 0
    count = Counter()
    resets = 0
    for line_number, line in enumerate(path.read_text().splitlines(), 1):
        a = line.split()
        event = a[0]
        def check(condition, detail):
            if not condition:
                raise AssertionError(f'{path.name}:{line_number}: {line}: {detail}')
        count[event] += 1
        if event == 'R':
            banks = [None, None]
            offers = {'C': None, 'H': None}
            rr = {'C': 0, 'H': 0}
            frozen = {}
            capture = burst = last_response = None
            generation, next_seq = 0, 1
            armed = False
            published = failed = rejected = 0
            resets += 1
        elif event == 'F':
            pending_sensor = tuple(map(int, a[1:]))
        elif event == 'C':
            new_gen, accept, reject = map(int, a[1:])
            check(all(b is None for b in banks) and burst is None and capture is None,
                  'configuration while ownership/AXI outstanding')
            expected = not bad_cfg and new_gen != 0 and new_gen != generation
            check((accept, reject) == (int(expected), int(not expected)), 'config result')
            if accept:
                generation, next_seq, armed = new_gen, 1, True
                rr = {'C': 0, 'H': 0}
        elif event == 'Q':
            check(capture is None and all(b is None for b in banks), 'rollover injection while owned')
            next_seq = int(a[1])
        elif event == 'A':
            bank = int(a[1])
            check(armed and not bad_cfg and next_seq != 0 and banks[bank] is None,
                  'admission without free bank/fresh epoch')
            check(capture is None and pending_sensor is not None, 'duplicate/unbound capture')
            capture = {'bank': bank, 'seed': pending_sensor[0], 'pixels': pending_sensor[1],
                       'seq': next_seq, 'gen': generation, 'tag_completed': False}
            banks[bank] = {'state': 1}
        elif event == 'M':
            address, byte_length = int(a[1], 16), int(a[2])
            check(capture is not None, 'DMA command without reserved source')
            base = bases[capture['bank']]
            check((address, byte_length) in [(base, length), (base+length, 16)],
                  'runtime/unbounded command layout')
        elif event == 'AW':
            addr, beats = int(a[1], 16), int(a[2])
            check(capture is not None and burst is None, 'AW without capture or prior B')
            bank = capture['bank']
            check(banks[bank]['state'] == 1 and bank not in frozen, 'AW to immutable lease')
            check(bases[bank] <= addr and addr+16*beats <= bases[bank]+length+16,
                  'AW outside source/tag bounds')
            check(addr % 16 == 0 and 1 <= beats <= 16 and (addr & 4095)+beats*16 <= 4096,
                  'AW burst/alignment/4KiB boundary')
            tag = addr == bases[bank]+length
            check(not tag or beats == 1, 'tag must be one whole 128-bit word')
            burst = {'base': addr, 'addr': addr, 'left': beats, 'tag': tag, 'bank': bank}
        elif event == 'W':
            addr, word, strobe, last = int(a[1],16), int(a[2],16), int(a[3],16), int(a[4])
            check(burst is not None and burst['left'] > 0 and addr == burst['addr'], 'W obligation/address')
            check(last == (burst['left'] == 1), 'strict WLAST')
            check(strobe in [0, 0xffff], 'partial/unknown WSTRB')
            if strobe == 0:
                check(word == 0, 'all 128 dummy bits must be zero even with no strobes')
                count['dummy_words'] += 1
            else:
                expected = capture['seq'] if burst['tag'] else golden_word(
                    capture['seed'], (addr-bases[burst['bank']])//16, width)
                check(word == expected, f'full 128-bit golden mismatch got={word:032x} expected={expected:032x}')
                if not burst['tag']:
                    check((addr-bases[burst['bank']])//2+8 <= capture['pixels'], 'write of unoffered sensor pixels')
                memory[addr] = word
                count['exact_payload_words' if not burst['tag'] else 'exact_tag_words'] += 1
            burst['addr'] += 16
            burst['left'] -= 1
        elif event == 'B':
            addr, response = int(a[1],16), int(a[2])
            check(burst is not None and burst['left'] == 0 and addr == burst['base'], 'B before final W')
            check(response in [0, 2], 'unexpected response')
            last_response = (burst['tag'], response)
            if burst['tag'] and response == 0:
                capture['tag_completed'] = True
            burst = None
        elif event == 'P':
            bank, seq = map(int, a[1:])
            check(capture is not None and burst is None and capture['tag_completed'], 'publication before actual tag B')
            check(last_response == (True, 0), 'failed tag publication')
            check(bank == capture['bank'] and seq == next_seq and seq != 0, 'publication identity')
            check(capture['pixels'] == words*8, 'publication of malformed source')
            expected_image = [golden_word(capture['seed'], i, width) for i in range(words)] + [seq]
            actual_image = [memory.get(bases[bank]+16*i) for i in range(words+1)]
            check(actual_image == expected_image, 'DDR image incl. tag padding differs from independent RGB565 golden')
            frozen[bank] = tuple(actual_image)
            banks[bank] = {'state': 2, 'seq': seq, 'gen': generation,
                           'claimed': set(), 'released': set() if host_required else {'H'}}
            next_seq = (next_seq+1) & 0xffffffff
            if next_seq == 0:
                armed = False
            published += 1
            count['certified_frames'] += 1
            count['golden_image_words'] += words+1
            capture = None
        elif event == 'E':
            check(capture is not None and burst is None, 'error release before DMA obligations retired')
            bank = capture['bank']
            check(banks[bank]['state'] == 1, 'failure released a published lease')
            banks[bank] = None
            capture = None
            failed += 1
        elif event in ['O', 'D']:
            consumer = a[1]
            bank, seq, gen = map(int, a[2:5])
            addr, byte_length, token, camera, raw = int(a[5],16), int(a[6]), int(a[7],16), int(a[8]), int(a[9])
            record = banks[bank]
            check(record is not None and record['state'] == 2 and consumer not in record['claimed'],
                  'descriptor before publication or repeated claim')
            payload = (bank, seq, gen, addr, byte_length, token, camera, raw)
            expected = (bank, record['seq'], record['gen'], bases[bank], length,
                        (record['gen']<<32)|record['seq'], 4, 1)
            check(payload == expected, 'descriptor exact identity/layout/certification')
            if consumer == 'H':
                check(host_required, 'host claim in explicit coop-only mode')
            if event == 'O':
                eligible = [i for i,b in enumerate(banks) if b and b['state']==2 and consumer not in b['claimed']]
                chosen = rr[consumer] if len(eligible)==2 else eligible[0]
                check(bank == chosen and offers[consumer] is None, 'descriptor deterministic order/independence')
                offers[consumer] = payload
            else:
                check(offers[consumer] == payload, 'accepted descriptor differs from offered stable record')
                offers[consumer] = None
                record['claimed'].add(consumer)
                rr[consumer] = 1-bank
        elif event == 'L':
            consumer = a[1]
            camera, bank, seq, gen = map(int, a[2:6])
            token, accept, reject = int(a[6],16), int(a[7]), int(a[8])
            record = banks[bank]
            expected = bool(record and record['state'] == 2 and consumer in record['claimed']
                            and consumer not in record['released'] and camera == 4
                            and (seq,gen)==(record['seq'],record['gen']) and token==(gen<<32)|seq)
            check((accept,reject)==(int(expected),int(not expected)), 'release matching/claim/stale result')
            if accept:
                record['released'].add(consumer)
                if record['released'] == {'C','H'}:
                    image = tuple(memory.get(bases[bank]+16*i) for i in range(words+1))
                    check(image == frozen[bank], 'leased DDR contents changed while held')
                    del frozen[bank]
                    banks[bank] = None
                    count['fully_released_frames'] += 1
            else:
                rejected += 1
        elif event == 'S':
            actual = tuple(map(int,a[1:]))
            expected = tuple((b['state'] if b else 0) for b in banks) + (int(armed),0,published,failed,rejected)
            check(actual == expected, f'independent state oracle expected {expected}, got {actual}')
            count['state_snapshots'] += 1
        elif event == 'Z':
            checks, aw, b, w, abort = map(int,a[1:])
            check(aw == count['AW'] and b == count['B'] and w == count['W'] and abort == count['E'], 'summary counts')
            check(all(x is None for x in banks) and capture is None and burst is None and not frozen,
                  'unfinished ownership at end')
            check(aw-b == (1 if resets == 2 else 0), 'AW/B ledger including one coordinated reset cancellation')
            count['explicit_checks'] = checks
        else:
            raise AssertionError('Unknown trace event ' + event)
    if count['Z'] != 1:
        raise AssertionError('Missing trace completion')
    return dict(count)
