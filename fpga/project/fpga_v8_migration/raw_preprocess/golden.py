"""Independent integer RGB565/NHWC reference; no RTL-derived bit slices."""
from pathlib import Path


def rgb565(pixel):
    r = (pixel // 2048) % 32
    g = (pixel // 32) % 64
    b = pixel % 32
    return bytes(((r * 8) | (r // 4), (g * 4) | (g // 16),
                  (b * 8) | (b // 4)))


def source_pixels(count, frame):
    # Odd multiplication permutes all 65536 words. Include primaries and the
    # literal ASCII KF word 0x464b to catch accidental RAW metadata filtering.
    special = [0xf800, 0x07e0, 0x001f, 0x464b, 0xffff, 0x0000, 0x0821]
    return [special[(i + frame) % len(special)] if i < len(special)
            else ((i * 40503 + frame * 7919 + 12345) & 65535)
            for i in range(count)]


def letterbox(pixels, width, height, out_height, top, fill=114):
    if not (1 <= width <= 65535 and 1 <= height <= out_height <= 65535
            and 0 <= top <= out_height - height and 0 <= fill <= 255):
        raise ValueError("Invalid letterbox geometry/fill")
    if len(pixels) != width * height:
        raise ValueError("Source pixel count differs from geometry")
    pad_row = bytes([fill]) * (width * 3)
    body = b"".join(rgb565(p) for p in pixels)
    return pad_row * top + body + pad_row * (out_height - height - top)


def packed_words(frame):
    result = []
    for offset in range(0, len(frame), 16):
        chunk = frame[offset:offset + 16]
        result.append((int.from_bytes(chunk, "little"),
                       (1 << len(chunk)) - 1,
                       int(offset + len(chunk) == len(frame))))
    return result


def write_hex(path, values, digits):
    Path(path).write_text("".join(f"{v:0{digits}x}\n" for v in values),
                          encoding="ascii")


def self_check():
    assert rgb565(0xf800) == bytes([255, 0, 0])
    assert rgb565(0x07e0) == bytes([0, 255, 0])
    assert rgb565(0x001f) == bytes([0, 0, 255])
    assert rgb565(0x0821) == bytes([8, 4, 8])
    assert rgb565(0x464b) == bytes([66, 203, 90])
    assert packed_words(bytes(range(18))) == [
        (int.from_bytes(bytes(range(16)), "little"), 65535, 0),
        (0x1110, 3, 1)]
