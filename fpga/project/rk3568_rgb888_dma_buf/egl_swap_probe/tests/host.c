#define _GNU_SOURCE
#include "../egl_abi.h"
#include <assert.h>
#include <dlfcn.h>
#include <errno.h>
#include <pthread.h>
#include <stdatomic.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

extern EGLBoolean eglSwapBuffers(EGLDisplay, EGLSurface);
extern EGLBoolean eglSwapInterval(EGLDisplay, EGLint);
extern __eglMustCastToProperFunctionPointerType eglGetProcAddress(const char *);
extern atomic_uint stub_swaps, stub_intervals, clock_calls;
extern atomic_ullong clock_value;
extern atomic_ullong clock_step;
extern int fail_clock_call, recursive, alternate_proc;
extern _Thread_local EGLBoolean stub_return;
typedef EGLBoolean (*swap_fn)(EGLDisplay, EGLSurface);
typedef EGLBoolean (*interval_fn)(EGLDisplay, EGLint);
static EGLDisplay display = (void *)(uintptr_t)0x1234;
static EGLSurface surface = (void *)(uintptr_t)0x5678;
void nested_swap(void)
{
    errno = EDOM;
    assert(eglSwapBuffers(display, surface) == stub_return);
    assert(errno == ERANGE);
}
static void interval(EGLint value)
{
    errno = EDOM;
    assert(eglSwapInterval(display, value) == (value == -3 ? 0U : 9U));
    assert(errno == EACCES);
}
static void *worker(void *arg)
{
    (void)arg;
    for (int i = 0; i < 100; ++i) nested_swap();
    return NULL;
}
static void flush(void)
{
    atomic_fetch_add(&clock_value, 6000000000ULL);
    nested_swap();
}
int main(int argc, char **argv)
{
    assert(argc == 2);
    if (!strcmp(argv[1], "swapfailure")) {
        stub_return = 0;
        nested_swap();
        stub_return = 7;
        flush();
        assert(atomic_load(&stub_swaps) == 2);
    } else if (!strcmp(argv[1], "buckets")) {
        const unsigned long long steps[] = {500000, 1000000, 5000000, 10000000, 20000000};
        for (unsigned i = 0; i < sizeof steps / sizeof steps[0]; ++i) {
            atomic_store(&clock_step, steps[i]);
            nested_swap();
        }
        flush();
        assert(atomic_load(&stub_swaps) == 6);
    } else if (!strcmp(argv[1], "threads")) {
        pthread_t threads[4];
        for (int i = 0; i < 4; ++i) assert(!pthread_create(&threads[i], NULL, worker, NULL));
        for (int i = 0; i < 4; ++i) assert(!pthread_join(threads[i], NULL));
        flush();
        assert(atomic_load(&stub_swaps) == 401);
        assert(atomic_load(&clock_calls) == 802);
    } else if (!strcmp(argv[1], "clockfail1") || !strcmp(argv[1], "clockfail2")) {
        fail_clock_call = argv[1][9] - '0';
        nested_swap();
        flush();
        assert(atomic_load(&stub_swaps) == 2);
    } else if (!strcmp(argv[1], "reentry")) {
        recursive = 1;
        nested_swap();
        flush();
        assert(atomic_load(&stub_swaps) == 4);
        assert(atomic_load(&clock_calls) == 4);
    } else {
        void *handle = dlopen("libstub.so", RTLD_NOW | RTLD_LOCAL);
        __eglMustCastToProperFunctionPointerType ptr;
        assert(handle);
        nested_swap();
        interval(-3); interval(0); interval(1); interval(42);
        errno = EDOM;
        ptr = eglGetProcAddress("eglSwapBuffers");
        assert(errno == ENOTTY);
        assert(ptr == (__eglMustCastToProperFunctionPointerType)
            (!strcmp(argv[1], "disabled") ? dlsym(handle, "eglSwapBuffers") :
                                            dlsym(RTLD_DEFAULT, "eglSwapBuffers")));
        errno = EDOM;
        assert(((swap_fn)ptr)(display, surface) == 7 && errno == ERANGE);
        errno = EDOM;
        ptr = eglGetProcAddress("eglSwapInterval");
        assert(errno == ENOTTY);
        assert(ptr == (__eglMustCastToProperFunctionPointerType)
            (!strcmp(argv[1], "disabled") ? dlsym(handle, "eglSwapInterval") :
                                            dlsym(RTLD_DEFAULT, "eglSwapInterval")));
        errno = EDOM;
        assert(((interval_fn)ptr)(display, -3) == 0 && errno == EACCES);
        errno = EDOM;
        ptr = eglGetProcAddress("unrelated");
        assert(ptr && errno == ENOTTY);
        /* Stub binds its functions locally, allowing identity checks. */
        { typedef __eglMustCastToProperFunctionPointerType (*get_fn)(const char *);
          get_fn direct = (get_fn)dlsym(handle, "eglGetProcAddress");
          errno = EDOM;
          assert(ptr == direct("unrelated")); }
        errno = EDOM;
        assert(!eglGetProcAddress("missing") && errno == ENOTTY);
        alternate_proc = 1;
        errno = EDOM;
        ptr = eglGetProcAddress("eglSwapBuffers");
        assert(errno == ENOTTY);
        assert(((swap_fn)ptr)(display, surface) == 77);
        assert(atomic_load(&stub_swaps) == 2);
        assert(atomic_load(&stub_intervals) == 5);
        if (!strcmp(argv[1], "disabled")) assert(!atomic_load(&clock_calls));
        else flush();
    }
    puts("host assertions passed");
    return 0;
}
