#!/bin/sh
set -eu
export DETVIEW_EGL_METADATA=1
src=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
out=$(mktemp -d)
trap 'rm -rf "$out"' EXIT HUP INT TERM
cc=${CC:-gcc}
flags='-std=c11 -O2 -Wall -Wextra -Werror'
$cc $flags -shared -fPIC "$src/egl_probe.c" -o "$out/libegl_probe.so" -ldl -lpthread
$cc $flags -shared -fPIC "$src/fake_egl.c" -o "$out/libfake_egl.so" -ldl
$cc $flags -shared -fPIC "$src/fake_core_egl.c" -o "$out/libfake_core_egl.so"
$cc $flags "$src/probe_selftest.c" -L"$out" -Wl,-rpath,"$out" -lfake_egl -o "$out/test"
$cc $flags "$src/local_selftest.c" -o "$out/local_test" -ldl
ulimit -c 0
DETVIEW_EGL_TRACE=1 LD_PRELOAD="$out/libegl_probe.so" "$out/test" enabled 2>"$out/enabled.log"
grep -q '\[egl-call\] interval=0 success=1' "$out/enabled.log"
grep -q '\[egl-call\] interval=1 success=0' "$out/enabled.log"
grep -q 'window_s=.*mean_ms=3000.000 max_ms=3000.000' "$out/enabled.log"
grep -q 'surface EGL_SWAP_BEHAVIOR success=0' "$out/enabled.log"
grep -q 'config_id_matched=1' "$out/enabled.log"
test "$(grep -c '\[egl-probe\] init ' "$out/enabled.log")" = 1
test "$(grep -c '\[egl-call\] interval=' "$out/enabled.log")" = 2
DETVIEW_EGL_TRACE=0 LD_PRELOAD="$out/libegl_probe.so" "$out/test" 2>"$out/off.log"
test ! -s "$out/off.log"
env -u DETVIEW_EGL_TRACE LD_PRELOAD="$out/libegl_probe.so" "$out/test" 2>"$out/unset.log"
test ! -s "$out/unset.log"
DETVIEW_EGL_TRACE=1 DETVIEW_EGL_METADATA=0 LD_PRELOAD="$out/libegl_probe.so" "$out/test" enabled 2>"$out/no_metadata.log"
grep -q '\[egl-call\] interval=0 success=1' "$out/no_metadata.log"
if grep -q '\[egl-probe\] init' "$out/no_metadata.log"; then
    echo 'FAIL: metadata without opt-in'; exit 1
fi
# Late RTLD_GLOBAL is visible at first call, unlike constructor-time resolution.
DETVIEW_EGL_TRACE=1 LD_PRELOAD="$out/libegl_probe.so" "$out/local_test" "$out/libfake_egl.so" global 2>"$out/global.log"
grep -q 'resolver scope=RTLD_NEXT' "$out/global.log"
# RTLD_LOCAL requires an authoritative provider; all queries use that handle.
DETVIEW_EGL_TRACE=1 DETVIEW_EGL_PROVIDER="$out/libfake_egl.so" LD_PRELOAD="$out/libegl_probe.so" "$out/local_test" "$out/libfake_egl.so" local 2>"$out/local.log"
grep -q 'resolver scope=explicit-loaded-provider' "$out/local.log"
grep -q 'config_id_matched=1' "$out/local.log"
FAKE_CORE_EGL="$out/libfake_core_egl.so" DETVIEW_EGL_TRACE=1 DETVIEW_EGL_PROVIDER="$out/libfake_egl.so" LD_PRELOAD="$out/libegl_probe.so" "$out/local_test" "$out/libfake_egl.so" local 2>"$out/dispatch.log"
grep -q 'current display_matches=1 draw_matches=1 context_present=1' "$out/dispatch.log"
grep -q 'vendor success=1 value=fake vendor' "$out/dispatch.log"
DETVIEW_EGL_TRACE=0 DETVIEW_EGL_PROVIDER="$out/libfake_egl.so" LD_PRELOAD="$out/libegl_probe.so" "$out/local_test" "$out/libfake_egl.so" local 2>"$out/local_off.log"
test ! -s "$out/local_off.log"
# Missing/unloaded providers must terminate explicitly, never fake EGL_FALSE.
if DETVIEW_EGL_TRACE=1 LD_PRELOAD="$out/libegl_probe.so" "$out/local_test" "$out/libfake_egl.so" local 2>"$out/missing.log"; then
    echo 'FAIL: unresolved local provider returned normally'; exit 1
fi
grep -q 'fatal forwarding unavailable' "$out/missing.log"
if DETVIEW_EGL_TRACE=1 DETVIEW_EGL_PROVIDER="$out/libfake_egl.so" LD_PRELOAD="$out/libegl_probe.so" "$out/local_test" "$out/libfake_egl.so" missing 2>"$out/unloaded.log"; then
    echo 'FAIL: unloaded provider returned normally'; exit 1
fi
grep -q 'selected provider is not loaded' "$out/unloaded.log"
cat "$out/enabled.log"
echo 'PASS: aggregation, metadata, gating, late global/local providers, explicit resolution failures'
