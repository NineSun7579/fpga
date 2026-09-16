#!/usr/bin/env python3
"""Send one key to the focused X11 window without xdotool."""
import ctypes
import sys


class XKeyEvent(ctypes.Structure):
    _fields_ = [
        ("type", ctypes.c_int), ("serial", ctypes.c_ulong),
        ("send_event", ctypes.c_int), ("display", ctypes.c_void_p),
        ("window", ctypes.c_ulong), ("root", ctypes.c_ulong),
        ("subwindow", ctypes.c_ulong), ("time", ctypes.c_ulong),
        ("x", ctypes.c_int), ("y", ctypes.c_int),
        ("x_root", ctypes.c_int), ("y_root", ctypes.c_int),
        ("state", ctypes.c_uint), ("keycode", ctypes.c_uint),
        ("same_screen", ctypes.c_int),
    ]


key = sys.argv[1].lower()
if len(key) != 1:
    raise SystemExit("usage: send_key.py <single-key>")

x11 = ctypes.CDLL("libX11.so.6")
x11.XOpenDisplay.restype = ctypes.c_void_p
x11.XDefaultRootWindow.restype = ctypes.c_ulong
display = x11.XOpenDisplay(b":0")
if not display:
    raise SystemExit("cannot open DISPLAY=:0")

window = ctypes.c_ulong()
revert = ctypes.c_int()
x11.XGetInputFocus(display, ctypes.byref(window), ctypes.byref(revert))
root = x11.XDefaultRootWindow(display)
keycode = x11.XKeysymToKeycode(display, ord(key))

event = XKeyEvent()
event.display = display
event.window = window.value
event.root = root
event.same_screen = 1
event.keycode = keycode

for event_type, mask in ((2, 1 << 0), (3, 1 << 1)):
    event.type = event_type
    x11.XSendEvent(display, window.value, 1, mask, ctypes.byref(event))
x11.XFlush(display)
x11.XCloseDisplay(display)
