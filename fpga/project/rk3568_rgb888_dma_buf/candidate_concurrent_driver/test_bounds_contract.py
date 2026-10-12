"""Host arithmetic and source-contract checks; no kernel/hardware emulation."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parent
HEADER = (ROOT / 'pango_zc_uapi.h').read_bytes()
SOURCE = (ROOT / 'pango_zc.c').read_bytes()


def constant(name):
    return int(re.search(rb'#define ' + name.encode() + rb' (0x[0-9a-fA-F]+|[0-9]+)U', HEADER)[1], 0)


SIZE = constant('PZ_BUFFER_BYTES')
OFFSET = constant('PZ_INPUT_OFFSET')
RESERVE = constant('PZ_INPUT_BYTES')
CROP = constant('PZ_MVP_INPUT_BYTES')


def range_ok(size, off, length):
    # Arithmetic contract of the driver's subtraction-based range_ok.
    return bool(length and off <= size and length <= size - off)


class BoundsContract(unittest.TestCase):
    def test_layout(self):
        self.assertEqual((SIZE, OFFSET, RESERVE, CROP),
                         (0x800000, 0x400000, 1228800, 921600))
        self.assertEqual(OFFSET % 4096, 0)
        self.assertLessEqual(6 * 0x97000, 0x3ff000)
        self.assertEqual(0x3ff000 + 4096, OFFSET)
        self.assertEqual(OFFSET + RESERVE, 0x52c000)
        self.assertTrue(range_ok(SIZE, OFFSET, RESERVE))
        self.assertTrue(range_ok(SIZE, OFFSET, CROP))
        self.assertEqual(80 * 640 * 3, 153600)
        self.assertEqual(480 * 640 * 3, CROP)

    def test_per_allocation_bounds(self):
        for size in (4096, 0x100000, 0x400000, SIZE):
            self.assertTrue(range_ok(size, size - 4, 4))
            for off, length in ((size, 4), (size - 4, 8),
                                (0, 0), (0xffffffff, 4), (4, 0xffffffff)):
                self.assertFalse(range_ok(size, off, length))
        self.assertFalse(range_ok(0x400000, OFFSET, CROP))
        self.assertIn(b'return bytes && off <= size && bytes <= size - off;', SOURCE)
        self.assertIn(b'range_ok(b->size, op->offset_addr, op->total_length)', SOURCE)
        self.assertIn(b'bytes > b->size - vma->vm_pgoff * PAGE_SIZE', SOURCE)

    def test_address_ceiling(self):
        last_base = (1 << 32) - SIZE
        self.assertEqual(last_base + SIZE, 1 << 32)
        self.assertGreater(last_base + 4096 + SIZE, 1 << 32)
        self.assertIn(b'(u64)b->dma + bytes > (1ULL << 32)', SOURCE)
        self.assertIn(b'(u64)addr + op->total_length > (1ULL << 32)', SOURCE)
        self.assertIn(b'dma_set_mask_and_coherent(&dev->dev, DMA_BIT_MASK(32))', SOURCE)

    def test_export_covers_all_pages(self):
        self.assertEqual(SIZE // 4096, 2048)
        for fragment_pages in (1, 16, 256, 2048):
            pages = [page for start in range(0, 2048, fragment_pages)
                     for page in range(start, min(start + fragment_pages, 2048))]
            self.assertEqual(pages, list(range(2048)))
        for guard in (b'g->rx.size != PZ_BUFFER_BYTES',
                      b'PZ_BUFFER_BYTES / PAGE_SIZE',
                      b'total >= PZ_BUFFER_BYTES', b'return total == PZ_BUFFER_BYTES;',
                      b'phys != sg_phys(page_sg) + page_pos',
                      b'info.size = PZ_BUFFER_BYTES;',
                      b'PAGE_SIZE != 4096'):
            self.assertIn(guard, SOURCE)

    def test_producer_and_lease_source_contract(self):
        self.assertIn(b'q->offset == PZ_INPUT_OFFSET', SOURCE)
        self.assertIn(b'q->length == PZ_INPUT_BYTES', SOURCE)
        self.assertIn(b'op->offset_addr == PZ_INPUT_OFFSET', SOURCE)
        self.assertIn(b'op->total_length == PZ_MVP_INPUT_BYTES', SOURCE)
        self.assertIn(b'g->ready_length = PZ_INPUT_BYTES;', SOURCE)
        self.assertIn(b'g->ready_offset != q->offset || g->ready_length != q->length', SOURCE)
        transfer = SOURCE.split(b'static int transfer(', 1)[1].split(b'static int get_pages(', 1)[0]
        guard = transfer.index(b'if (g->pending || (rx && cpu_busy(g)) ||')
        self.assertLess(guard, transfer.index(b'iowrite32('))

    def test_abi_unchanged(self):
        self.assertEqual(constant('PZ_RX_MMAP_OFFSET'), 0x100000)
        self.assertEqual(constant('PZ_VERSION'), 1)
        for line in (b'#define PZ_MAP _IOWR(0x53, 2, int)',
                     b'#define PZ_H2F _IOWR(0x53, 4, int)',
                     b'#define PZ_F2H _IOWR(0x53, 5, int)',
                     b'#define PZ_UNMAP _IOWR(0x53, 7, int)',
                     b'#define PZ_EXPORT_RX _IOW(0x53, 0x30, struct pz_export_rx)',
                     b'#define PZ_BEGIN _IOWR(0x53, 0x31, struct pz_lease)',
                     b'#define PZ_END _IOW(0x53, 0x32, struct pz_lease)'):
            self.assertIn(line, HEADER)
        for name, size in ((b'pz_dma_op', 20), (b'pz_export_rx', 16), (b'pz_lease', 40)):
            self.assertIn(b'BUILD_BUG_ON(sizeof(struct ' + name + b') != ' + str(size).encode() + b');', SOURCE)

    def test_lifetime_protections_present(self):
        for guard in (b'g->pending || g->exported || g->mapped || g->token || cpu_busy(g)',
                      b'g->token || g->pending || cpu_busy(g) || atomic_read(&pz.active)',
                      b'quarantine(g);', b'g->mapped = true;',
                      b'dma_unmap_sgtable(att->dev, &m->table, dir, PZ_MAP_ATTRS)'):
            self.assertIn(guard, SOURCE)


if __name__ == '__main__':
    unittest.main(verbosity=2)
