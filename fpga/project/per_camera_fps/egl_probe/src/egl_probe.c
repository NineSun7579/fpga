#define _GNU_SOURCE
#include <dlfcn.h>
#include <pthread.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

/* Linux EGL ABI types; no EGL headers or link-time EGL dependency. */
typedef void *EGLDisplay;
typedef void *EGLSurface;
typedef void *EGLContext;
typedef void *EGLConfig;
typedef unsigned int EGLBoolean;
typedef int32_t EGLint;
enum {
    EGL_BUFFER_SIZE = 0x3020, EGL_ALPHA_SIZE = 0x3021,
    EGL_CONFIG_ID = 0x3028, EGL_NATIVE_VISUAL_ID = 0x302e,
    EGL_MIN_SWAP_INTERVAL = 0x303b, EGL_MAX_SWAP_INTERVAL = 0x303c,
    EGL_RENDERABLE_TYPE = 0x3040, EGL_VENDOR = 0x3053,
    EGL_VERSION = 0x3054, EGL_EXTENSIONS = 0x3055,
    EGL_HEIGHT = 0x3056, EGL_WIDTH = 0x3057, EGL_DRAW = 0x3059,
    EGL_RENDER_BUFFER = 0x3086, EGL_SWAP_BEHAVIOR = 0x3093
};
static EGLBoolean (*next_interval)(EGLDisplay, EGLint);
static EGLBoolean (*next_swap)(EGLDisplay, EGLSurface);
static EGLDisplay (*current_display)(void);
static EGLSurface (*current_surface)(EGLint);
static EGLContext (*current_context)(void);
static EGLBoolean (*query_surface)(EGLDisplay, EGLSurface, EGLint, EGLint *);
static EGLBoolean (*get_configs)(EGLDisplay, EGLConfig *, EGLint, EGLint *);
static EGLBoolean (*config_attrib)(EGLDisplay, EGLConfig, EGLint, EGLint *);
static const char *(*query_string)(EGLDisplay, EGLint);
static pthread_once_t symbols_once = PTHREAD_ONCE_INIT;
static pthread_mutex_t lock = PTHREAD_MUTEX_INITIALIZER;
static _Thread_local int resolving, inside;
static int enabled, metadata_enabled, metadata_done, interval_seen;
static EGLint last_interval;
static EGLBoolean last_interval_result;
static uint64_t window_start, swaps, swap_ok, intervals, interval_ok;
static uint64_t swap_ns, swap_max, interval_ns, interval_max;
EGLBoolean eglSwapInterval(EGLDisplay d, EGLint interval);
EGLBoolean eglSwapBuffers(EGLDisplay d, EGLSurface s);

static void forwarding_failure(const char *reason)
{
    fprintf(stderr, "[egl-probe] fatal forwarding unavailable: %s; no EGL call issued\n", reason);
    fflush(stderr);
    abort();
}

static uint64_t now_ns(void)
{
    struct timespec t;
    if (clock_gettime(CLOCK_MONOTONIC, &t) != 0) return 0;
    return (uint64_t)t.tv_sec * 1000000000ULL + (uint64_t)t.tv_nsec;
}

static void resolve_symbols(void)
{
    resolving = 1;
    /* Qt may load EGL after constructors, and may keep it RTLD_LOCAL.
     * An explicit provider must be the application's already-loaded provider;
     * never load a guessed libEGL/GLVND stack for opaque vendor handles. */
    const char *provider = getenv("DETVIEW_EGL_PROVIDER");
    void *scope = RTLD_NEXT;
    if (provider && *provider) {
        scope = dlopen(provider, RTLD_NOW | RTLD_LOCAL | RTLD_NOLOAD);
        if (!scope) forwarding_failure("selected provider is not loaded");
        /* Retain this reference: cached functions must remain callable. */
    }
#define RESOLVE(dst, name) *(void **)(&(dst)) = dlsym(scope, name)
    RESOLVE(next_interval, "eglSwapInterval");
    RESOLVE(next_swap, "eglSwapBuffers");
    if (!next_interval || !next_swap)
        forwarding_failure("eglSwapInterval/eglSwapBuffers missing (RTLD_LOCAL needs DETVIEW_EGL_PROVIDER)");
    if (next_interval == eglSwapInterval || next_swap == eglSwapBuffers)
        forwarding_failure("selected provider resolves back to probe");
    if (enabled) {
        Dl_info swap_info = {0}, interval_info = {0};
        dladdr((void *)next_swap, &swap_info);
        dladdr((void *)next_interval, &interval_info);
        fprintf(stderr, "[egl-probe] resolver scope=%s swap_object=%s interval_object=%s\n",
                scope == RTLD_NEXT ? "RTLD_NEXT" : "explicit-loaded-provider",
                swap_info.dli_fname ? swap_info.dli_fname : "unknown",
                interval_info.dli_fname ? interval_info.dli_fname : "unknown");
    }
    if (enabled && metadata_enabled) {
        RESOLVE(current_display, "eglGetCurrentDisplay");
        RESOLVE(current_surface, "eglGetCurrentSurface");
        RESOLVE(current_context, "eglGetCurrentContext");
        RESOLVE(query_surface, "eglQuerySurface");
        RESOLVE(get_configs, "eglGetConfigs");
        RESOLVE(config_attrib, "eglGetConfigAttrib");
        RESOLVE(query_string, "eglQueryString");
    }
#undef RESOLVE
    resolving = 0;
}

__attribute__((constructor)) static void initialize(void)
{
    const char *value = getenv("DETVIEW_EGL_TRACE");
    enabled = value && strcmp(value, "1") == 0;
    value = getenv("DETVIEW_EGL_METADATA");
    metadata_enabled = value && strcmp(value, "1") == 0;
}

static void surface_value(EGLDisplay d, EGLSurface s, EGLint key, const char *name)
{
    EGLint value = 0;
    EGLBoolean ok = query_surface(d, s, key, &value);
    if (ok) fprintf(stderr, "[egl-probe] surface %s=%d (0x%x) success=1\n",
                    name, value, (unsigned)value);
    else fprintf(stderr, "[egl-probe] surface %s success=0\n", name);
}

static void metadata(EGLDisplay d, EGLSurface s)
{
    fprintf(stderr, "[egl-probe] init next_swap=%d next_interval=%d query_surface=%d configs=%d config_attrib=%d\n",
            next_swap != NULL, next_interval != NULL, query_surface != NULL,
            get_configs != NULL, config_attrib != NULL);
    int display_matches = current_display ? current_display() == d : -1;
    int draw_matches = current_surface ? current_surface(EGL_DRAW) == s : -1;
    int context_present = current_context ? current_context() != NULL : -1;
    fprintf(stderr, "[egl-probe] current display_matches=%d draw_matches=%d context_present=%d\n",
            display_matches, draw_matches, context_present);
    if (display_matches != 1 || draw_matches != 1 || context_present != 1) {
        fprintf(stderr, "[egl-probe] metadata skipped: provider current context does not match\n");
        return;
    }
    if (query_string) {
        const EGLint keys[] = { EGL_VERSION, EGL_VENDOR, EGL_EXTENSIONS };
        const char *names[] = { "version", "vendor", "extensions" };
        for (unsigned i = 0; i < 3; ++i) {
            const char *text = query_string(d, keys[i]);
            fprintf(stderr, "[egl-probe] %s success=%d value=%.512s%s\n", names[i],
                    text != NULL, text ? text : "", text && strlen(text) > 512 ? " [truncated]" : "");
        }
    }
    if (!query_surface) return;
    surface_value(d, s, EGL_RENDER_BUFFER, "EGL_RENDER_BUFFER");
    surface_value(d, s, EGL_SWAP_BEHAVIOR, "EGL_SWAP_BEHAVIOR");
    surface_value(d, s, EGL_WIDTH, "EGL_WIDTH");
    surface_value(d, s, EGL_HEIGHT, "EGL_HEIGHT");
    EGLint id = 0, count = 0;
    EGLBoolean ok = query_surface(d, s, EGL_CONFIG_ID, &id);
    fprintf(stderr, "[egl-probe] surface EGL_CONFIG_ID success=%u value=%d\n", ok, id);
    if (!ok || !get_configs || !config_attrib) return;
    ok = get_configs(d, NULL, 0, &count);
    fprintf(stderr, "[egl-probe] eglGetConfigs count success=%u count=%d\n", ok, count);
    if (!ok || count <= 0 || count > 65536) return;
    EGLConfig *configs = calloc((size_t)count, sizeof(*configs));
    if (!configs) { fprintf(stderr, "[egl-probe] config allocation failed\n"); return; }
    EGLint filled = 0;
    ok = get_configs(d, configs, count, &filled);
    fprintf(stderr, "[egl-probe] eglGetConfigs list success=%u count=%d\n", ok, filled);
    int matched = 0;
    if (ok) for (EGLint i = 0; i < filled && i < count; ++i) {
        EGLint candidate = 0;
        ok = config_attrib(d, configs[i], EGL_CONFIG_ID, &candidate);
        if (!ok) fprintf(stderr, "[egl-probe] config index=%d EGL_CONFIG_ID success=0\n", i);
        if (!ok || candidate != id) continue;
        matched = 1;
        const EGLint keys[] = { EGL_MIN_SWAP_INTERVAL, EGL_MAX_SWAP_INTERVAL,
            EGL_ALPHA_SIZE, EGL_BUFFER_SIZE, EGL_NATIVE_VISUAL_ID, EGL_RENDERABLE_TYPE };
        const char *names[] = { "EGL_MIN_SWAP_INTERVAL", "EGL_MAX_SWAP_INTERVAL",
            "EGL_ALPHA_SIZE", "EGL_BUFFER_SIZE", "EGL_NATIVE_VISUAL_ID", "EGL_RENDERABLE_TYPE" };
        for (unsigned j = 0; j < 6; ++j) {
            EGLint value = 0;
            ok = config_attrib(d, configs[i], keys[j], &value);
            if (ok) fprintf(stderr, "[egl-probe] config %s=%d (0x%x) success=1\n",
                            names[j], value, (unsigned)value);
            else fprintf(stderr, "[egl-probe] config %s success=0\n", names[j]);
        }
        break;
    }
    fprintf(stderr, "[egl-probe] config_id_matched=%d\n", matched);
    free(configs);
}

/* Called under lock, after forwarding; no EGL error reads or state setters. */
static void aggregate(uint64_t end)
{
    if (!window_start) window_start = end;
    if (end < window_start || end - window_start < 10000000000ULL) return;
    fprintf(stderr, "[egl-call] window_s=%.3f swaps=%llu successes=%llu failures=%llu mean_ms=%.3f max_ms=%.3f interval_calls=%llu successes=%llu failures=%llu interval_mean_ms=%.3f interval_max_ms=%.3f\n",
            (end - window_start) / 1e9, (unsigned long long)swaps,
            (unsigned long long)swap_ok, (unsigned long long)(swaps - swap_ok),
            swaps ? swap_ns / 1e6 / swaps : 0.0, swap_max / 1e6,
            (unsigned long long)intervals, (unsigned long long)interval_ok,
            (unsigned long long)(intervals - interval_ok),
            intervals ? interval_ns / 1e6 / intervals : 0.0, interval_max / 1e6);
    window_start = end;
    swaps = swap_ok = intervals = interval_ok = 0;
    swap_ns = swap_max = interval_ns = interval_max = 0;
}

EGLBoolean eglSwapInterval(EGLDisplay d, EGLint interval)
{
    if (resolving) forwarding_failure("resolver reentry in eglSwapInterval");
    pthread_once(&symbols_once, resolve_symbols);
    if (!enabled || inside) return next_interval(d, interval);
    inside = 1;
    uint64_t start = now_ns();
    EGLBoolean result = next_interval(d, interval);
    uint64_t end = now_ns(), elapsed = end >= start ? end - start : 0;
    pthread_mutex_lock(&lock);
    if (!window_start) window_start = start;
    ++intervals; interval_ok += result != 0; interval_ns += elapsed;
    if (elapsed > interval_max) interval_max = elapsed;
    if (!interval_seen || interval != last_interval || result != last_interval_result) {
        fprintf(stderr, "[egl-call] interval=%d success=%u duration_ms=%.3f\n", interval, result, elapsed / 1e6);
        interval_seen = 1; last_interval = interval; last_interval_result = result;
    }
    aggregate(end);
    pthread_mutex_unlock(&lock);
    inside = 0;
    return result;
}

EGLBoolean eglSwapBuffers(EGLDisplay d, EGLSurface s)
{
    if (resolving) forwarding_failure("resolver reentry in eglSwapBuffers");
    pthread_once(&symbols_once, resolve_symbols);
    if (!enabled || inside) return next_swap(d, s);
    inside = 1;
    uint64_t start = now_ns();
    EGLBoolean result = next_swap(d, s);
    uint64_t end = now_ns(), elapsed = end >= start ? end - start : 0;
    pthread_mutex_lock(&lock);
    if (!window_start) window_start = start;
    ++swaps; swap_ok += result != 0; swap_ns += elapsed;
    if (elapsed > swap_max) swap_max = elapsed;
    if (result && metadata_enabled && !metadata_done) {
        metadata_done = 1;
        metadata(d, s);
    }
    aggregate(end);
    pthread_mutex_unlock(&lock);
    inside = 0;
    return result;
}
