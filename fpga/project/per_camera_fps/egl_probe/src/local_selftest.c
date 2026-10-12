#define _GNU_SOURCE
#include <assert.h>
#include <dlfcn.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

int main(int argc, char **argv)
{
    assert(argc == 3);
    const char *core = getenv("FAKE_CORE_EGL");
    if (core) assert(dlopen(core, RTLD_NOW | RTLD_GLOBAL));
    /* No EGL DT_NEEDED: reproduce Qt loading its provider after preload init. */
    void *provider = NULL;
    if (strcmp(argv[2], "missing") != 0) {
        int visibility = strcmp(argv[2], "global") == 0 ? RTLD_GLOBAL : RTLD_LOCAL;
        provider = dlopen(argv[1], RTLD_NOW | visibility);
        assert(provider);
    }
    unsigned (*interval)(void *, int);
    unsigned (*swap)(void *, void *);
    *(void **)(&interval) = dlsym(RTLD_DEFAULT, "eglSwapInterval");
    *(void **)(&swap) = dlsym(RTLD_DEFAULT, "eglSwapBuffers");
    assert(interval && swap);
    assert(interval((void *)1, 0) == 1);
    assert(interval((void *)1, 1) == 0);
    assert(swap((void *)1, (void *)2) == 0);
    for (int i = 0; i < 8; ++i) assert(swap((void *)1, (void *)2) == 1);
    unsigned (*count)(void);
    *(void **)(&count) = dlsym(provider, "fake_swaps");
    assert(count && count() == 9);
    *(void **)(&count) = dlsym(provider, "fake_intervals");
    assert(count && count() == 3);
    *(void **)(&count) = dlsym(provider, "fake_error_reads");
    assert(count && count() == 0);
    *(void **)(&count) = dlsym(provider, "fake_queries");
    const char *trace = getenv("DETVIEW_EGL_TRACE");
    const char *metadata = getenv("DETVIEW_EGL_METADATA");
    assert(count && count() == (trace && strcmp(trace, "1") == 0 &&
           metadata && strcmp(metadata, "1") == 0 ? 18U : 0U));
    puts("PASS: late-loaded provider, exact forwarding, metadata from same provider");
    return 0;
}
