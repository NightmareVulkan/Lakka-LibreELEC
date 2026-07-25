#!/usr/bin/env python3
"""
steam_triton_bridge.py
-----------------------
Bridges Valve's new Steam Controller (2026 "Triton") + Puck dongle into a
full-featured virtual Linux joystick, using SDL3's own hidapi driver for
protocol handling (lizard-mode disable, paddle buttons, touchpads, grip
sense) instead of relying on the kernel, which has no driver for this
device yet.

Requires: libSDL3.so.0 present on the system (built/installed as a Lakka
package; RetroArch itself does NOT need to link it).

No third-party Python packages needed — only ctypes + stdlib, so this runs
fine on Lakka's stock Python 3 without pip.

Run as root (needed to create /dev/uinput nodes). Intended to be started
by a udev rule when the Puck (28de:1304) is plugged in, and stopped when
it's removed.
"""

import ctypes
import ctypes.util
import fcntl
import os
import struct
import sys
import time

# ---------------------------------------------------------------------------
# uinput low-level bindings (pure stdlib, no external uinput package needed)
# ---------------------------------------------------------------------------

UI_DEV_CREATE = 0x5501
UI_DEV_DESTROY = 0x5502
UI_SET_EVBIT = 0x40045564
UI_SET_KEYBIT = 0x40045565
UI_SET_ABSBIT = 0x40045567

EV_SYN = 0x00
EV_KEY = 0x01
EV_ABS = 0x03

SYN_REPORT = 0

BTN_A = 0x130
BTN_B = 0x131
BTN_X = 0x133
BTN_Y = 0x134
BTN_TL = 0x136
BTN_TR = 0x137
BTN_TL2 = 0x138
BTN_TR2 = 0x139
BTN_SELECT = 0x13a
BTN_START = 0x13b
BTN_MODE = 0x13c
BTN_THUMBL = 0x13d
BTN_THUMBR = 0x13e
BTN_DPAD_UP = 0x220
BTN_DPAD_DOWN = 0x221
BTN_DPAD_LEFT = 0x222
BTN_DPAD_RIGHT = 0x223
# Extra buttons for paddles / grip sense / second touchpad — these codes
# are free in the gamepad range and RetroArch's udev driver reads them
# fine as generic BTN_TRIGGER_HAPPY slots.
BTN_TRIGGER_HAPPY1 = 0x2c0  # paddle1 (back-left upper)
BTN_TRIGGER_HAPPY2 = 0x2c1  # paddle2 (back-right upper)
BTN_TRIGGER_HAPPY3 = 0x2c2  # paddle3 (back-left lower)
BTN_TRIGGER_HAPPY4 = 0x2c3  # paddle4 (back-right lower)
BTN_TRIGGER_HAPPY5 = 0x2c4  # left touchpad click
BTN_TRIGGER_HAPPY6 = 0x2c5  # right touchpad click
BTN_TRIGGER_HAPPY7 = 0x2c6  # left grip sense
BTN_TRIGGER_HAPPY8 = 0x2c7  # right grip sense

ABS_X, ABS_Y, ABS_RX, ABS_RY, ABS_Z, ABS_RZ = 0x00, 0x01, 0x03, 0x04, 0x02, 0x05
ABS_HAT0X, ABS_HAT0Y = 0x10, 0x11  # left touchpad position
ABS_HAT1X, ABS_HAT1Y = 0x12, 0x13  # right touchpad position

AXIS_MIN, AXIS_MAX = -32768, 32767

BUS_USB = 0x03


class uinput_user_dev(ctypes.Structure):
    _fields_ = [
        ("name", ctypes.c_char * 80),
        ("id_bustype", ctypes.c_uint16),
        ("id_vendor", ctypes.c_uint16),
        ("id_product", ctypes.c_uint16),
        ("id_version", ctypes.c_uint16),
        ("ff_effects_max", ctypes.c_uint32),
        ("absmax", ctypes.c_int32 * 64),
        ("absmin", ctypes.c_int32 * 64),
        ("absfuzz", ctypes.c_int32 * 64),
        ("absflat", ctypes.c_int32 * 64),
    ]


class UInputJoystick:
    """Minimal uinput virtual joystick, no external dependencies."""

    def __init__(self, name="Steam Controller (2026) Bridge",
                 vendor=0x28de, product=0x1304):
        self.fd = os.open("/dev/uinput", os.O_WRONLY | os.O_NONBLOCK)

        fcntl.ioctl(self.fd, UI_SET_EVBIT, EV_KEY)
        for code in (
            BTN_A, BTN_B, BTN_X, BTN_Y, BTN_TL, BTN_TR, BTN_TL2, BTN_TR2,
            BTN_SELECT, BTN_START, BTN_MODE, BTN_THUMBL, BTN_THUMBR,
            BTN_DPAD_UP, BTN_DPAD_DOWN, BTN_DPAD_LEFT, BTN_DPAD_RIGHT,
            BTN_TRIGGER_HAPPY1, BTN_TRIGGER_HAPPY2, BTN_TRIGGER_HAPPY3,
            BTN_TRIGGER_HAPPY4, BTN_TRIGGER_HAPPY5, BTN_TRIGGER_HAPPY6,
            BTN_TRIGGER_HAPPY7, BTN_TRIGGER_HAPPY8,
        ):
            fcntl.ioctl(self.fd, UI_SET_KEYBIT, code)

        fcntl.ioctl(self.fd, UI_SET_EVBIT, EV_ABS)
        for code in (ABS_X, ABS_Y, ABS_RX, ABS_RY, ABS_Z, ABS_RZ,
                     ABS_HAT0X, ABS_HAT0Y, ABS_HAT1X, ABS_HAT1Y):
            fcntl.ioctl(self.fd, UI_SET_ABSBIT, code)

        dev = uinput_user_dev()
        dev.name = name.encode()[:79]
        dev.id_bustype = BUS_USB
        dev.id_vendor = vendor
        dev.id_product = product
        dev.id_version = 1
        for code in (ABS_X, ABS_Y, ABS_RX, ABS_RY,
                     ABS_HAT0X, ABS_HAT0Y, ABS_HAT1X, ABS_HAT1Y):
            dev.absmin[code] = AXIS_MIN
            dev.absmax[code] = AXIS_MAX
        for code in (ABS_Z, ABS_RZ):
            dev.absmin[code] = 0
            dev.absmax[code] = AXIS_MAX

        os.write(self.fd, bytes(dev))
        fcntl.ioctl(self.fd, UI_DEV_CREATE)
        # give the kernel a moment to register the node
        time.sleep(0.2)

    def emit(self, ev_type, code, value):
        # struct input_event { struct timeval time; u16 type; u16 code; s32 value; }
        t = time.time()
        sec = int(t)
        usec = int((t - sec) * 1_000_000)
        os.write(self.fd, struct.pack("llHHi", sec, usec, ev_type, code, value))

    def key(self, code, pressed):
        self.emit(EV_KEY, code, 1 if pressed else 0)
        self.emit(EV_SYN, SYN_REPORT, 0)

    def abs_axis(self, code, value):
        self.emit(EV_ABS, code, value)
        self.emit(EV_SYN, SYN_REPORT, 0)

    def close(self):
        fcntl.ioctl(self.fd, UI_DEV_DESTROY)
        os.close(self.fd)


# ---------------------------------------------------------------------------
# SDL3 bindings (only the handful of calls we need)
# ---------------------------------------------------------------------------

SDL_INIT_GAMEPAD = 0x00002000
SDL_EVENT_GAMEPAD_ADDED = 0x653
SDL_EVENT_GAMEPAD_REMOVED = 0x654
SDL_EVENT_GAMEPAD_BUTTON_DOWN = 0x650
SDL_EVENT_GAMEPAD_BUTTON_UP = 0x651
SDL_EVENT_GAMEPAD_AXIS_MOTION = 0x656
SDL_EVENT_QUIT = 0x100

# SDL_GamepadButton enum (SDL3) — includes the new controller's extras.
SDL_GAMEPAD_BUTTON_SOUTH = 0
SDL_GAMEPAD_BUTTON_EAST = 1
SDL_GAMEPAD_BUTTON_WEST = 2
SDL_GAMEPAD_BUTTON_NORTH = 3
SDL_GAMEPAD_BUTTON_BACK = 4
SDL_GAMEPAD_BUTTON_GUIDE = 5
SDL_GAMEPAD_BUTTON_START = 6
SDL_GAMEPAD_BUTTON_LEFT_STICK = 7
SDL_GAMEPAD_BUTTON_RIGHT_STICK = 8
SDL_GAMEPAD_BUTTON_LEFT_SHOULDER = 9
SDL_GAMEPAD_BUTTON_RIGHT_SHOULDER = 10
SDL_GAMEPAD_BUTTON_DPAD_UP = 11
SDL_GAMEPAD_BUTTON_DPAD_DOWN = 12
SDL_GAMEPAD_BUTTON_DPAD_LEFT = 13
SDL_GAMEPAD_BUTTON_DPAD_RIGHT = 14
SDL_GAMEPAD_BUTTON_MISC1 = 15
SDL_GAMEPAD_BUTTON_LEFT_PADDLE1 = 16
SDL_GAMEPAD_BUTTON_RIGHT_PADDLE1 = 17
SDL_GAMEPAD_BUTTON_LEFT_PADDLE2 = 18
SDL_GAMEPAD_BUTTON_RIGHT_PADDLE2 = 19
SDL_GAMEPAD_BUTTON_TOUCHPAD = 20
# Newer "misc2..6" slots used for the second touchpad / grip sense on this
# controller per the SDL PR that added them (adjust indices if a newer SDL
# release renumbers them — check SDL3's SDL_gamepad.h on your build).
SDL_GAMEPAD_BUTTON_MISC2 = 21
SDL_GAMEPAD_BUTTON_MISC3 = 22
SDL_GAMEPAD_BUTTON_MISC4 = 23
SDL_GAMEPAD_BUTTON_MISC5 = 24
SDL_GAMEPAD_BUTTON_MISC6 = 25

SDL_GAMEPAD_AXIS_LEFTX = 0
SDL_GAMEPAD_AXIS_LEFTY = 1
SDL_GAMEPAD_AXIS_RIGHTX = 2
SDL_GAMEPAD_AXIS_RIGHTY = 3
SDL_GAMEPAD_AXIS_LEFT_TRIGGER = 4
SDL_GAMEPAD_AXIS_RIGHT_TRIGGER = 5

BUTTON_MAP = {
    SDL_GAMEPAD_BUTTON_SOUTH: BTN_A,
    SDL_GAMEPAD_BUTTON_EAST: BTN_B,
    SDL_GAMEPAD_BUTTON_WEST: BTN_X,
    SDL_GAMEPAD_BUTTON_NORTH: BTN_Y,
    SDL_GAMEPAD_BUTTON_BACK: BTN_SELECT,
    SDL_GAMEPAD_BUTTON_GUIDE: BTN_MODE,
    SDL_GAMEPAD_BUTTON_START: BTN_START,
    SDL_GAMEPAD_BUTTON_LEFT_STICK: BTN_THUMBL,
    SDL_GAMEPAD_BUTTON_RIGHT_STICK: BTN_THUMBR,
    SDL_GAMEPAD_BUTTON_LEFT_SHOULDER: BTN_TL,
    SDL_GAMEPAD_BUTTON_RIGHT_SHOULDER: BTN_TR,
    SDL_GAMEPAD_BUTTON_DPAD_UP: BTN_DPAD_UP,
    SDL_GAMEPAD_BUTTON_DPAD_DOWN: BTN_DPAD_DOWN,
    SDL_GAMEPAD_BUTTON_DPAD_LEFT: BTN_DPAD_LEFT,
    SDL_GAMEPAD_BUTTON_DPAD_RIGHT: BTN_DPAD_RIGHT,
    # The four back/grip paddle buttons your kernel currently drops entirely:
    SDL_GAMEPAD_BUTTON_LEFT_PADDLE1: BTN_TRIGGER_HAPPY1,
    SDL_GAMEPAD_BUTTON_RIGHT_PADDLE1: BTN_TRIGGER_HAPPY2,
    SDL_GAMEPAD_BUTTON_LEFT_PADDLE2: BTN_TRIGGER_HAPPY3,
    SDL_GAMEPAD_BUTTON_RIGHT_PADDLE2: BTN_TRIGGER_HAPPY4,
    SDL_GAMEPAD_BUTTON_TOUCHPAD: BTN_TRIGGER_HAPPY5,
    SDL_GAMEPAD_BUTTON_MISC2: BTN_TRIGGER_HAPPY6,
    SDL_GAMEPAD_BUTTON_MISC3: BTN_TRIGGER_HAPPY7,
    SDL_GAMEPAD_BUTTON_MISC4: BTN_TRIGGER_HAPPY8,
}

AXIS_MAP = {
    SDL_GAMEPAD_AXIS_LEFTX: ABS_X,
    SDL_GAMEPAD_AXIS_LEFTY: ABS_Y,
    SDL_GAMEPAD_AXIS_RIGHTX: ABS_RX,
    SDL_GAMEPAD_AXIS_RIGHTY: ABS_RY,
    SDL_GAMEPAD_AXIS_LEFT_TRIGGER: ABS_Z,
    SDL_GAMEPAD_AXIS_RIGHT_TRIGGER: ABS_RZ,
}


class SDL3Event(ctypes.Structure):
    # We only need the first ~64 bytes (SDL_Event is a big union but every
    # variant starts the same way: type, timestamp, then payload fields we
    # access generically below).
    _fields_ = [("raw", ctypes.c_uint8 * 128)]


def load_sdl3():
    libname = ctypes.util.find_library("SDL3") or "libSDL3.so.0"
    sdl = ctypes.CDLL(libname)

    sdl.SDL_Init.argtypes = [ctypes.c_uint32]
    sdl.SDL_Init.restype = ctypes.c_bool

    sdl.SDL_PollEvent.argtypes = [ctypes.POINTER(SDL3Event)]
    sdl.SDL_PollEvent.restype = ctypes.c_bool

    sdl.SDL_OpenGamepad.argtypes = [ctypes.c_uint32]
    sdl.SDL_OpenGamepad.restype = ctypes.c_void_p

    sdl.SDL_GetGamepads.argtypes = [ctypes.POINTER(ctypes.c_int)]
    sdl.SDL_GetGamepads.restype = ctypes.POINTER(ctypes.c_uint32)

    sdl.SDL_free.argtypes = [ctypes.c_void_p]

    return sdl


def event_field(ev, offset, ctype):
    return ctype.from_buffer_copy(bytes(ev.raw[offset:offset + ctypes.sizeof(ctype)])).value


def main():
    sdl = load_sdl3()
    if not sdl.SDL_Init(SDL_INIT_GAMEPAD):
        print("SDL_Init failed", file=sys.stderr)
        sys.exit(1)

    joy = UInputJoystick()
    print("Virtual joystick created. Waiting for the Steam Controller...")

    gamepad = None
    ev = SDL3Event()

    try:
        while True:
            while sdl.SDL_PollEvent(ctypes.byref(ev)):
                ev_type = event_field(ev, 0, ctypes.c_uint32)

                if ev_type == SDL_EVENT_QUIT:
                    return

                if ev_type == SDL_EVENT_GAMEPAD_ADDED:
                    count = ctypes.c_int()
                    ids = sdl.SDL_GetGamepads(ctypes.byref(count))
                    if count.value > 0:
                        gamepad = sdl.SDL_OpenGamepad(ids[0])
                        print("Steam Controller connected.")
                    sdl.SDL_free(ids)

                elif ev_type == SDL_EVENT_GAMEPAD_REMOVED:
                    gamepad = None
                    print("Steam Controller disconnected.")

                elif ev_type in (SDL_EVENT_GAMEPAD_BUTTON_DOWN, SDL_EVENT_GAMEPAD_BUTTON_UP):
                    # SDL_GamepadButtonEvent: type(u32) timestamp(u64) which(u32) button(u8) down(bool) ...
                    button = event_field(ev, 16, ctypes.c_uint8)
                    pressed = ev_type == SDL_EVENT_GAMEPAD_BUTTON_DOWN
                    code = BUTTON_MAP.get(button)
                    if code is not None:
                        joy.key(code, pressed)

                elif ev_type == SDL_EVENT_GAMEPAD_AXIS_MOTION:
                    # SDL_GamepadAxisEvent: type(u32) timestamp(u64) which(u32) axis(u8) ... value(s16)
                    axis = event_field(ev, 16, ctypes.c_uint8)
                    value = event_field(ev, 20, ctypes.c_int16)
                    code = AXIS_MAP.get(axis)
                    if code is not None:
                        joy.abs_axis(code, value)

            time.sleep(0.004)  # ~250Hz poll, plenty for a gamepad
    except KeyboardInterrupt:
        pass
    finally:
        joy.close()


if __name__ == "__main__":
    if os.geteuid() != 0:
        print("Must run as root (needs /dev/uinput).", file=sys.stderr)
        sys.exit(1)
    main()
