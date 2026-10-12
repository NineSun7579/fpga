#define _GNU_SOURCE
#include <assert.h>
#include <dlfcn.h>
#include <stdint.h>
#include <string.h>
#include <time.h>

static unsigned swaps, intervals, queries, error_reads;
static uint64_t ticks = 1000000000ULL;
static void *display = (void *)1, *surface = (void *)2;
int clock_gettime(clockid_t clock, struct timespec *t)
{
    assert(clock == CLOCK_MONOTONIC);
    t->tv_sec = (time_t)(ticks / 1000000000ULL);
    t->tv_nsec = (long)(ticks % 1000000000ULL);
    ticks += 3000000000ULL;
    return 0;
}
void *eglGetCurrentDisplay(void) { return display; }
void *eglGetCurrentSurface(int key) { assert(key == 0x3059); return surface; }
void *eglGetCurrentContext(void) { return (void *)3; }
unsigned eglGetError(void) { ++error_reads; return 0x3000; }
unsigned eglSwapInterval(void *d, int n)
{
    assert(d == display);
    ++intervals;
    return n == 0 ? 1U : 0U;
}
unsigned eglSwapBuffers(void *d, void *s)
{
    assert(d == display && s == surface);
    ++swaps;
    if (swaps == 2) {
        unsigned (*nested)(void *, int);
        *(void **)(&nested) = dlsym(RTLD_DEFAULT, "eglSwapInterval");
        assert(nested && nested(d, 0) == 1);
    }
    return swaps == 1 ? 0U : 1U;
}
const char *eglQueryString(void *d, int key)
{
    assert(d == display);
    ++queries;
    if (key == 0x3054) return "fake EGL 1.5";
    if (key == 0x3053) return "fake vendor";
    assert(key == 0x3055);
    return "FAKE_extension";
}
unsigned eglQuerySurface(void *d, void *s, int key, int *value)
{
    assert(d == display && s == surface);
    ++queries;
    if (key == 0x3093) return 0; /* Deliberately fail one metadata query. */
    *value = key == 0x3028 ? 42 : 640;
    return 1;
}
unsigned eglGetConfigs(void *d, void **configs, int capacity, int *count)
{
    assert(d == display);
    ++queries;
    *count = 2;
    if (configs) {
        assert(capacity == 2);
        configs[0] = (void *)10;
        configs[1] = (void *)11;
    }
    return 1;
}
unsigned eglGetConfigAttrib(void *d, void *config, int key, int *value)
{
    assert(d == display);
    ++queries;
    if (key == 0x3028) *value = config == (void *)11 ? 42 : 7;
    else { assert(config == (void *)11); *value = key == 0x303c ? 1 : 0; }
    return 1;
}
unsigned fake_swaps(void) { return swaps; }
unsigned fake_intervals(void) { return intervals; }
unsigned fake_queries(void) { return queries; }
unsigned fake_error_reads(void) { return error_reads; }
