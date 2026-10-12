"""Durable Linux generation allocator for a coordinated FPGA reset domain.

The journal is external to the FPGA and must survive board/process restarts.
This tool does NOT reset, ARM, access or identify a device. Bootstrap requires
an independently established upper bound on all generations ever used in the
domain. A lost/rolled-back journal cannot be recovered by inventing a new epoch.
"""
import argparse
from contextlib import contextmanager
import json
import os
from pathlib import Path
import secrets
import stat

MAX_EPOCH = 0xffffffff


def _require_linux():
    if os.name != 'posix' or not hasattr(os, 'O_NOFOLLOW') or not hasattr(os, 'O_DIRECTORY'):
        raise RuntimeError('allocator requires Linux file locks and durable directory fsync')


def _check_domain(domain):
    if not isinstance(domain, str) or not domain.strip() or len(domain) > 256:
        raise ValueError('explicit stable physical reset-domain identity required')


@contextmanager
def _locked(path):
    _require_linux()
    import fcntl
    directory_fd = os.open(str(path.parent), os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW)
    lock_fd = None
    try:
        lock_name = path.name + '.lock'
        lock_fd = os.open(lock_name, os.O_RDWR | os.O_CREAT | os.O_CLOEXEC | os.O_NOFOLLOW,
                          0o600, dir_fd=directory_fd)
        info = os.fstat(lock_fd)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise ValueError('lock must be one regular private file')
        fcntl.flock(lock_fd, fcntl.LOCK_EX)
        current = os.stat(lock_name, dir_fd=directory_fd, follow_symlinks=False)
        if (current.st_dev, current.st_ino) != (info.st_dev, info.st_ino):
            raise RuntimeError('lock identity changed')
        yield directory_fd
    finally:
        if lock_fd is not None:
            os.close(lock_fd)
        os.close(directory_fd)


def _read(directory_fd, name, domain):
    fd = os.open(name, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW, dir_fd=directory_fd)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > 4096:
            raise ValueError('journal must be one bounded regular file')
        with os.fdopen(fd, 'r', encoding='ascii', closefd=False) as stream:
            data = json.load(stream)
    finally:
        os.close(fd)
    if not isinstance(data, dict) or set(data) != {'format', 'domain', 'last_reserved'}:
        raise ValueError('invalid epoch journal schema')
    if type(data['format']) is not int or data['format'] != 1 or data['domain'] != domain:
        raise ValueError('journal format or physical reset domain differs')
    value = data['last_reserved']
    if type(value) is not int or not 0 <= value <= MAX_EPOCH:
        raise ValueError('invalid last reserved generation')
    return data


def _commit(directory_fd, name, data, create_only=False):
    temporary = '.' + name + '.' + secrets.token_hex(16) + '.pending'
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC,
                 0o600, dir_fd=directory_fd)
    try:
        payload = (json.dumps(data, sort_keys=True, ensure_ascii=True) + '\n').encode('ascii')
        with os.fdopen(fd, 'wb', closefd=False) as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(fd)
        if create_only:
            # Link prevents replacement even if another program ignores our lock.
            os.link(temporary, name, src_dir_fd=directory_fd, dst_dir_fd=directory_fd,
                    follow_symlinks=False)
            os.unlink(temporary, dir_fd=directory_fd)
        else:
            os.replace(temporary, name, src_dir_fd=directory_fd, dst_dir_fd=directory_fd)
        # Do not expose the epoch before the directory entry is durable.
        os.fsync(directory_fd)
    finally:
        os.close(fd)
        try:
            os.unlink(temporary, dir_fd=directory_fd)
        except FileNotFoundError:
            pass


def initialize(path, domain, last_reserved):
    """Explicit provisioning; caller certifies an unused domain or valid bound."""
    path = Path(path)
    _check_domain(domain)
    if type(last_reserved) is not int or not 0 <= last_reserved <= MAX_EPOCH:
        raise ValueError('explicit independently established upper bound required')
    with _locked(path) as directory_fd:
        _commit(directory_fd, path.name, {'format': 1, 'domain': domain,
            'last_reserved': last_reserved}, create_only=True)


def allocate(path, domain):
    """Reserve one new nonzero epoch durably; burned epochs are never reused."""
    path = Path(path)
    _check_domain(domain)
    with _locked(path) as directory_fd:
        data = _read(directory_fd, path.name, domain)
        if data['last_reserved'] == MAX_EPOCH:
            raise OverflowError('generation domain exhausted; never wrap or reinitialize it')
        data['last_reserved'] += 1
        _commit(directory_fd, path.name, data)
        return data['last_reserved']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('journal', type=Path)
    parser.add_argument('--domain', required=True)
    command = parser.add_mutually_exclusive_group(required=True)
    command.add_argument('--allocate', action='store_true')
    command.add_argument('--initialize-last-reserved', type=int)
    args = parser.parse_args()
    if args.allocate:
        print(allocate(args.journal, args.domain))
    else:
        initialize(args.journal, args.domain, args.initialize_last_reserved)
        print('EPOCH_JOURNAL_INITIALIZED')


if __name__ == '__main__':
    main()
