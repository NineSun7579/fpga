#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

extern unsigned eglSwapInterval(void *, int);
extern unsigned eglSwapBuffers(void *, void *);
extern unsigned fake_swaps(void), fake_intervals(void);
extern unsigned fake_queries(void), fake_error_reads(void);

int main(int argc, char **argv)
{
    int enabled = argc == 2 && strcmp(argv[1], "enabled") == 0;
    assert(eglSwapInterval((void *)1, 0) == 1);
    assert(eglSwapInterval((void *)1, 1) == 0);
    assert(eglSwapBuffers((void *)1, (void *)2) == 0);
    for (int i = 0; i < 8; ++i)
        assert(eglSwapBuffers((void *)1, (void *)2) == 1);
    assert(fake_swaps() == 9 && fake_intervals() == 3);
    assert(fake_error_reads() == 0);
    const char *metadata = getenv("DETVIEW_EGL_METADATA");
    assert(fake_queries() == (enabled && metadata && strcmp(metadata, "1") == 0 ? 18U : 0U));
    puts("PASS: exact returns, forwarding, recursion, query gating, no error reads");
    return 0;
}
