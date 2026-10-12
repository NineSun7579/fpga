#!/bin/bash
# Invoked only in the newly created evidence root. Never install or execute detview.
set -u
if [ -e build_return_code.txt ] || [ -e detview ] || [ -e main.o ]; then
    printf '%s\n' 'Refusing to reuse build products' >&2
    exit 97
fi
printf '%s\n' '/usr/lib/qt5/bin/qmake -o Makefile detview.pro -after TARGET=detview-native-current-candidate' > commands.txt
/usr/lib/qt5/bin/qmake -o Makefile detview.pro -after TARGET=detview-native-current-candidate > qmake.log 2>&1
rc=$?
if [ "$rc" -eq 0 ]; then
    cp Makefile Makefile.fresh
    printf '%s\n' "make -j2 CXX='g++ -MD' LINK='g++ -Wl,-t'" >> commands.txt
    make -j2 CXX='g++ -MD' LINK='g++ -Wl,-t' > compile_link.log 2>&1
    rc=$?
fi
printf '%s\n' "$rc" > build_return_code.txt
printf '{"build_return_code":%s}\n' "$rc"
exit 0
