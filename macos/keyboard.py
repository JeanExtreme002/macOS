# -*- coding: utf-8 -*-

"""
Type text, press keys and shortcuts, and control the keyboard backlight.

::

    macos.keyboard.type("Hello, world!")
    macos.keyboard.press("enter")
    macos.keyboard.press("cmd+shift+4")        # the screenshot shortcut
    macos.keyboard.set_brightness(0.5)          # the keyboard backlight
    macos.keyboard.set_layout("ABC")            # the input source

    for key in macos.keyboard.watch():          # every key pressed, in any app
        print(key.shortcut)                     # 'cmd+shift+k'

Typing and pressing keys need the *Accessibility* permission for the app
running Python (your terminal or IDE); without it macOS silently drops the
keystrokes, so these functions raise :class:`~macos.errors.PermissionDeniedError`
instead. The backlight and the layouts need no permission.
"""

import ctypes
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass
from functools import lru_cache
from typing import Dict, Iterator, List, Optional, Tuple

from . import _cf, _events, _objc
from ._system import framework, private_framework
from .errors import MacOSError, NotSupportedError

__all__ = [
    "type",
    "press",
    "hold",
    "caps_lock",
    "KeyPress",
    "watch",
    "key_repeat",
    "set_key_repeat",
    "press_and_hold",
    "set_press_and_hold",
    "standard_function_keys",
    "set_standard_function_keys",
    "autocorrect",
    "set_autocorrect",
    "smart_quotes",
    "set_smart_quotes",
    "smart_dashes",
    "set_smart_dashes",
    "layout",
    "layouts",
    "set_layout",
    "has_permission",
    "request_permission",
    "brightness",
    "set_brightness",
    "auto_brightness",
    "set_auto_brightness",
]

has_permission = _events.has_permission
request_permission = _events.request_permission

# Virtual key codes (HIToolbox's kVK_*), which name physical keys.
_KEYS = {
    "enter": 36,
    "return": 36,
    "tab": 48,
    "space": 49,
    "delete": 51,
    "backspace": 51,
    "forward_delete": 117,
    "escape": 53,
    "esc": 53,
    "left": 123,
    "right": 124,
    "down": 125,
    "up": 126,
    "home": 115,
    "end": 119,
    "page_up": 116,
    "page_down": 121,
    "help": 114,
    "caps_lock": 57,
}
_FUNCTION_KEYS = (122, 120, 99, 118, 96, 97, 98, 100, 101, 109, 103, 111, 105, 107, 113, 106, 64, 79, 80, 90)
_KEYS.update({"f{}".format(number): code for number, code in enumerate(_FUNCTION_KEYS, start=1)})

# The keys of a US keyboard, used when the current layout can't be read.
_US_LAYOUT = {
    "a": 0, "s": 1, "d": 2, "f": 3, "h": 4, "g": 5, "z": 6, "x": 7, "c": 8, "v": 9, "b": 11, "q": 12,
    "w": 13, "e": 14, "r": 15, "y": 16, "t": 17, "1": 18, "2": 19, "3": 20, "4": 21, "6": 22, "5": 23,
    "=": 24, "9": 25, "7": 26, "-": 27, "8": 28, "0": 29, "]": 30, "o": 31, "u": 32, "[": 33, "i": 34,
    "p": 35, "l": 37, "j": 38, "'": 39, "k": 40, ";": 41, "\\": 42, ",": 43, "/": 44, "n": 45, "m": 46,
    ".": 47, "`": 50,
}  # fmt: skip

# What Shift types on those keys.
_US_SHIFTED = dict(zip('~!@#$%^&*()_+{}|:"<>?', "`1234567890-=[]\\;',./"))

# Modifier keys: their flag (kCGEventFlagMask*) and key code.
_MODIFIERS = {
    "cmd": (1 << 20, 55),
    "command": (1 << 20, 55),
    "shift": (1 << 17, 56),
    "option": (1 << 19, 58),
    "opt": (1 << 19, 58),
    "alt": (1 << 19, 58),
    "ctrl": (1 << 18, 59),
    "control": (1 << 18, 59),
    "fn": (1 << 23, 63),
}

_SHIFT = _MODIFIERS["shift"]
_MODIFIER_FLAGS = {code: flag for flag, code in _MODIFIERS.values()}

# Names for the characters "+" can't spell in a shortcut.
_ALIASES = {"plus": "+", "minus": "-"}

# The numeric keypad's keys: shortcuts expect the main keys, which type the same.
_KEYPAD = {65, 67, 69, 71, 75, 76, 78, 81, 82, 83, 84, 85, 86, 87, 88, 89, 91, 92}

# The most UTF-16 units one keyboard event carries.
_CHUNK = 20


@lru_cache(maxsize=None)
def _text_input() -> ctypes.CDLL:
    carbon = framework("Carbon")
    pointer = ctypes.c_void_p
    carbon.TISCopyCurrentKeyboardLayoutInputSource.argtypes = ()
    carbon.TISCopyCurrentKeyboardLayoutInputSource.restype = pointer
    carbon.TISGetInputSourceProperty.argtypes = (pointer, pointer)
    carbon.TISGetInputSourceProperty.restype = pointer
    carbon.LMGetKbdType.argtypes = ()
    carbon.LMGetKbdType.restype = ctypes.c_uint8
    carbon.UCKeyTranslate.argtypes = (
        pointer,
        ctypes.c_uint16,
        ctypes.c_uint16,
        ctypes.c_uint32,
        ctypes.c_uint32,
        ctypes.c_uint32,
        ctypes.POINTER(ctypes.c_uint32),
        ctypes.c_ulong,
        ctypes.POINTER(ctypes.c_ulong),
        ctypes.POINTER(ctypes.c_uint16),
    )
    carbon.UCKeyTranslate.restype = ctypes.c_int32
    carbon.TISCopyCurrentKeyboardInputSource.argtypes = ()
    carbon.TISCopyCurrentKeyboardInputSource.restype = pointer
    carbon.TISCreateInputSourceList.argtypes = (pointer, ctypes.c_bool)
    carbon.TISCreateInputSourceList.restype = pointer
    carbon.TISSelectInputSource.argtypes = (pointer,)
    carbon.TISSelectInputSource.restype = ctypes.c_int32
    return carbon


def _layout() -> Dict[str, Tuple[int, bool]]:
    """
    What each key of the current keyboard layout types: ``{"a": (0, False), "?": (44, True)}``.

    The ``bool`` says whether it needs Shift. Falls back to a US keyboard
    when the layout can't be read: macOS only allows it on the main thread.
    """
    fallback = {char: (code, False) for char, code in _US_LAYOUT.items()}
    fallback.update({char: (_US_LAYOUT[base], True) for char, base in _US_SHIFTED.items()})
    if threading.current_thread() is not threading.main_thread():
        return fallback
    carbon = _text_input()
    cf = framework("CoreFoundation")
    cf.CFDataGetBytePtr.argtypes = (ctypes.c_void_p,)
    cf.CFDataGetBytePtr.restype = ctypes.c_void_p
    cf.CFRelease.argtypes = (ctypes.c_void_p,)
    cf.CFRelease.restype = None
    source = carbon.TISCopyCurrentKeyboardLayoutInputSource()
    if not source:
        return fallback
    try:
        key = ctypes.c_void_p.in_dll(carbon, "kTISPropertyUnicodeKeyLayoutData").value
        data = carbon.TISGetInputSourceProperty(source, key)
        if not data:
            return fallback
        layout = cf.CFDataGetBytePtr(data)
        keyboard_type = carbon.LMGetKbdType()
        found: Dict[str, Tuple[int, bool]] = {}
        # Unshifted characters win: "1" is the 1 key, not Shift+something.
        for shifted, modifiers in ((False, 0), (True, 0x02)):  # 0x02: shiftKey >> 8
            for code in range(128):
                if code in _KEYPAD:
                    continue
                dead = ctypes.c_uint32()
                length = ctypes.c_ulong()
                chars = (ctypes.c_uint16 * 4)()
                status = carbon.UCKeyTranslate(
                    layout, code, 3, modifiers, keyboard_type, 1, ctypes.byref(dead), 4, ctypes.byref(length), chars
                )
                if status == 0 and length.value == 1:
                    char = chr(chars[0])
                    if char.isprintable() and char.strip() and char not in found:
                        found[char] = (code, shifted)
        return found or fallback
    finally:
        cf.CFRelease(source)


def _parse(keys: str) -> Tuple[List[Tuple[int, int]], int, bool]:
    """
    Split ``"cmd+shift+4"`` into its modifiers ``[(flag, key code), ...]``, the key code and whether Shift is added.
    """
    text = keys.strip()
    if not text:
        raise ValueError("press() needs a key, such as 'enter' or 'cmd+c'")
    # A last "+" is the key itself: "+" or "cmd++".
    if text == "+":
        parts = ["+"]
    elif text.endswith("++"):
        parts = text[:-2].split("+") + ["+"]
    else:
        parts = text.split("+")
    names, key = [part.strip() for part in parts[:-1]], parts[-1].strip() or parts[-1]
    modifiers = []
    for name in names:
        if name.lower() not in _MODIFIERS:
            raise ValueError("{!r} is not a modifier; use cmd, shift, option, ctrl or fn".format(name))
        modifiers.append(_MODIFIERS[name.lower()])
    if not key:
        raise ValueError("{!r} has no key after the modifiers".format(keys))
    if key.lower() in _KEYS:
        return modifiers, _KEYS[key.lower()], False
    if key.lower() in _MODIFIERS:  # a modifier alone, such as "shift"
        return modifiers, _MODIFIERS[key.lower()][1], False
    key = _ALIASES.get(key.lower(), key)
    if len(key) == 1:
        layout = _layout()
        # Letters work in either case, like the keys' labels: "cmd+C" is Cmd+C.
        for char in (key.lower(), key):
            if char in layout:
                code, shifted = layout[char]
                return modifiers, code, shifted
        raise ValueError("no key types {!r} on this keyboard layout; use type() for text".format(key))
    raise ValueError("unknown key {!r}; use a character or a name such as 'enter', 'tab', 'left' or 'f5'".format(key))


def _key_event(code: int, down: bool, flags: int) -> int:
    event = _events.graphics().CGEventCreateKeyboardEvent(None, code, down)
    if not event:
        raise MacOSError("could not create a keyboard event")
    _events.graphics().CGEventSetFlags(event, flags | _events.held_flags())
    return event


def press(keys: str, *, times: int = 1) -> None:
    """
    Press a key or a shortcut, like ``"enter"``, ``"a"``, ``"cmd+c"`` or ``"cmd+shift+4"``, ``times`` times.

    Modifiers are ``cmd``, ``shift``, ``option`` (or ``alt``), ``ctrl`` and
    ``fn``, joined with ``+``. Keys are characters, found on the current
    keyboard layout (so ``"cmd+z"`` is undo on an AZERTY keyboard too), or
    names: ``enter``, ``tab``, ``space``, ``delete`` (backspace),
    ``forward_delete``, ``escape``, ``left``, ``right``, ``up``, ``down``,
    ``home``, ``end``, ``page_up``, ``page_down``, ``f1`` to ``f20``...

    The keystrokes go to the app in front. Needs the Accessibility permission.
    """
    if times < 1:
        raise ValueError("times must be at least 1, not {}".format(times))
    modifiers, code, shifted = _parse(keys)
    if shifted and _SHIFT not in modifiers:
        modifiers.append(_SHIFT)
    _events.require_permission()
    # A modifier pressed alone ("shift") sets its own flag while it's down.
    own = _MODIFIER_FLAGS.get(code, 0)
    for _ in range(times):
        flags = 0
        for flag, modifier in modifiers:
            flags |= flag
            _events.post(_key_event(modifier, True, flags))
        _events.post(_key_event(code, True, flags | own))
        _events.post(_key_event(code, False, flags))
        for flag, modifier in reversed(modifiers):
            flags &= ~flag
            _events.post(_key_event(modifier, False, flags))


@contextmanager
def hold(*keys: str) -> Iterator[None]:
    """
    Hold keys down while the ``with`` block runs, and release them at the end.

    For Shift-clicks, Cmd-clicks, Option-drags, or a key held in a game::

        with macos.keyboard.hold("shift"):
            macos.mouse.click(100, 200)
            macos.mouse.click(100, 400)      # selects the range in between

        with macos.keyboard.hold("cmd", "option"):
            macos.mouse.drag(600, 300)

    Each key is written as for :func:`press` (``"cmd+shift"`` holds both).
    The keys are released even when the block raises. Needs the
    Accessibility permission.
    """
    if not keys:
        raise ValueError("hold() needs at least one key, such as 'shift'")
    presses: List[Tuple[int, int]] = []
    for spec in keys:
        modifiers, code, shifted = _parse(spec)
        if shifted and _SHIFT not in modifiers:
            modifiers.append(_SHIFT)
        for entry in modifiers + [(_MODIFIER_FLAGS.get(code, 0), code)]:
            if entry not in presses:
                presses.append(entry)
    _events.require_permission()
    pressed: List[Tuple[int, int]] = []
    try:
        for flag, code in presses:
            _events.HELD.append(flag)
            pressed.append((flag, code))
            _events.post(_key_event(code, True, 0))
        yield
    finally:
        for flag, code in reversed(pressed):
            _events.HELD.remove(flag)
            _events.post(_key_event(code, False, 0))


_ALPHA_SHIFT = 1 << 16  # kCGEventFlagMaskAlphaShift: Caps Lock is on
_HID_STATE = 1  # kCGEventSourceStateHIDSystemState: the hardware's own state


def caps_lock() -> bool:
    """Whether Caps Lock is on. Needs no permission."""
    return bool(_events.graphics().CGEventSourceFlagsState(_HID_STATE) & _ALPHA_SHIFT)


def _chunks(text: str, size: int) -> List[str]:
    """Split ``text`` into pieces of at most ``size`` UTF-16 units, never inside a character."""
    pieces: List[str] = []
    current, units = "", 0
    for char in text:
        width = len(char.encode("utf-16-le")) // 2
        if current and units + width > size:
            pieces.append(current)
            current, units = "", 0
        current += char
        units += width
    if current:
        pieces.append(current)
    return pieces


def type(text: str, *, interval: float = 0.0) -> None:
    """
    Type ``text`` into the app in front, as if typed on the keyboard.

    Any character works (accents, emoji...), whatever the keyboard layout.
    New lines press Enter and tabs press Tab. ``interval`` is the pause
    between characters, in seconds, for apps that can't keep up. Needs the
    Accessibility permission.
    """
    if interval < 0:
        raise ValueError("interval must not be negative, not {}".format(interval))
    _events.require_permission()
    cg = _events.graphics()
    pieces: List[str] = []
    for line_index, line in enumerate(text.split("\n")):
        if line_index:
            pieces.append("\n")
        for tab_index, part in enumerate(line.split("\t")):
            if tab_index:
                pieces.append("\t")
            if part:
                pieces.extend(_chunks(part, 1 if interval else _CHUNK))
    for piece in pieces:
        if piece in ("\n", "\t"):
            code = _KEYS["enter" if piece == "\n" else "tab"]
            _events.post(_key_event(code, True, 0))
            _events.post(_key_event(code, False, 0))
        else:
            encoded = piece.encode("utf-16-le")
            units = (ctypes.c_uint16 * (len(encoded) // 2)).from_buffer_copy(encoded)
            for down in (True, False):
                event = _key_event(0, down, 0)
                cg.CGEventKeyboardSetUnicodeString(event, len(units), units)
                _events.post(event)
        if interval:
            time.sleep(interval)


# Keyboard layouts (input sources), through Text Input Sources.


def _tis_constant(name: str) -> int:
    return ctypes.c_void_p.in_dll(_text_input(), name).value or 0


def _source_property(source: int, name: str) -> str:
    return _cf.to_str(_text_input().TISGetInputSourceProperty(source, _tis_constant(name))) or ""


@contextmanager
def _input_sources() -> Iterator[List[Tuple[int, str, str]]]:
    """The enabled keyboard input sources, as ``(source, name, id)``, alive inside the ``with`` block."""
    cf = _cf.lib()
    wanted = _cf.dictionary(
        {
            _tis_constant("kTISPropertyInputSourceCategory"): _tis_constant("kTISCategoryKeyboardInputSource"),
            _tis_constant("kTISPropertyInputSourceIsSelectCapable"): _cf.constant(cf, "kCFBooleanTrue"),
        }
    )
    with _cf.owned(wanted):
        found = _text_input().TISCreateInputSourceList(wanted, False)
    with _cf.owned(found):
        yield [
            (
                source,
                _source_property(source, "kTISPropertyLocalizedName"),
                _source_property(source, "kTISPropertyInputSourceID"),
            )
            for source in _cf.items(found)
        ]


def layouts() -> List[str]:
    """
    Return the keyboard layouts and input methods enabled in the menu bar's input menu: ``['ABC', 'Brazilian']``.

    Add more in System Settings › Keyboard › Text Input.
    """
    with _input_sources() as sources:
        return [name for _, name, _ in sources]


def layout() -> str:
    """Return the keyboard layout (input source) in use, such as ``'ABC'`` or ``'Brazilian'``."""
    carbon = _text_input()
    with _cf.owned(carbon.TISCopyCurrentKeyboardInputSource()) as source:
        if not source:
            raise MacOSError("could not read the keyboard layout")
        return _source_property(source, "kTISPropertyLocalizedName")


def set_layout(name: str) -> str:
    """
    Switch to one of the enabled keyboard layouts, like picking it in the input menu, and return its name.

    ``name`` is as :func:`layouts` returns it, its identifier (such as
    ``'com.apple.keylayout.ABC'``) or part of its name when that matches only
    one layout.
    """
    with _input_sources() as sources:
        exact = [entry for entry in sources if name in (entry[1], entry[2])]
        loose = [entry for entry in sources if name.casefold() in entry[1].casefold()]
        chosen = exact or loose
        names = ", ".join(repr(entry[1]) for entry in sources)
        if not chosen:
            raise ValueError("no enabled keyboard layout matches {!r}; enabled: {}".format(name, names))
        if len(chosen) > 1:
            raise ValueError("{!r} matches several keyboard layouts ({}); use the full name".format(name, names))
        source, found, _ = chosen[0]
        status = _text_input().TISSelectInputSource(source)
    if status != 0:
        raise MacOSError("could not switch to {!r} (OSStatus {})".format(found, status))
    return found


# The keyboard backlight, through CoreBrightness (a private framework).


def _backlight() -> Tuple[int, int]:
    """The ``KeyboardBrightnessClient`` (autoreleased) and the backlit keyboard's ID. Call inside a pool."""
    private_framework("CoreBrightness")
    framework("Foundation")
    try:
        _objc.cls("KeyboardBrightnessClient")
    except LookupError:
        raise NotSupportedError("this version of macOS doesn't expose the keyboard backlight") from None
    client = _objc.new("KeyboardBrightnessClient")
    ids = [
        int(_objc.send(number, "unsignedLongLongValue", restype=ctypes.c_uint64))
        for number in _objc.nsarray(_objc.send(client, "copyKeyboardBacklightIDs"))
    ]
    if not ids:
        raise NotSupportedError("this Mac has no keyboard backlight")
    built_in = [
        keyboard
        for keyboard in ids
        if _objc.send(client, "isKeyboardBuiltIn:", keyboard, argtypes=(ctypes.c_uint64,), restype=_objc.BOOL)
    ]
    return client, (built_in or ids)[0]


def brightness() -> float:
    """
    The keyboard backlight's brightness, from 0.0 (off) to 1.0.

    Raises :class:`~macos.errors.NotSupportedError` on a Mac without a
    backlit keyboard.
    """
    with _objc.autorelease_pool():
        client, keyboard = _backlight()
        value = _objc.send(client, "brightnessForKeyboard:", keyboard, argtypes=(ctypes.c_uint64,), restype=ctypes.c_float)
    return round(float(value), 3)


def set_brightness(value: float) -> None:
    """
    Set the keyboard backlight's brightness, from 0.0 (off) to 1.0.

    With automatic brightness on (see :func:`auto_brightness`), macOS keeps
    adjusting it to the room's light afterwards.
    """
    if not 0.0 <= value <= 1.0:
        raise ValueError("brightness must be from 0.0 to 1.0, not {}".format(value))
    with _objc.autorelease_pool():
        client, keyboard = _backlight()
        ok = _objc.send(
            client,
            "setBrightness:forKeyboard:",
            float(value),
            keyboard,
            argtypes=(ctypes.c_float, ctypes.c_uint64),
            restype=_objc.BOOL,
        )
    if not ok:
        raise MacOSError("macOS refused to change the keyboard backlight")


def auto_brightness() -> bool:
    """Whether the keyboard backlight follows the room's light, as set in System Settings › Keyboard."""
    with _objc.autorelease_pool():
        client, keyboard = _backlight()
        return bool(
            _objc.send(
                client, "isAutoBrightnessEnabledForKeyboard:", keyboard, argtypes=(ctypes.c_uint64,), restype=_objc.BOOL
            )
        )


def set_auto_brightness(on: bool) -> None:
    """Turn on or off the keyboard backlight's automatic brightness."""
    with _objc.autorelease_pool():
        client, keyboard = _backlight()
        ok = _objc.send(
            client,
            "enableAutoBrightness:forKeyboard:",
            bool(on),
            keyboard,
            argtypes=(_objc.BOOL, ctypes.c_uint64),
            restype=_objc.BOOL,
        )
    if not ok:
        raise MacOSError("macOS refused to change the keyboard backlight")


@dataclass(frozen=True)
class KeyPress:
    """A key pressed, as :func:`watch` sees it."""

    key: str
    """The key, named as :func:`press` takes it: ``'a'``, ``'1'``, ``'enter'``, ``'f5'``, ``'left'``..."""
    modifiers: Tuple[str, ...]
    """The modifiers held, among ``'cmd'``, ``'ctrl'``, ``'option'`` and ``'shift'``."""
    text: str
    """What the key typed, such as ``'A'`` with Shift; ``''`` for keys that type nothing."""
    code: int
    """The virtual key code, which names the physical key whatever the layout."""
    repeat: bool
    """Whether it comes from holding the key down."""

    @property
    def shortcut(self) -> str:
        """The key and its modifiers as :func:`press` and :mod:`macos.hotkeys` write them, such as ``'cmd+shift+k'``."""
        return "+".join(self.modifiers + (self.key,))


# Names for the codes of the keys that type nothing (the first name of each in _KEYS).
_KEY_NAMES: Dict[int, str] = {}
for _name, _code in _KEYS.items():
    _KEY_NAMES.setdefault(_code, _name)

_WATCHED_MODIFIERS = (("cmd", 1 << 20), ("ctrl", 1 << 18), ("option", 1 << 19), ("shift", 1 << 17))
_KEY_DOWN = 10  # kCGEventKeyDown
_AUTOREPEAT = 8  # kCGKeyboardEventAutorepeat
_KEYCODE = 9  # kCGKeyboardEventKeycode


def _typed(event: int) -> str:
    length = ctypes.c_ulong()
    chars = (ctypes.c_uint16 * 8)()
    _events.graphics().CGEventKeyboardGetUnicodeString(event, len(chars), ctypes.byref(length), chars)
    text = bytes(chars)[: length.value * 2].decode("utf-16-le", "replace")
    return text if text.isprintable() else ""


def watch(*, timeout: Optional[float] = None) -> Iterator[KeyPress]:
    """
    Yield a :class:`KeyPress` for each key pressed, in any app, as it happens.

    ::

        for key in macos.keyboard.watch():
            if key.shortcut == "ctrl+option+q":
                break
            log.write(key.text)

    It only listens: the keys still reach the app in front (to take a
    shortcut for yourself, see :mod:`macos.hotkeys`). It goes on until you
    ``break`` out of the loop, or ``timeout`` seconds pass. Needs the *Input
    Monitoring* permission. macOS hides the keys typed in password fields.
    """
    unshifted = {code: char for char, (code, shifted) in _layout().items() if not shifted}
    cg = _events.graphics()

    def convert(kind: int, event: int) -> KeyPress:
        code = int(cg.CGEventGetIntegerValueField(event, _KEYCODE))
        flags = cg.CGEventGetFlags(event)
        text = _typed(event)
        key = _KEY_NAMES.get(code) or unshifted.get(code) or text.lower() or "key{}".format(code)
        return KeyPress(
            key=key,
            modifiers=tuple(name for name, flag in _WATCHED_MODIFIERS if flags & flag),
            text="" if code in _KEY_NAMES and code != _KEYS["space"] else text,
            code=code,
            repeat=bool(cg.CGEventGetIntegerValueField(event, _AUTOREPEAT)),
        )

    return _events.listen(
        [_KEY_DOWN],
        convert,
        timeout,
        "listening to the keyboard needs the Input Monitoring permission: allow the app running Python (your "
        "terminal or IDE) in System Settings › Privacy & Security › Input Monitoring, then restart it",
    )


# --- Settings ---------------------------------------------------------------

_KEY_REPEAT_UNIT = 0.015  # KeyRepeat and InitialKeyRepeat count 15 ms steps


def _global(key: str, default: object) -> object:
    from . import defaults

    return defaults.read(defaults.GLOBAL, key, default=default)


def _set_global(key: str, value: object, apply: bool = True) -> None:
    from . import defaults
    from ._system import apply_input_settings

    defaults.write(defaults.GLOBAL, key, value)
    if apply:
        apply_input_settings()


def key_repeat() -> Tuple[float, float]:
    """``(interval, delay)``: seconds between the repeats of a held key, and before the first one."""
    interval = float(_global("KeyRepeat", 6)) * _KEY_REPEAT_UNIT  # type: ignore[arg-type]
    delay = float(_global("InitialKeyRepeat", 25)) * _KEY_REPEAT_UNIT  # type: ignore[arg-type]
    return round(interval, 3), round(delay, 3)


def set_key_repeat(interval: Optional[float] = None, *, delay: Optional[float] = None) -> None:
    """
    Set how fast a held key repeats: ``interval`` seconds between repeats, after ``delay`` seconds.

    ::

        macos.keyboard.set_key_repeat(0.03, delay=0.25)   # fast, the favorite of developers

    System Settings' fastest are 0.03 and 0.225 seconds; shorter ones work
    too. Takes effect at the next login.
    """
    if interval is None and delay is None:
        raise ValueError("give interval, delay, or both")
    for label, value in (("interval", interval), ("delay", delay)):
        if value is not None and value <= 0:
            raise ValueError("{} must be positive, not {}".format(label, value))
    if interval is not None:
        _set_global("KeyRepeat", max(1, round(interval / _KEY_REPEAT_UNIT)), apply=False)
    if delay is not None:
        _set_global("InitialKeyRepeat", max(1, round(delay / _KEY_REPEAT_UNIT)), apply=False)


def press_and_hold() -> bool:
    """Whether holding a key shows the accents menu (é, ê, è...) instead of repeating it."""
    return bool(_global("ApplePressAndHoldEnabled", True))


def set_press_and_hold(on: bool = True) -> None:
    """
    Show the accents menu when a key is held, or repeat the key instead (``False``).

    Apps pick it up when they're reopened.
    """
    _set_global("ApplePressAndHoldEnabled", bool(on), apply=False)


def standard_function_keys() -> bool:
    """Whether F1, F2... act as function keys without holding Fn (instead of brightness, volume...)."""
    return bool(_global("com.apple.keyboard.fnState", False))


def set_standard_function_keys(on: bool = True) -> None:
    """Make F1, F2... act as function keys without Fn, like System Settings › Keyboard › Keyboard Shortcuts › Function Keys."""
    _set_global("com.apple.keyboard.fnState", bool(on))


def autocorrect() -> bool:
    """Whether macOS corrects spelling as you type."""
    return bool(_global("NSAutomaticSpellingCorrectionEnabled", True))


def set_autocorrect(on: bool = True) -> None:
    """Correct spelling as you type, or not. Apps pick it up when they're reopened."""
    _set_global("NSAutomaticSpellingCorrectionEnabled", bool(on), apply=False)
    _set_global("WebAutomaticSpellingCorrectionEnabled", bool(on), apply=False)


def smart_quotes() -> bool:
    """Whether typed quotes become curly ones (“ ”), which break code pasted anywhere."""
    return bool(_global("NSAutomaticQuoteSubstitutionEnabled", True))


def set_smart_quotes(on: bool = True) -> None:
    """Turn typed quotes into curly ones, or keep them straight (``False``). Apps pick it up when reopened."""
    _set_global("NSAutomaticQuoteSubstitutionEnabled", bool(on), apply=False)


def smart_dashes() -> bool:
    """Whether a typed ``--`` becomes a dash (—)."""
    return bool(_global("NSAutomaticDashSubstitutionEnabled", True))


def set_smart_dashes(on: bool = True) -> None:
    """Turn a typed ``--`` into a dash, or keep it (``False``). Apps pick it up when reopened."""
    _set_global("NSAutomaticDashSubstitutionEnabled", bool(on), apply=False)
