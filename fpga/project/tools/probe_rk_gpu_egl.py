"""Small EGL/GLES pbuffer smoke test; runs on RK3568 via Python ctypes."""
import ctypes as c
import json

egl = c.CDLL('libEGL.so.1')
gles = c.CDLL('libGLESv2.so.2')

def bind(lib, name, result, args):
    fn = getattr(lib, name)
    fn.restype = result
    fn.argtypes = args
    return fn

ptr, integer = c.c_void_p, c.c_int
get_display = bind(egl, 'eglGetDisplay', ptr, [ptr])
initialize = bind(egl, 'eglInitialize', c.c_uint, [ptr, c.POINTER(integer), c.POINTER(integer)])
query = bind(egl, 'eglQueryString', c.c_char_p, [ptr, integer])
choose = bind(egl, 'eglChooseConfig', c.c_uint, [ptr, c.POINTER(integer), c.POINTER(ptr), integer, c.POINTER(integer)])
bind_api = bind(egl, 'eglBindAPI', c.c_uint, [c.c_uint])
create_surface = bind(egl, 'eglCreatePbufferSurface', ptr, [ptr, ptr, c.POINTER(integer)])
create_context = bind(egl, 'eglCreateContext', ptr, [ptr, ptr, ptr, c.POINTER(integer)])
make_current = bind(egl, 'eglMakeCurrent', c.c_uint, [ptr, ptr, ptr, ptr])
get_error = bind(egl, 'eglGetError', integer, [])
gl_string = bind(gles, 'glGetString', c.c_char_p, [c.c_uint])
gl_clear_color = bind(gles, 'glClearColor', None, [c.c_float] * 4)
gl_clear = bind(gles, 'glClear', None, [c.c_uint])
gl_read = bind(gles, 'glReadPixels', None, [integer] * 4 + [c.c_uint, c.c_uint, ptr])
gl_error = bind(gles, 'glGetError', c.c_uint, [])

def check(value, operation):
    if not value:
        raise RuntimeError('%s failed: EGL error %#x' % (operation, get_error()))
    return value

display = check(get_display(None), 'eglGetDisplay')
major, minor = integer(), integer()
check(initialize(display, c.byref(major), c.byref(minor)), 'eglInitialize')
config, count = ptr(), integer()
attributes = (integer * 13)(0x3033, 1, 0x3040, 4, 0x3024, 8, 0x3023, 8, 0x3022, 8, 0x3021, 8, 0x3038)
check(choose(display, attributes, c.byref(config), 1, c.byref(count)), 'eglChooseConfig')
check(count.value, 'config count')
check(bind_api(0x30A0), 'eglBindAPI')
surface = check(create_surface(display, config, (integer * 5)(0x3057, 16, 0x3056, 16, 0x3038)), 'eglCreatePbufferSurface')
context = check(create_context(display, config, None, (integer * 3)(0x3098, 2, 0x3038)), 'eglCreateContext')
check(make_current(display, surface, surface, context), 'eglMakeCurrent')
gl_clear_color(1, 0, 0, 1)
gl_clear(0x4000)
pixel = (c.c_ubyte * 4)()
gl_read(0, 0, 1, 1, 0x1908, 0x1401, pixel)
result = {'egl_version': '%d.%d' % (major.value, minor.value),
          'egl_vendor': query(display, 0x3053).decode(),
          'gl_vendor': gl_string(0x1F00).decode(),
          'gl_renderer': gl_string(0x1F01).decode(),
          'gl_version': gl_string(0x1F02).decode(),
          'rgba_readback': list(pixel), 'gl_error': gl_error()}
result['pass'] = result['rgba_readback'] == [255, 0, 0, 255] and result['gl_error'] == 0
print(json.dumps(result, indent=2))
make_current(display, None, None, None)
bind(egl, 'eglDestroyContext', c.c_uint, [ptr, ptr])(display, context)
bind(egl, 'eglDestroySurface', c.c_uint, [ptr, ptr])(display, surface)
bind(egl, 'eglTerminate', c.c_uint, [ptr])(display)
raise SystemExit(0 if result['pass'] else 1)
