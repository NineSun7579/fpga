#!/bin/sh
# Dependency/link tracing only; original compiler optimization/ABI flags retained.
exec make CXX='g++ -MD' LINK='g++ -Wl,-t' "$@"
