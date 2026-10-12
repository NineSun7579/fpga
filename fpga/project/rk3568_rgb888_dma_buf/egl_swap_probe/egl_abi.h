#ifndef DETVIEW_EGL_ABI_H
#define DETVIEW_EGL_ABI_H
/* Use Khronos declarations when the build sysroot supplies them. */
#if !defined(PROBE_NO_EGL_HEADERS) && defined(__has_include)
# if __has_include(<EGL/egl.h>)
#  include <EGL/egl.h>
#  define PROBE_OFFICIAL_EGL 1
# endif
#endif
#ifndef PROBE_OFFICIAL_EGL
typedef void *EGLDisplay;
typedef void *EGLSurface;
typedef unsigned int EGLBoolean;
typedef int EGLint;
#define EGLAPIENTRY
typedef void (EGLAPIENTRY *__eglMustCastToProperFunctionPointerType)(void);
#endif
#endif
