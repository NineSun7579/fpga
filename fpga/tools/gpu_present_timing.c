#define _GNU_SOURCE
#include <dlfcn.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <time.h>

static double now(void) {
    struct timespec t;
    clock_gettime(CLOCK_MONOTONIC, &t);
    return t.tv_sec + t.tv_nsec / 1e9;
}
static uint64_t swaps, clears, uploads;
static double swap_ms, clear_ms, upload_ms, max_swap_ms, max_clear_ms, epoch;
static void (*actual_clear)(unsigned int);
static void (*actual_upload)(unsigned int,int,int,int,int,int,unsigned int,unsigned int,const void *);
static void *egl_symbol(const char *name) {
    static void *handle;
    if (!handle) handle=dlopen("/usr/lib/aarch64-linux-gnu/mali/libEGL.so.1", RTLD_LAZY | RTLD_LOCAL);
    return handle ? dlsym(handle,name) : NULL;
}
static void report(void) {
    double t = now();
    if (!epoch) epoch = t;
    if (t - epoch < 5) return;
    fprintf(stderr, "gpu_timing seconds=%.3f swaps=%lu swap_ms=%.3f max_swap_ms=%.3f clears=%lu clear_ms=%.3f max_clear_ms=%.3f uploads=%lu upload_ms=%.3f\n",
            t-epoch, (unsigned long)swaps, swaps ? swap_ms/swaps : 0, max_swap_ms,
            (unsigned long)clears, clears ? clear_ms/clears : 0, max_clear_ms,
            (unsigned long)uploads, uploads ? upload_ms/uploads : 0);
    fflush(stderr);
    swaps=clears=uploads=0;
    swap_ms=clear_ms=upload_ms=max_swap_ms=max_clear_ms=0;
    epoch=t;
}
unsigned int eglSwapBuffers(void *display, void *surface) {
    static unsigned int (*real)(void *, void *);
    if (!real) real=egl_symbol("eglSwapBuffers");
    double t=now();
    unsigned int result=real(display,surface);
    double ms=(now()-t)*1000;
    ++swaps; swap_ms+=ms; if(ms>max_swap_ms) max_swap_ms=ms;
    report();
    return result;
}
void glClear(unsigned int mask) {
    if (!actual_clear) actual_clear=dlsym(RTLD_NEXT,"glClear");
    double t=now(); actual_clear(mask); double ms=(now()-t)*1000;
    ++clears; clear_ms+=ms; if(ms>max_clear_ms) max_clear_ms=ms;
}
void glTexSubImage2D(unsigned int target,int level,int x,int y,int w,int h,
                     unsigned int format,unsigned int type,const void *pixels) {
    if (!actual_upload) actual_upload=dlsym(RTLD_NEXT,"glTexSubImage2D");
    double t=now(); actual_upload(target,level,x,y,w,h,format,type,pixels);
    ++uploads; upload_ms+=(now()-t)*1000;
}
void *eglGetProcAddress(const char *name) {
    static void *(*real)(const char *);
    if (!real) real=egl_symbol("eglGetProcAddress");
    if (!strcmp(name,"glClear")) { actual_clear=real(name); return actual_clear ? (void *)glClear : NULL; }
    if (!strcmp(name,"glTexSubImage2D")) { actual_upload=real(name); return actual_upload ? (void *)glTexSubImage2D : NULL; }
    if (!strcmp(name,"eglSwapBuffers")) return (void *)eglSwapBuffers;
    return real(name);
}
