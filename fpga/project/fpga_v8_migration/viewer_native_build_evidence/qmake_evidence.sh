#!/bin/sh
# The immutable .pro sets TARGET itself; apply the intended override afterward.
exec /usr/lib/qt5/bin/qmake "$@" -after 'TARGET=detview-native-candidate'
