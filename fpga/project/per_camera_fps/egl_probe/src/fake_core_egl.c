#include <stdlib.h>

/* A separate global dispatch facade has no knowledge of the local vendor's
 * current display. Any forwarding to it in the provider test is a bug. This
 * models dispatch separation, not the complete GLVND/Mesa/Mali implementation. */
void *eglGetCurrentDisplay(void) { return NULL; }
void *eglGetCurrentSurface(int key) { (void)key; return NULL; }
void *eglGetCurrentContext(void) { return NULL; }
unsigned eglSwapInterval(void *d, int interval)
{
    (void)d; (void)interval;
    abort();
}
unsigned eglSwapBuffers(void *d, void *s)
{
    (void)d; (void)s;
    abort();
}
const char *eglQueryString(void *d, int key)
{
    (void)d; (void)key;
    return "fake core dispatch";
}
