#pragma once
#include <cstddef>
#include <cstring>
#include <vector>

namespace bypass {
// Xlib represents format-32 items as native unsigned longs, including on LP64.
struct Property {
    unsigned long type = 0;
    int format = 0;
    unsigned long count = 0;
    std::vector<unsigned char> bytes;
    std::vector<unsigned short> shorts;
    std::vector<unsigned long> longs;

    bool save(unsigned long t, int f, unsigned long n,
              unsigned long remaining, const unsigned char* data) {
        *this = Property{};
        if (remaining || (t && f != 8 && f != 16 && f != 32) ||
            (!t && n) || (n && !data) || n > 16384) return false;
        type = t; format = f; count = n;
        if (f == 8) bytes.resize(n);
        if (f == 16) shorts.resize(n);
        if (f == 32) longs.resize(n);
        if (n) std::memcpy(storage(), data, n * itemBytes());
        return true;
    }
    std::size_t itemBytes() const {
        return format == 32 ? sizeof(unsigned long) : format == 16 ? sizeof(unsigned short) : 1;
    }
    unsigned char* storage() {
        if (format == 32) return reinterpret_cast<unsigned char*>(longs.data());
        if (format == 16) return reinterpret_cast<unsigned char*>(shorts.data());
        return bytes.data();
    }
    const unsigned char* storage() const {
        if (format == 32) return reinterpret_cast<const unsigned char*>(longs.data());
        if (format == 16) return reinterpret_cast<const unsigned char*>(shorts.data());
        return bytes.data();
    }
    bool isHint(unsigned long cardinal) const {
        return type == cardinal && format == 32 && count == 1 && longs[0] == 1;
    }
};
}
