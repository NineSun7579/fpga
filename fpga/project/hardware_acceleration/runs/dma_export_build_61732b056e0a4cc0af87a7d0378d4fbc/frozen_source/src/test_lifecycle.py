"""Offline model checks; export cases assume a hypothetical audited backend.

They are executable expectations for parent review, not a kernel safety proof.
"""
import itertools
import unittest
from lifecycle_model import Driver, Rejected, slice_pages, PAGE, PIXELS, STRIDE, RX_BYTES


class Lifecycle(unittest.TestCase):
    def setUp(self):
        self.d = Driver(export_proven=True, backend_audited=True)
        self.generation = self.d.open()
        self.d.map(0, PAGE)
        self.d.map(1, RX_BYTES)

    def rejected(self, errno, method, *args, **kwargs):
        with self.assertRaises(Rejected) as result:
            method(*args, **kwargs)
        self.assertEqual(result.exception.errno, errno)

    def test_default_gate_fails_closed(self):
        d = Driver()
        d.open()
        d.map(1, RX_BYTES)
        self.rejected("EOPNOTSUPP", d.export, 0)
        self.assertEqual(d.gen.refs, 1)
        self.assertFalse(d.fds or d.reserved_fds)

    def test_gate_alone_cannot_enable_unaudited_backend(self):
        d = Driver(export_proven=True)
        gen = d.open()
        d.map(1, RX_BYTES)
        self.rejected("EOPNOTSUPP", d.export, 0)
        self.rejected("EOPNOTSUPP", d.begin, 0, gen)
        self.assertEqual(d.gen.refs, 1)

    def test_export_pending_blocks_reuse_and_rolls_back_core_failure(self):
        buf = self.d.reserve_export(0)
        self.assertEqual(self.d.gen.refs, 2)
        for method, args in ((self.d.open, ()), (self.d.unmap, (3,)),
                             (self.d.start_copy, (STRIDE, PIXELS)),
                             (self.d.mmap, (0x100000, PAGE)),
                             (self.d.export, (0,)), (self.d.export, (1,))):
            self.rejected("EBUSY", method, *args)
        self.rejected("EOPNOTSUPP", self.d.finish_export, buf, fail="export")
        self.assertFalse(self.d.gen.export_pending or self.d.reserved_fds)
        self.assertEqual(self.d.gen.refs, 1)

    def test_remove_between_core_export_and_delivery_revalidates(self):
        buf = self.d.reserve_export(0)
        self.d.remove()
        self.rejected("ENODEV", self.d.finish_export, buf)
        self.assertFalse(self.d.gen.export_pending or self.d.fds or self.d.reserved_fds)
        self.assertTrue(self.d.gen.quarantined)
        self.assertEqual(self.d.gen.refs, 2)  # owner plus quarantine

    def test_begin_pending_blocks_all_dma_and_mmap_until_commit(self):
        self.d.export(0)
        token = self.d.reserve_begin(0, self.generation)
        self.assertEqual(self.d.gen.refs, 3)
        for method, args in ((self.d.start_copy, (STRIDE, PIXELS)),
                             (self.d.mmap, (0x100000, PAGE)),
                             (self.d.unmap, (3,)), (self.d.export, (1,)),
                             (self.d.end, (0, self.generation, token))):
            self.rejected("EBUSY", method, *args)
        self.assertEqual(self.d.finish_begin(0), token)
        self.assertFalse(self.d.gen.begin_pending)
        self.assertEqual(self.d.gen.refs, 2)
        self.d.start_copy(STRIDE, PIXELS)  # only slot overlap remains blocked
        self.d.complete_copy()

    def test_last_export_close_during_begin_rolls_back_delivery(self):
        fd = self.d.export(0)["fd"]
        self.d.reserve_begin(0, self.generation)
        self.d.close_export(fd)
        self.rejected("ENXIO", self.d.finish_begin, 0)
        self.assertFalse(self.d.gen.leases or self.d.gen.begin_pending)
        self.assertEqual(self.d.gen.refs, 1)

    def test_remove_during_begin_delivery_drops_pending_pin_not_quarantine(self):
        self.d.export(0)
        self.d.reserve_begin(0, self.generation)
        self.d.remove()
        self.rejected("ENODEV", self.d.finish_begin, 0)
        self.assertFalse(self.d.gen.begin_pending or self.d.gen.leases)
        self.assertTrue(self.d.gen.quarantined)
        self.assertEqual(self.d.gen.refs, 3)  # owner, export, quarantine

    def test_dma32_both_directions_reject_high_or_crossing_intervals(self):
        for rx, attr in ((False, "tx_dma"), (True, "rx_dma")):
            with self.subTest(rx=rx):
                setattr(self.d.gen, attr, 0x100000000)
                self.rejected("EOVERFLOW", self.d.start_copy, 0, 4, rx=rx)
                setattr(self.d.gen, attr, 0xfffffffc)
                self.rejected("EOVERFLOW", self.d.start_copy, 0, 8, rx=rx)
                self.d.start_copy(0, 4, rx=rx)
                self.d.complete_copy()
        self.assertFalse(self.d.active)

    def test_dma32_allocation_rejects_entire_out_of_range_buffer(self):
        self.d.unmap(3)
        for direction, attr in ((0, "tx_dma"), (1, "rx_dma")):
            setattr(self.d.gen, attr, 0xfffff000)
            self.rejected("EOVERFLOW", self.d.map, direction, PAGE + 4)
            self.d.map(direction, PAGE)

    def test_exclusive_second_open_does_not_reset_active(self):
        self.d.start_copy(0, PIXELS)
        self.rejected("EBUSY", self.d.open)
        self.assertTrue(self.d.active)
        self.d.complete_copy()

    def test_six_bounded_exports_and_no_duplicate_object(self):
        for slot in range(6):
            result = self.d.export(slot)
            self.assertEqual(result["offset"], slot * STRIDE)
            self.assertEqual(result["length"], PIXELS)
            self.assertEqual(result["generation"], self.generation)
            self.assertEqual(result["reserved"], 0)
            self.rejected("EBUSY", self.d.export, slot)
        self.rejected("EINVAL", self.d.export, 6)
        self.assertEqual(len(self.d.gen.exports), 6)

    def test_new_abi_validation(self):
        for kwargs in ({"version": 0}, {"flags": 1}, {"fd": 0}, {"offset": 1},
                       {"length": PIXELS}, {"generation": 1}, {"reserved": 1}):
            self.rejected("EINVAL", self.d.export, 0, **kwargs)
        self.assertEqual(self.d.gen.refs, 1)

    def test_export_requires_exact_4m_rx(self):
        self.d.unmap(1)
        self.d.map(1, PIXELS)
        self.rejected("EOPNOTSUPP", self.d.export, 0)

    def test_export_failure_unwinds_reservation_and_refs(self):
        for fail, errno in (("reserve", "EMFILE"), ("allocate", "ENOMEM"),
                            ("pages", "EOPNOTSUPP"), ("export", "EOPNOTSUPP"),
                            ("copy_to_user", "EFAULT")):
            with self.subTest(fail=fail):
                self.rejected(errno, self.d.export, 0, fail=fail)
                self.assertFalse(self.d.fds or self.d.reserved_fds or self.d.gen.exports)
                self.assertEqual(self.d.gen.refs, 1)
                self.assertEqual((self.d.module_pins, self.d.device_pins), (1, 1))
        self.d.unmap(3)  # no stuck process mutex/resource lock after EFAULT

    def test_unmap_blocks_both_buffers_while_exported(self):
        fd = self.d.export(0)["fd"]
        for direction in (0, 1, 3):
            self.rejected("EBUSY", self.d.unmap, direction)
        self.d.close_export(fd)
        self.d.unmap(3)
        self.assertEqual((self.d.gen.tx, self.d.gen.rx), (0, 0))

    def test_device_close_retains_tx_rx_device_and_module(self):
        fd = self.d.export(0)["fd"]
        self.d.close_device()
        self.assertFalse(self.d.gen.owned)
        self.assertEqual((self.d.gen.tx, self.d.gen.rx), (PAGE, RX_BYTES))
        self.assertEqual((self.d.module_pins, self.d.device_pins), (2, 1))
        self.rejected("EBUSY", self.d.open)
        self.d.close_export(fd)
        self.assertIsNone(self.d.gen)
        self.assertEqual((self.d.module_pins, self.d.device_pins), (0, 0))
        self.assertGreater(self.d.open(), self.generation)

    def test_dup_fd_and_importer_keep_object_alive(self):
        fd = self.d.export(0)["fd"]
        dup = self.d.dup_export(fd)
        buf = self.d.attach(fd, "rga")
        mapping = self.d.map_attachment(buf, "rga")
        self.d.close_export(fd)
        self.d.close_export(dup)
        self.d.close_device()
        self.assertIsNotNone(self.d.gen)
        self.d.unmap_attachment(buf, mapping)
        self.d.detach(buf, "rga")
        self.assertIsNone(self.d.gen)

    def test_mmap_fork_pins_and_defers_file_release(self):
        self.d.mmap(0x100000, RX_BYTES)
        self.d.fork_vma()
        self.rejected("EBUSY", self.d.unmap, 3)
        self.d.close_device()
        self.assertTrue(self.d.gen.owned)  # VMA vm_file still holds open description
        self.d.close_vma()
        self.rejected("EBUSY", self.d.open)
        self.d.close_vma()
        self.assertIsNone(self.d.gen)

    def test_mmap_bounds_and_no_untrusted_offset_shift(self):
        for offset, size in ((-PAGE, PAGE), (1 << 63, PAGE), (0x100001, PAGE),
                             (0x100000, RX_BYTES + PAGE), (0, 0)):
            self.rejected("EINVAL", self.d.mmap, offset, size)
        self.assertEqual(self.d.gen.vmas, 0)

    def test_close_syscall_race_defers_final_release(self):
        self.d.enter_syscall()
        self.d.start_copy(0, PIXELS)
        self.d.close_device()
        self.assertTrue(self.d.gen.owned)
        self.d.complete_copy()
        self.d.leave_syscall()
        self.assertIsNone(self.d.gen)

    def test_copy_and_lease_linearizations(self):
        for order in itertools.permutations(("copy", "begin")):
            with self.subTest(order=order):
                d = Driver(export_proven=True, backend_audited=True)
                gen = d.open()
                d.map(1, RX_BYTES)
                d.export(0)
                if order[0] == "copy":
                    d.start_copy(0, PIXELS)
                    self.rejected("EBUSY", d.begin, 0, gen)
                    d.complete_copy()
                    d.begin(0, gen)
                else:
                    d.begin(0, gen)
                    self.rejected("EBUSY", d.start_copy, 0, PIXELS)

    def test_all_slot_boundaries_tag_scratch_and_neighbors(self):
        for slot in range(6):
            fd = self.d.export(slot)["fd"]
            token = self.d.begin(slot, self.generation)
            start = slot * STRIDE
            for offset, length in ((start, PIXELS), (start + PIXELS - 4, 8), (0, RX_BYTES)):
                self.rejected("EBUSY", self.d.start_copy, offset, length)
            for offset, length in ((start + PIXELS, 16), (0x3ff000, 16)):
                self.d.start_copy(offset, length)
                self.d.complete_copy()
            if slot < 5:
                self.d.start_copy((slot + 1) * STRIDE, PIXELS)
                self.d.complete_copy()
            self.d.end(slot, self.generation, token)
            self.d.close_export(fd)

    def test_copy_bounds_alignment_and_h2f_independence(self):
        self.d.export(0)
        self.d.begin(0, self.generation)
        self.d.start_copy(0, PAGE, rx=False)
        self.d.complete_copy()
        for offset, length in ((0, 0), (RX_BYTES, 4), (RX_BYTES - 4, 8),
                               (1, 4), (0, 3), (0xffffffff, 8)):
            self.rejected("EINVAL", self.d.start_copy, offset, length)

    def test_lease_generation_token_and_copyout_rollback(self):
        self.d.export(0)
        self.rejected("EINVAL", self.d.begin, 0, self.generation + 1)
        self.rejected("EFAULT", self.d.begin, 0, self.generation, fail_copy=True)
        self.assertFalse(self.d.gen.leases)
        token = self.d.begin(0, self.generation)
        self.rejected("EBUSY", self.d.begin, 0, self.generation)
        self.rejected("EINVAL", self.d.end, 0, self.generation, token + 1)
        self.d.end(0, self.generation, token)
        self.rejected("EINVAL", self.d.end, 0, self.generation, token)
        self.assertGreater(self.d.begin(0, self.generation), token)

    def test_fd_close_never_proves_lease_completion(self):
        fd = self.d.export(0)["fd"]
        token = self.d.begin(0, self.generation)
        self.d.close_export(fd)
        self.rejected("EBUSY", self.d.unmap, 3)
        self.rejected("EBUSY", self.d.export, 0)
        self.d.end(0, self.generation, token)
        self.d.unmap(3)

    def test_owner_death_in_lease_quarantines_even_after_all_fds_close(self):
        fd = self.d.export(0)["fd"]
        self.d.begin(0, self.generation)
        self.d.close_device()
        self.d.close_export(fd)
        self.assertTrue(self.d.gen.quarantined)
        self.assertEqual(self.d.gen.refs, 1)
        self.assertFalse(self.d.freed)
        self.rejected("EBUSY", self.d.open)

    def test_timeout_or_signal_after_dma_submission_quarantines(self):
        self.d.start_copy(0, PIXELS)
        self.d.fail_copy()
        self.rejected("EIO", self.d.unmap, 3)
        self.d.complete_copy()  # late MSI cannot reverse a failed proof
        self.d.close_device()
        self.assertTrue(self.d.gen.quarantined)
        self.assertFalse(self.d.freed)

    def test_attach_failure_no_ref_leak(self):
        fd = self.d.export(0)["fd"]
        self.rejected("EOPNOTSUPP", self.d.attach, fd, "rga", fail=True)
        self.assertEqual(self.d.fds[fd].refs, 1)
        self.assertEqual(self.d.device_pins, 1)

    def test_hypothetical_map_failure_and_merged_nents_cleanup(self):
        fd = self.d.export(0)["fd"]
        buf = self.d.attach(fd, "rga-real-device")
        self.rejected("EIO", self.d.map_attachment, buf, "rga-real-device", fail=True)
        self.assertFalse(buf.mappings)
        mapping = self.d.map_attachment(buf, "rga-real-device")
        self.assertEqual(buf.mappings[mapping][1:3], (150, 1))
        self.d.unmap_attachment(buf, mapping)
        self.assertEqual(self.d.sg_frees[-1], (150, "mapped"))
        self.d.detach(buf, "rga-real-device")
        self.d.close_export(fd)
        self.d.unmap(3)

    def test_source_direction_and_hypothetical_attachment_handoff(self):
        fd = self.d.export(0)["fd"]
        buf = self.d.attach(fd, "rga-real-device")
        self.rejected("EOPNOTSUPP", self.d.map_attachment, buf, "rga-real-device", "FROM_DEVICE")
        self.rejected("EOPNOTSUPP", self.d.map_attachment, buf, "rga-real-device", "BIDIRECTIONAL")
        self.d.map_attachment(buf, "rga-real-device", "TO_DEVICE")
        token = self.d.begin(0, self.generation)
        self.d.end(0, self.generation, token)
        self.assertEqual(self.d.syncs, [("rga-real-device", 0, "device"),
                                      ("rga-real-device", 0, "cpu")])

    def test_remove_with_active_copy_and_exports_retains_allocation(self):
        fd = self.d.export(0)["fd"]
        self.d.start_copy(0, PIXELS)
        self.d.remove()
        self.rejected("ENODEV", self.d.begin, 0, self.generation)
        self.rejected("ENODEV", self.d.start_copy, STRIDE, PIXELS)
        self.d.complete_copy()
        self.d.close_device()
        self.d.close_export(fd)
        self.assertTrue(self.d.gen.quarantined)
        self.assertEqual((self.d.gen.tx, self.d.gen.rx), (PAGE, RX_BYTES))
        self.assertFalse(self.d.freed)

    def test_remove_idle_backing_is_also_quarantined(self):
        self.d.remove()
        self.d.close_device()
        self.assertTrue(self.d.gen.quarantined)

    def test_remove_wakeup_before_remove_mutex_never_proves_dma_done(self):
        self.d.start_copy(0, PIXELS)
        # remove first marks dead/wakes waiters, but has not acquired the
        # process mutex to run quarantine/teardown. Close wins that mutex.
        self.d.dead = True
        self.d.close_device()
        self.assertTrue(self.d.active)
        self.assertTrue(self.d.gen.quarantined)
        self.assertFalse(self.d.freed)

    def test_remove_without_allocation_can_drop_generation(self):
        self.d.unmap(3)
        self.d.remove()
        self.d.close_device()
        self.assertIsNone(self.d.gen)

    def test_close_export_close_owner_interleavings(self):
        for order in itertools.permutations(("export", "owner")):
            d = Driver(export_proven=True, backend_audited=True)
            d.open()
            d.map(1, RX_BYTES)
            fd = d.export(0)["fd"]
            for action in order:
                d.close_export(fd) if action == "export" else d.close_device()
            self.assertIsNone(d.gen)
            self.assertEqual(len(d.freed), 1)


class ScatterGather(unittest.TestCase):
    def test_contiguous_and_fragmented_pages_match_all_slots(self):
        contiguous = [(0, RX_BYTES, 0)]
        fragmented = [(n * 11 + 10000, PAGE, 0) for n in range(RX_BYTES // PAGE)]
        uneven = [(1000, 3 * PAGE, 0), (2000, 151 * PAGE, 0),
                  (3000, RX_BYTES - 154 * PAGE, 0)]
        for slot in range(6):
            start = slot * STRIDE
            pages = slice_pages(contiguous, start, PIXELS)
            self.assertEqual(pages, list(range(start // PAGE, (start + PIXELS) // PAGE)))
            other = slice_pages(fragmented, start, PIXELS)
            self.assertEqual(other, [n * 11 + 10000 for n in pages])
            self.assertEqual(len(slice_pages(uneven, start, PIXELS)), 150)
            self.assertNotIn((start + PIXELS) // PAGE, pages)  # tag's page private
            self.assertNotIn(0x3ff000 // PAGE, pages)

    def test_bad_page_view_fails_closed(self):
        for entries, offset, length in (([(0, RX_BYTES, 1)], 0, PIXELS),
                                        ([(None, RX_BYTES, 0)], 0, PIXELS),
                                        ([(0, RX_BYTES - 1, 0)], 0, PIXELS),
                                        ([(0, PAGE, 0)], 0, PIXELS),
                                        ([(0, RX_BYTES, 0)], 1, PIXELS),
                                        ([(0, RX_BYTES, 0)], 0, PIXELS - 1)):
            with self.subTest(entries=entries, offset=offset, length=length):
                with self.assertRaises(Rejected):
                    slice_pages(entries, offset, length)


if __name__ == "__main__":
    unittest.main()
