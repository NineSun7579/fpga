"""Deterministic offline SPECIFICATION model, not kernel or hardware execution.

The C policy harness executes the actual shared range/UNMAP predicates. This
model explores resource ownership, syscall linearization and fault rollback.
"""
from dataclasses import dataclass, field

PAGE = 4096
RX_BYTES = 0x400000
STRIDE = 0x97000
PIXELS = 0x96000
SLOTS = 6


class Rejected(Exception):
    def __init__(self, errno):
        self.errno = errno
        super().__init__(errno)


def require(condition, errno):
    if not condition:
        raise Rejected(errno)


def valid(size, offset, length):
    return length > 0 and 0 <= offset <= size and length <= size - offset


def overlap(a, alen, b, blen):
    return a < b + blen and b < a + alen


def slice_pages(entries, offset, length):
    """entries: (first_page_number, byte_length, byte_offset), in SG order."""
    require(offset % PAGE == 0 and length > 0 and length % PAGE == 0,
            "EOPNOTSUPP")
    result = []
    skip = offset
    for page, size, byte_offset in entries:
        require(page is not None and byte_offset == 0 and size > 0 and
                size % PAGE == 0, "EOPNOTSUPP")
        if skip >= size:
            skip -= size
            continue
        pos = skip
        skip = 0
        available = min(size - pos, length - len(result) * PAGE)
        result.extend(page + n for n in range(pos // PAGE,
                                              (pos + available) // PAGE))
        if len(result) * PAGE == length:
            return result
    raise Rejected("EOPNOTSUPP")


@dataclass
class Buffer:
    slot: int
    refs: int = 1
    attached: dict = field(default_factory=dict)
    mappings: dict = field(default_factory=dict)


@dataclass
class Generation:
    id: int
    refs: int = 1  # file description's owning ref
    owned: bool = True
    vmas: int = 0
    tx: int = 0
    rx: int = 0
    tx_dma: int = 0x1000000
    rx_dma: int = 0x2000000
    exports: dict = field(default_factory=dict)
    leases: dict = field(default_factory=dict)
    export_pending: dict = field(default_factory=dict)
    begin_pending: dict = field(default_factory=dict)
    quarantined: bool = False


class Driver:
    def __init__(self, export_proven=False, backend_audited=False):
        self.proven = export_proven
        self.backend = backend_audited  # hypothetical test backend, never hardware proof
        self.gen = None
        self.next_id = 0
        self.next_token = 0
        self.device_fds = 0
        self.syscalls = 0
        self.active = False
        self.dead = False
        self.faulted = False
        self.module_pins = 0
        self.device_pins = 0
        self.freed = []
        self.next_fd = 10
        self.reserved_fds = set()
        self.fds = {}
        self.syncs = []
        self.sg_frees = []

    def open(self):
        require(not self.dead, "ENODEV")
        require(self.gen is None and not self.faulted, "EBUSY")
        self.next_id += 1
        self.gen = Generation(self.next_id)
        self.device_fds = 1
        self.module_pins += 1
        self.device_pins += 1
        return self.gen.id

    def live(self):
        require(not self.dead, "ENODEV")
        require(self.gen is not None and self.gen.owned, "EBADF")
        require(not self.faulted and not self.gen.quarantined, "EIO")

    def put_generation(self):
        g = self.gen
        g.refs -= 1
        if not g.refs:
            assert not (g.owned or g.exports or g.vmas or g.quarantined or
                        g.export_pending or g.begin_pending or g.leases)
            assert not self.active
            self.freed.append((g.id, g.tx, g.rx))
            self.gen = None
            self.module_pins -= 1
            self.device_pins -= 1

    def map(self, direction, size):
        self.live()
        require(direction in (0, 1) and 0 < size <= RX_BYTES, "EINVAL")
        require(not (self.active or self.gen.export_pending or self.gen.begin_pending), "EBUSY")
        attr = "rx" if direction else "tx"
        require(not getattr(self.gen, attr), "EBUSY")
        alloc_size = (size + PAGE - 1) // PAGE * PAGE
        require(valid(1 << 32, getattr(self.gen, attr + "_dma"), alloc_size), "EOVERFLOW")
        setattr(self.gen, attr, alloc_size)

    def unmap(self, direction):
        self.live()
        require(direction in (0, 1, 3), "EINVAL")
        g = self.gen
        require(not (g.exports or g.vmas or g.leases or g.export_pending or
                     g.begin_pending or self.active or g.quarantined),
                "EBUSY")
        if direction in (0, 3):
            g.tx = 0
        if direction in (1, 3):
            g.rx = 0

    def mmap(self, offset, length):
        self.live()
        require(offset in (0, 0x100000), "EINVAL")
        require(not (self.gen.export_pending or self.gen.begin_pending or self.gen.leases), "EBUSY")
        require(valid(self.gen.rx if offset else self.gen.tx, 0, length), "EINVAL")
        self.gen.vmas += 1
        self.gen.refs += 1

    def fork_vma(self):
        assert self.gen and self.gen.vmas
        self.gen.vmas += 1
        self.gen.refs += 1

    def close_vma(self):
        assert self.gen and self.gen.vmas
        self.gen.vmas -= 1
        self.put_generation()
        self.maybe_release_file()

    def enter_syscall(self):
        self.live()
        self.syscalls += 1

    def leave_syscall(self):
        self.syscalls -= 1
        self.maybe_release_file()

    def reserve_export(self, slot, fail=None, version=1, flags=0, fd=-1,
                       offset=0, length=0, generation=0, reserved=0):
        require(version == 1 and 0 <= slot < SLOTS and flags == 0 and fd == -1 and
                offset == length == generation == reserved == 0, "EINVAL")
        require(self.proven and self.backend, "EOPNOTSUPP")
        self.live()
        g = self.gen
        require(g.rx == RX_BYTES, "EOPNOTSUPP")
        require(slot not in g.exports and slot not in g.leases and not self.active and
                not g.export_pending and not g.begin_pending,
                "EBUSY")
        if fail == "reserve":
            raise Rejected("EMFILE")
        fd = self.next_fd
        self.next_fd += 1
        self.reserved_fds.add(fd)
        if fail in ("allocate", "pages"):
            self.reserved_fds.remove(fd)
            raise Rejected("ENOMEM" if fail == "allocate" else "EOPNOTSUPP")
        buf = Buffer(slot)
        g.export_pending[slot] = (fd, buf)
        g.refs += 1
        return buf

    def abort_export(self, buf, core_created=False):
        fd, _ = self.gen.export_pending.pop(buf.slot)
        self.reserved_fds.remove(fd)
        if core_created:
            self.module_pins -= 1
        self.put_generation()

    def finish_export(self, buf, fail=None):
        if fail == "export":
            self.abort_export(buf)
            raise Rejected("EOPNOTSUPP")
        self.module_pins += 1  # dma-buf core owner pin
        try:
            self.live()  # revalidate after dma_buf_export unlocked
        except Rejected:
            self.abort_export(buf, core_created=True)
            raise
        if fail == "copy_to_user":
            self.abort_export(buf, core_created=True)
            raise Rejected("EFAULT")
        fd, _ = self.gen.export_pending.pop(buf.slot)
        self.gen.exports[buf.slot] = buf
        self.reserved_fds.remove(fd)
        self.fds[fd] = buf
        return {"fd": fd, "offset": buf.slot * STRIDE, "length": PIXELS,
                "generation": self.gen.id, "reserved": 0}

    def export(self, slot, fail=None, **kwargs):
        buf = self.reserve_export(slot, fail=fail, **kwargs)
        return self.finish_export(buf, fail=fail)

    def put_buffer(self, buf):
        buf.refs -= 1
        if not buf.refs:
            assert not buf.mappings and not buf.attached
            del self.gen.exports[buf.slot]
            self.module_pins -= 1
            self.put_generation()

    def dup_export(self, fd):
        buf = self.fds[fd]
        buf.refs += 1
        new = self.next_fd
        self.next_fd += 1
        self.fds[new] = buf
        return new

    def close_export(self, fd):
        self.put_buffer(self.fds.pop(fd))

    def attach(self, fd, device, fail=False):
        self.live()
        require(self.backend, "EOPNOTSUPP")
        require(not fail, "EOPNOTSUPP")
        buf = self.fds[fd]
        require(device not in buf.attached, "EINVAL")
        buf.attached[device] = 0
        buf.refs += 1  # importer owns its dma-buf reference
        self.device_pins += 1
        return buf

    def map_attachment(self, buf, device, direction="TO_DEVICE", fail=False):
        self.live()
        require(device in buf.attached, "EINVAL")
        require(direction == "TO_DEVICE" and self.backend, "EOPNOTSUPP")
        require(not self.active and not self.gen.export_pending and
                not self.gen.begin_pending and buf.slot not in self.gen.leases, "EBUSY")
        # Distinct fresh SG object per map; DMA nents may merge, orig stays 150.
        mapping = len(self.sg_frees) + len(buf.mappings) + 1
        if fail:
            self.sg_frees.append((PIXELS // PAGE, "unmapped"))
            raise Rejected("EIO")
        buf.mappings[mapping] = (device, PIXELS // PAGE, 1, direction)
        buf.attached[device] += 1
        return mapping

    def unmap_attachment(self, buf, mapping):
        device, orig, merged, direction = buf.mappings.pop(mapping)
        self.sg_frees.append((orig, "mapped"))
        buf.attached[device] -= 1

    def detach(self, buf, device):
        require(buf.attached[device] == 0, "EBUSY")
        del buf.attached[device]
        self.device_pins -= 1
        self.put_buffer(buf)

    def reserve_begin(self, slot, generation):
        self.live()
        require(self.proven and self.backend, "EOPNOTSUPP")
        require(generation == self.gen.id and 0 <= slot < SLOTS, "EINVAL")
        require(slot in self.gen.exports, "ENXIO")
        require(not self.active and slot not in self.gen.leases and
                not self.gen.export_pending and not self.gen.begin_pending, "EBUSY")
        self.next_token += 1
        token = self.next_token
        self.gen.leases[slot] = token
        self.gen.begin_pending[slot] = token
        self.gen.refs += 1
        self.syncs.extend((mapping[0], slot, "device") for mapping in
                          self.gen.exports[slot].mappings.values())
        return token

    def finish_begin(self, slot, fail_copy=False):
        token = self.gen.begin_pending[slot]
        errno = "EFAULT" if fail_copy else None
        if not errno:
            try:
                self.live()
                require(slot in self.gen.exports, "ENXIO")
            except Rejected as error:
                errno = error.errno
        if errno:
            del self.gen.leases[slot]
            if slot in self.gen.exports:
                self.syncs.extend((mapping[0], slot, "cpu") for mapping in
                                  self.gen.exports[slot].mappings.values())
        del self.gen.begin_pending[slot]
        self.put_generation()
        if errno:
            raise Rejected(errno)
        return token

    def begin(self, slot, generation, fail_copy=False):
        self.reserve_begin(slot, generation)
        return self.finish_begin(slot, fail_copy=fail_copy)

    def end(self, slot, generation, token):
        self.live()
        require(self.proven and self.backend, "EOPNOTSUPP")
        require(not self.gen.export_pending and not self.gen.begin_pending, "EBUSY")
        require(generation == self.gen.id and token != 0 and
                self.gen.leases.get(slot) == token, "EINVAL")
        if slot in self.gen.exports:
            self.syncs.extend((mapping[0], slot, "cpu") for mapping in
                              self.gen.exports[slot].mappings.values())
        del self.gen.leases[slot]

    def start_copy(self, offset, length, rx=True):
        self.live()
        require(not self.active, "EBUSY")
        require(not self.gen.export_pending and not self.gen.begin_pending, "EBUSY")
        size = self.gen.rx if rx else self.gen.tx
        require(size > 0, "ENXIO")
        require(valid(size, offset, length) and (offset | length) & 3 == 0, "EINVAL")
        require(valid(1 << 32, (self.gen.rx_dma if rx else self.gen.tx_dma) + offset,
                      length), "EOVERFLOW")
        if rx:
            require(not any(overlap(offset, length, slot * STRIDE, PIXELS)
                            for slot in self.gen.leases), "EBUSY")
        self.active = True

    def complete_copy(self):
        self.active = False

    def fail_copy(self):
        # Timeout/interruption after submission is not a completed transaction.
        self.quarantine()

    def quarantine(self):
        self.faulted = True
        if not self.gen.quarantined:
            self.gen.quarantined = True
            self.gen.refs += 1

    def close_device(self):
        self.device_fds -= 1
        self.maybe_release_file()

    def maybe_release_file(self):
        if self.gen and self.gen.owned and not self.device_fds and not self.gen.vmas and not self.syscalls:
            if (self.active or self.gen.leases or self.gen.begin_pending or
                    self.gen.export_pending or (self.dead and (self.gen.tx or self.gen.rx))):
                self.quarantine()
            self.gen.owned = False
            self.put_generation()

    def remove(self):
        self.dead = True
        if self.gen and (self.gen.tx or self.gen.rx):
            self.quarantine()  # even an idle PCI allocator's domain may vanish
