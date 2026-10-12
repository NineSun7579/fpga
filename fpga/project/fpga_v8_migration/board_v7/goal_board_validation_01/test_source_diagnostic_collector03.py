"""Local protocol tapes, not an RTL model, driver stub, or hardware test."""
from collections import deque
import contextlib
import io as textio
import unittest
from unittest.mock import patch

import source_diagnostic_collector03 as c


class Tape:
    """Require exact serial transactions; answers are explicit test inputs."""
    def __init__(self, operations):
        self.operations = deque(operations)
        self.calls = []

    def next(self, direction, address, value=None):
        self.calls.append((direction, address, value))
        expected, addr, val, answer = self.operations.popleft()
        assert (direction, address, value) == (expected, addr, val)
        if isinstance(answer, BaseException):
            raise answer
        return answer

    def read32(self, address):
        return self.next('read', address)

    def write32(self, address, value):
        return self.next('write', address, value)


def success_tape(camera, final_epoch=7, status_after=1):
    base = 0x20001000 + (camera - 1) * 0x100
    def r(offset, result):
        return ('read', base + offset, None, result)
    def w(offset, value):
        return ('write', base + offset, value, None)
    # Hand-authored counter/flag examples with all field widths represented.
    words = [0xffffffff, 0xffffff, 0xffff, 3, 123, 124, 5, 0xa5ffff,
             444, 222, 223, 1, 0x96, 2, 6, 0x53464401]
    ops = [r(0x40, 7), r(0, 4), r(0x40, 7), w(0x10, 1), r(0, 1)]
    for index, word in enumerate(words):
        ops += [w(0x20, index), r(0x20, index), r(0x30, word)]
    ops += [r(0, status_after), r(0x40, final_epoch)]
    if final_epoch == 7 and status_after == 1:
        ops += [w(0x10, 2), r(0, 4), r(0x40, 7)]
    return ops, words


class ProtocolTests(unittest.TestCase):
    def test_four_camera_addresses_and_serial_atomic_read(self):
        for camera in range(1, 5):
            ops, words = success_tape(camera)
            tape = Tape(ops)
            row = c.snapshot(c.RegisterIO(tape), camera)
            self.assertFalse(tape.operations)
            self.assertEqual(row['raw_words'], words)
            self.assertEqual(row['epoch_before'], row['epoch_after'])
            self.assertFalse(row['normal_frames_proven'])
            self.assertTrue(all(addr & 15 == 0 for _, addr, _ in tape.calls))
            self.assertEqual(row['values']['source_bytes'], 0xffffff)
            self.assertEqual(row['values']['href_segments'], 0xffff)
            self.assertEqual(row['values']['tail_gap_cycles'], 0xffff)
            self.assertEqual(row['values']['raw_byte_vsync_overlap'], 6)
            self.assertEqual(row['values']['flags'], dict(armed=True, have_previous=False,
                seen_href=True, tail_gap_saturated=False, clipped_href=False, vsync_mismatch=True,
                counter_overflow=False, bad=True))
            self.assertEqual(row['values']['boundary_flags'], dict(start_native=False,
                end_native=True, start_aligned=True, end_aligned=False, end_href=True,
                previous_start_aligned=False, previous_end_aligned=False, previous_bad=True))

    def test_alignment_rejected_before_submission(self):
        tape = Tape([])
        reg = c.RegisterIO(tape)
        for delta in (1, 4, 8, 12):
            with self.assertRaises(ValueError):
                reg.operation('read', 0x20001000 + delta)
        self.assertEqual(tape.calls, [])

    def test_epoch_changed_rejects_whole_snapshot_no_release(self):
        ops, _ = success_tape(3, final_epoch=8)
        tape = Tape(ops)
        with self.assertRaisesRegex(ValueError, 'epoch changed'):
            c.snapshot(c.RegisterIO(tape), 3)
        self.assertFalse(tape.operations)
        self.assertNotIn(('write', 0x20001210, 2), tape.calls)

    def test_reset_or_lease_loss_rejected(self):
        for status in (0, 8, 9):
            ops, _ = success_tape(1, status_after=status)
            with self.assertRaises(ValueError):
                c.snapshot(c.RegisterIO(Tape(ops)), 1)

    def test_busy_unavailable_wait_is_bounded_without_acquire(self):
        tape = Tape([('read', 0x20001040, None, 7)] +
                    [('read', 0x20001000, None, 0), ('read', 0x20001040, None, 7)] * 3)
        times = iter((0, 0.1, 0.2, 0.3))
        with self.assertRaises(TimeoutError):
            c.snapshot(c.RegisterIO(tape), 1, timeout=0.25, clock=lambda: next(times), sleep=lambda _: None)
        self.assertFalse(tape.operations)
        self.assertTrue(all(d == 'read' for d, _, _ in tape.calls))

    def test_existing_lease_and_invalid_session_do_not_acquire(self):
        for status in (1, 5, 8, 12):
            tape = Tape([('read', 0x20001040, None, 7),
                         ('read', 0x20001000, None, status), ('read', 0x20001040, None, 7)])
            with self.assertRaises(ValueError):
                c.snapshot(c.RegisterIO(tape), 1)
            self.assertTrue(all(d == 'read' for d, _, _ in tape.calls))

    def test_epoch_change_while_waiting_does_not_acquire(self):
        tape = Tape([('read', 0x20001140, None, 7),
                     ('read', 0x20001100, None, 4), ('read', 0x20001140, None, 8)])
        with self.assertRaisesRegex(ValueError, 'Epoch changed'):
            c.snapshot(c.RegisterIO(tape), 2)
        self.assertTrue(all(d == 'read' for d, _, _ in tape.calls))

    def test_mid_read_deadline_refuses_partial_result(self):
        ops, _ = success_tape(1)
        tape = Tape(ops[:8])  # acquire plus index0/data0 only
        times = iter((0, 0.1, 0.3))
        with self.assertRaises(TimeoutError):
            c.snapshot(c.RegisterIO(tape), 1, timeout=0.25, clock=lambda: next(times))
        self.assertFalse(tape.operations)
        self.assertNotIn(('write', 0x20001010, 2), tape.calls)

    def test_read_failure_poison_is_permanent_and_retains_object(self):
        for answer in (None, OSError('completion uncertain'), KeyboardInterrupt(), -1):
            tape = Tape([('read', 0x20001040, None, answer)])
            reg = c.RegisterIO(tape)
            with self.assertRaises(c.UncertainDMA):
                reg.rd(1, c.EPOCH)
            for _ in range(2):
                with self.assertRaises(c.UncertainDMA):
                    reg.wr(1, c.COMMAND, 2)
            self.assertIs(reg.driver, tape)
            self.assertEqual(len(tape.calls), 1)

    def test_write_failure_stops_all_future_submissions(self):
        tape = Tape([('write', 0x20001320, 0, OSError('timeout'))])
        reg = c.RegisterIO(tape)
        with self.assertRaises(c.UncertainDMA):
            reg.wr(4, c.INDEX, 0)
        with self.assertRaises(c.UncertainDMA):
            reg.rd(4, c.DATA)
        self.assertEqual(len(tape.calls), 1)

    def test_format_and_reserved_width_reject(self):
        _, words = success_tape(1)
        for index, value in ((15, 0), (1, 1 << 24), (2, 1 << 16), (7, 1 << 24), (12, 1 << 8)):
            bad = words.copy()
            bad[index] = value
            with self.assertRaises(ValueError):
                c.decode(bad)

    def test_default_check_cannot_open_device(self):
        with patch.object(c.os, 'open', side_effect=AssertionError('device open forbidden')), \
                patch.object(c.sys, 'argv', ['collector']), contextlib.redirect_stdout(textio.StringIO()):
            self.assertEqual(c.main(), 0)


if __name__ == '__main__':
    unittest.main()
