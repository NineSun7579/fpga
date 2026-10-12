#include "bypass_property.h"
#include <cassert>
#include <cstdio>

int main() {
    bypass::Property p;
    assert(p.save(0, 0, 0, 0, nullptr) && !p.type);
    const unsigned char bytes[] = {0, 255, 12};
    assert(p.save(7, 8, 3, 0, bytes) && p.bytes[1] == 255 && p.count == 3);
    const unsigned short shorts[] = {0, 65535};
    assert(p.save(8, 16, 2, 0, reinterpret_cast<const unsigned char*>(shorts)));
    assert(p.shorts[1] == 65535 && p.itemBytes() == sizeof(unsigned short));
    const unsigned long values[] = {1, 0xffffffffUL};
    assert(p.save(6, 32, 2, 0, reinterpret_cast<const unsigned char*>(values)));
    assert(p.longs[1] == 0xffffffffUL && p.itemBytes() == sizeof(unsigned long));
    assert(!p.isHint(6)); // Extra items are not our hint.
    assert(p.save(6, 32, 1, 0, reinterpret_cast<const unsigned char*>(values)) && p.isHint(6));
    assert(!p.isHint(7));
    const unsigned long changed = 2;
    assert(p.save(6, 32, 1, 0, reinterpret_cast<const unsigned char*>(&changed)));
    assert(!p.isHint(6)); // An external change must skip conditional restoration.
    const unsigned char byteOne = 1;
    assert(p.save(6, 8, 1, 0, &byteOne) && !p.isHint(6));
    assert(!p.save(6, 32, 1, 4, reinterpret_cast<const unsigned char*>(values)));
    assert(!p.save(6, 24, 1, 0, bytes));
    assert(!p.save(6, 32, 1, 0, nullptr));
    assert(p.save(9, 8, 0, 0, nullptr) && p.type == 9 && p.count == 0);
    std::puts("BYPASS_PROPERTY_SELFTEST_PASS");
}
