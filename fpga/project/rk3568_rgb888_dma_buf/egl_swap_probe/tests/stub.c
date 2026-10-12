#define _GNU_SOURCE
#include "../egl_abi.h"
#include <assert.h>
#include <errno.h>
#include <stdint.h>
#include <stdatomic.h>
#include <string.h>
#include <time.h>

atomic_uint stub_swaps, stub_intervals, clock_calls;
atomic_ullong clock_value;
atomic_ullong clock_step = 25000000ULL;
int fail_clock_call, recursive, alternate_proc;
_Thread_local int nesting;
_Thread_local EGLBoolean stub_return = 7;
extern void nested_swap(void);
static void unrelated(void) {}
static EGLBoolean alternate(EGLDisplay d, EGLSurface s)
{ (void)d; (void)s; return 77; }

EGLBoolean EGLAPIENTRY eglSwapBuffers(EGLDisplay display, EGLSurface surface)
{
    assert(display == (void *)(uintptr_t)0x1234);
    assert(surface == (void *)(uintptr_t)0x5678);
    assert(errno == EDOM);
    atomic_fetch_add(&stub_swaps, 1);
    if (recursive && !nesting) {
        nesting = 1;
        nested_swap();
        nesting = 0;
    }
    errno = ERANGE;
    return stub_return; /* Exercise exact return, not boolean normalization. */
}
EGLBoolean EGLAPIENTRY eglSwapInterval(EGLDisplay display, EGLint interval)
{
    assert(display == (void *)(uintptr_t)0x1234);
    assert(errno == EDOM);
    atomic_fetch_add(&stub_intervals, 1);
    errno = EACCES;
    return interval == -3 ? 0 : 9;
}
__eglMustCastToProperFunctionPointerType EGLAPIENTRY eglGetProcAddress(const char *name)
{
    assert(errno == EDOM);
    errno = ENOTTY;
    if (!strcmp(name, "eglSwapBuffers"))
        return (__eglMustCastToProperFunctionPointerType)(alternate_proc ? alternate : eglSwapBuffers);
    if (!strcmp(name, "eglSwapInterval"))
        return (__eglMustCastToProperFunctionPointerType)eglSwapInterval;
    if (!strcmp(name, "unrelated")) return unrelated;
    return 0;
}
/* If the probe ever consumes EGL errors or queries config, tests abort. */
EGLint eglGetError(void) { assert(!"eglGetError must not be called"); return 0; }
EGLBoolean eglQuerySurface(void) { assert(!"query forbidden"); return 0; }
EGLBoolean eglGetConfigAttrib(void) { assert(!"query forbidden"); return 0; }
int probe_test_clock(clockid_t id, struct timespec *ts)
{
    unsigned call = atomic_fetch_add(&clock_calls, 1) + 1;
    unsigned long long ns;
    assert(id == CLOCK_MONOTONIC);
    if ((int)call == fail_clock_call) { errno = EIO; return -1; }
    ns = atomic_fetch_add(&clock_value, atomic_load(&clock_step));
    ts->tv_sec = (time_t)(ns / 1000000000ULL);
    ts->tv_nsec = (long)(ns % 1000000000ULL);
    errno = EINTR; /* Test both input and output errno restoration. */
    return 0;
}
