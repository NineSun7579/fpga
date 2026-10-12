"""Extract exact ASCII C function/struct bodies for local lock/event execution.

No kernel shim build is claimed: allocator/core/MM/IRQ operations are assertions
and mocks. Production source is never preprocessed with a changed export gate.
"""
import hashlib
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent


def extract_braced(source, name, function=True):
    pattern = (rb"^static [^\n]*\b" + name.encode("ascii") + rb"\s*\(" if function
               else rb"^(?:struct|union) " + name.encode("ascii") + rb"\s*\{")
    match = re.search(pattern, source, re.MULTILINE)
    if not match:
        raise ValueError("Missing extraction: " + name)
    start = source.index(b"{", match.start())
    depth = 1
    pos = start + 1
    # Tokenize comments and quoted strings before counting braces.
    token = re.compile(rb'/\*.*?\*/|//[^\n]*|"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|[{}]', re.S)
    for match_token in token.finditer(source, pos):
        item = match_token.group()
        if item == b"{":
            depth += 1
        elif item == b"}":
            depth -= 1
            if not depth:
                end = match_token.end() + (0 if function else 1)
                return source[match.start():end] + b"\n"
    raise ValueError("Unbalanced extraction: " + name)


def generate(directory):
    directory = Path(directory)
    source = (HERE / "pango_dma_candidate.c").read_bytes()
    groups = {
        "extracted_types.h": [(name, False) for name in
                              ("pango_buffer", "pango_generation", "pango_attachment",
                               "pango_mapping", "pango_view", "pango_ioctl_request")],
        "extracted_backend.h": [(name, True) for name in
                                ("pango_import_backend_ready", "pango_backend_map", "pango_sync_slot")],
        "extracted_driver.h": [(name, True) for name in
                               ("pango_free_buffer", "pango_live", "pango_map_legacy",
                                "pango_unmap_legacy", "pango_transfer", "pango_buf_map",
                                "pango_buf_release", "pango_reserved_zero", "pango_export_ioctl",
                                "pango_lease_ioctl", "pango_ioctl", "pango_mmap")],
    }
    hashes = {}
    for filename, entries in groups.items():
        parts = []
        for name, function in entries:
            part = extract_braced(source, name, function=function)
            hashes[name] = hashlib.sha256(part).hexdigest()
            parts.append(part)
        (directory / filename).write_bytes(b"\n".join(parts))
    return {"source_sha256": hashlib.sha256(source).hexdigest(),
            "extracted_sha256": hashes,
            "scope": "Exact candidate function bodies with mocked kernel events; no kernel/hardware execution"}
