# -*- coding: utf-8 -*-

"""
React to what happens on the Mac: sleep and wake, the screen locking, apps opening and quitting...

::

    macos.events.on("wake", lambda event: print("good morning"))
    macos.events.on("app_launched", lambda event: print(event.app.name, "opened"))
    macos.events.run()                        # until macos.events.stop() or Ctrl-C

    macos.events.wait("screen_unlocked")      # or just wait for one

The events come from ``NSWorkspace`` and the system's distributed
notifications, the same ones apps listen to. No permission is needed.
"""

import collections
import ctypes
import inspect
import threading
import time
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from . import _cf, _objc, apps
from ._system import framework

__all__ = ["Event", "Handler", "NAMES", "on", "off", "run", "stop", "wait"]

_WORKSPACE, _DISTRIBUTED = "workspace", "distributed"
# Events from other system sources than notification centers, each watched while listening.
_POWER, _NETWORK, _USB, _DISPLAYS = "power", "network", "usb", "displays"
_WATCHED = (_POWER, _NETWORK, _USB, _DISPLAYS)

# Our name: (notification center, notification name).
_NOTIFICATIONS: Dict[str, Tuple[str, str]] = {
    "sleep": (_WORKSPACE, "NSWorkspaceWillSleepNotification"),
    "wake": (_WORKSPACE, "NSWorkspaceDidWakeNotification"),
    "display_sleep": (_WORKSPACE, "NSWorkspaceScreensDidSleepNotification"),
    "display_wake": (_WORKSPACE, "NSWorkspaceScreensDidWakeNotification"),
    "screen_locked": (_DISTRIBUTED, "com.apple.screenIsLocked"),
    "screen_unlocked": (_DISTRIBUTED, "com.apple.screenIsUnlocked"),
    "space_changed": (_WORKSPACE, "NSWorkspaceActiveSpaceDidChangeNotification"),
    "app_launched": (_WORKSPACE, "NSWorkspaceDidLaunchApplicationNotification"),
    "app_quit": (_WORKSPACE, "NSWorkspaceDidTerminateApplicationNotification"),
    "app_activated": (_WORKSPACE, "NSWorkspaceDidActivateApplicationNotification"),
    "app_hidden": (_WORKSPACE, "NSWorkspaceDidHideApplicationNotification"),
    "app_unhidden": (_WORKSPACE, "NSWorkspaceDidUnhideApplicationNotification"),
    "volume_mounted": (_WORKSPACE, "NSWorkspaceDidMountNotification"),
    "volume_unmounted": (_WORKSPACE, "NSWorkspaceDidUnmountNotification"),
    # IOKit's power-source notification, which also comes as the battery drains: only the
    # changes between the charger and the battery are events.
    "power_connected": (_POWER, ""),
    "power_disconnected": (_POWER, ""),
    "network_changed": (_NETWORK, ""),
    "usb_connected": (_USB, ""),
    "usb_disconnected": (_USB, ""),
    "displays_changed": (_DISPLAYS, ""),
}

NAMES = tuple(_NOTIFICATIONS)
"""The events :func:`on` and :func:`wait` accept."""


@dataclass(frozen=True)
class Event:
    """Something that happened, passed to the callbacks."""

    name: str
    """One of :data:`NAMES`, such as ``'wake'`` or ``'app_launched'``."""
    app: Optional[apps.App] = None
    """For the ``app_*`` events: the app that launched, quit or came to the front."""
    path: Optional[Path] = None
    """For ``volume_mounted`` and ``volume_unmounted``: where the volume is (or was) mounted."""
    device: Optional[str] = None
    """For ``usb_connected`` and ``usb_disconnected``: the device's name, such as ``'USB Keyboard'``."""


class Handler:
    """A callback registered with :func:`on`. :meth:`remove` unregisters it."""

    def __init__(self, name: str, callback: Callable[..., object]) -> None:
        self.name = name
        self.callback = callback

    def __repr__(self) -> str:
        return "Handler({!r})".format(self.name)

    def remove(self) -> None:
        """Stop calling this callback."""
        off(self)


_lock = threading.Lock()
_handlers: List[Handler] = []
_stop = threading.Event()


def _check(name: str) -> None:
    if name not in _NOTIFICATIONS:
        raise ValueError("unknown event {!r}; use one of {}".format(name, ", ".join(NAMES)))


def on(name: str, callback: Callable[..., object]) -> Handler:
    """
    Call ``callback(event)`` each time ``name`` happens, while :func:`run` runs; return a :class:`Handler`.

    ``name`` is one of :data:`NAMES`:

    - ``'sleep'`` and ``'wake'``: the Mac goes to sleep, and wakes up.
    - ``'display_sleep'`` and ``'display_wake'``: the displays turn off and on.
    - ``'screen_locked'`` and ``'screen_unlocked'``.
    - ``'space_changed'``: another Space (desktop) or full-screen app is shown.
    - ``'app_launched'``, ``'app_quit'``, ``'app_activated'`` (came to the
      front), ``'app_hidden'`` and ``'app_unhidden'``, with the
      :class:`~macos.apps.App` in ``event.app``.
    - ``'volume_mounted'`` and ``'volume_unmounted'`` (disks, USB drives,
      disk images), with the mount point in ``event.path``.
    - ``'power_connected'`` and ``'power_disconnected'``: the Mac starts or
      stops running on its charger (never on a Mac without a battery).
    - ``'network_changed'``: the connection changed: another Wi-Fi network,
      a cable plugged in, offline or back online.
    - ``'usb_connected'`` and ``'usb_disconnected'``, with the device's name
      in ``event.device``.
    - ``'displays_changed'``: a display was connected, disconnected,
      rearranged or set to another resolution.

    To wait for dark or light mode to switch, see :func:`macos.appearance.wait_for_change`.

    The callback may also take no arguments. One registered for several
    events can tell them apart by ``event.name``.
    """
    _check(name)
    handler = Handler(name, callback)
    with _lock:
        _handlers.append(handler)
    return handler


def off(handler: "Handler | str") -> None:
    """Remove a :class:`Handler`, or every callback of an event name."""
    with _lock:
        if isinstance(handler, Handler):
            if handler in _handlers:
                _handlers.remove(handler)
        else:
            _check(handler)
            _handlers[:] = [registered for registered in _handlers if registered.name != handler]


def stop() -> None:
    """Make :func:`run` return, from a callback or from another thread."""
    _stop.set()


@lru_cache(maxsize=None)
def _notification_names() -> Dict[str, str]:
    """Notification name → our name. AppKit's names are read from its constants."""
    appkit = framework("AppKit")
    names = {}
    for ours, (center, notification) in _NOTIFICATIONS.items():
        if center in _WATCHED:
            continue
        if center == _WORKSPACE:
            constant = ctypes.c_void_p.in_dll(appkit, notification).value
            notification = _objc.pystring(constant) or notification
        names[notification] = ours
    return names


def _center(kind: str) -> int:
    if kind == _WORKSPACE:
        return _objc.send(_objc.send(_objc.cls("NSWorkspace"), "sharedWorkspace"), "notificationCenter")
    return _objc.send(_objc.cls("NSDistributedNotificationCenter"), "defaultCenter")


_DELIVER_IMMEDIATELY = 4  # NSNotificationSuspensionBehaviorDeliverImmediately

_received: "collections.deque[Event]" = collections.deque()
_Handle = ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)


def _event(notification: int) -> Optional[Event]:
    name = _notification_names().get(_objc.pystring(_objc.send(notification, "name")) or "")
    if name is None:
        return None
    info = _objc.send(notification, "userInfo")
    app, path = None, None
    if info and name.startswith("app_"):
        running = _objc.send(info, "objectForKey:", _objc.nsstring("NSWorkspaceApplicationKey"), argtypes=(_objc.id,))
        if running:
            app = apps._app(running)
    if info and name.startswith("volume_"):
        device = _objc.pystring(_objc.send(info, "objectForKey:", _objc.nsstring("NSDevicePath"), argtypes=(_objc.id,)))
        path = Path(device) if device else None
    return Event(name, app, path)


def _handle(self: int, selector: int, notification: int) -> None:
    # Only records the event: the callbacks run outside AppKit's call, where an exception can propagate.
    try:
        event = _event(notification)
    except Exception:  # an exception must not cross back into Objective-C
        return
    if event is not None:
        _received.append(event)


_PowerCallback = ctypes.CFUNCTYPE(None, ctypes.c_void_p)


@lru_cache(maxsize=None)
def _iokit() -> ctypes.CDLL:
    io = framework("IOKit")
    io.IOPSCopyPowerSourcesInfo.argtypes = ()
    io.IOPSCopyPowerSourcesInfo.restype = ctypes.c_void_p
    io.IOPSGetProvidingPowerSourceType.argtypes = (ctypes.c_void_p,)
    io.IOPSGetProvidingPowerSourceType.restype = ctypes.c_void_p
    io.IOPSNotificationCreateRunLoopSource.argtypes = (_PowerCallback, ctypes.c_void_p)
    io.IOPSNotificationCreateRunLoopSource.restype = ctypes.c_void_p
    return io


def _on_charger() -> bool:
    """Whether the Mac runs on its charger (or on mains power, without a battery)."""
    with _cf.owned(_iokit().IOPSCopyPowerSourcesInfo()) as info:
        return _cf.to_str(_iokit().IOPSGetProvidingPowerSourceType(info)) != "Battery Power"


class _PowerWatch:
    """Turns IOKit's power-source notifications, on this thread's run loop, into power events."""

    def __init__(self) -> None:
        self.plugged = _on_charger()
        self.callback = _PowerCallback(self.changed)  # kept alive while the source is scheduled
        self.source = _RunLoopSource(_iokit().IOPSNotificationCreateRunLoopSource(self.callback, None))

    def changed(self, context: int) -> None:
        try:
            plugged = _on_charger()
        except Exception:  # an exception must not cross back into IOKit
            return
        if plugged != self.plugged:
            self.plugged = plugged
            _received.append(Event("power_connected" if plugged else "power_disconnected"))

    def close(self) -> None:
        if self.source.source:
            _cf.release(self.source.source)
        self.source.close()


_Store = ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)
_NETWORK_KEYS = ("State:/Network/Global/IPv4", "State:/Network/Global/IPv6")


class _RunLoopSource:
    """A CoreFoundation run loop source on this thread, removed and released by :meth:`close`."""

    def __init__(self, source: Optional[int]) -> None:
        run_loop = framework("CoreFoundation")
        run_loop.CFRunLoopGetCurrent.restype = ctypes.c_void_p
        run_loop.CFRunLoopAddSource.argtypes = (ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)
        run_loop.CFRunLoopRemoveSource.argtypes = (ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)
        self.source = source
        self.loop = run_loop.CFRunLoopGetCurrent()
        self.mode = ctypes.c_void_p.in_dll(run_loop, "kCFRunLoopDefaultMode")
        if source:
            run_loop.CFRunLoopAddSource(self.loop, source, self.mode)

    def close(self) -> None:
        if self.source:
            framework("CoreFoundation").CFRunLoopRemoveSource(self.loop, self.source, self.mode)
            self.source = None


@lru_cache(maxsize=None)
def _configuration() -> ctypes.CDLL:
    sc = framework("SystemConfiguration")
    pointer = ctypes.c_void_p
    sc.SCDynamicStoreCreate.argtypes = (pointer, pointer, _Store, pointer)
    sc.SCDynamicStoreCreate.restype = pointer
    sc.SCDynamicStoreSetNotificationKeys.argtypes = (pointer, pointer, pointer)
    sc.SCDynamicStoreSetNotificationKeys.restype = ctypes.c_bool
    sc.SCDynamicStoreCreateRunLoopSource.argtypes = (pointer, pointer, ctypes.c_long)
    sc.SCDynamicStoreCreateRunLoopSource.restype = pointer
    sc.SCDynamicStoreCopyValue.argtypes = (pointer, pointer)
    sc.SCDynamicStoreCopyValue.restype = pointer
    return sc


class _NetworkWatch:
    """
    Network events, from the dynamic store configd keeps: the global IPv4 and IPv6 state.

    A change touches several keys at once; only a change of the state itself
    (interface, router, addresses) is an event.
    """

    def __init__(self) -> None:
        sc = _configuration()
        self.callback = _Store(self.changed)
        with _cf.owned(_cf.string("pymacos.events")) as name:
            self.store = sc.SCDynamicStoreCreate(None, name, self.callback, None)
        self.state = self.read()
        with _cf.owned(_cf.from_python(list(_NETWORK_KEYS))) as keys:
            sc.SCDynamicStoreSetNotificationKeys(self.store, keys, None)
        self.source = _RunLoopSource(sc.SCDynamicStoreCreateRunLoopSource(None, self.store, 0) if self.store else None)

    def read(self) -> Tuple[object, ...]:
        values = []
        for key in _NETWORK_KEYS:
            with _cf.owned(_cf.string(key)) as name:
                with _cf.owned(_configuration().SCDynamicStoreCopyValue(self.store, name)) as value:
                    values.append(repr(_cf.to_python(value)) if value else None)
        return tuple(values)

    def changed(self, store: int, keys: int, info: int) -> None:
        try:
            state = self.read()
        except Exception:  # an exception must not cross back into SystemConfiguration
            return
        if state != self.state:
            self.state = state
            _received.append(Event("network_changed"))

    def close(self) -> None:
        if self.source.source:
            _cf.release(self.source.source)
        self.source.close()
        _cf.release(self.store)
        self.store = None


_Matched = ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.c_uint32)


@lru_cache(maxsize=None)
def _io_registry() -> ctypes.CDLL:
    io = framework("IOKit")
    pointer, handle = ctypes.c_void_p, ctypes.c_uint32
    io.IONotificationPortCreate.argtypes = (handle,)
    io.IONotificationPortCreate.restype = pointer
    io.IONotificationPortGetRunLoopSource.argtypes = (pointer,)
    io.IONotificationPortGetRunLoopSource.restype = pointer
    io.IONotificationPortDestroy.argtypes = (pointer,)
    io.IONotificationPortDestroy.restype = None
    io.IOServiceMatching.argtypes = (ctypes.c_char_p,)
    io.IOServiceMatching.restype = pointer
    io.IOServiceAddMatchingNotification.argtypes = (pointer, ctypes.c_char_p, pointer, _Matched, pointer, ctypes.POINTER(handle))
    io.IOServiceAddMatchingNotification.restype = ctypes.c_int
    io.IOIteratorNext.argtypes = (handle,)
    io.IOIteratorNext.restype = handle
    io.IOObjectRelease.argtypes = (handle,)
    io.IOObjectRelease.restype = ctypes.c_int
    io.IORegistryEntryCreateCFProperty.argtypes = (handle, pointer, pointer, handle)
    io.IORegistryEntryCreateCFProperty.restype = pointer
    io.IORegistryEntryGetName.argtypes = (handle, ctypes.c_char_p)
    io.IORegistryEntryGetName.restype = ctypes.c_int
    return io


def _device_name(device: int) -> Optional[str]:
    io = _io_registry()
    with _cf.owned(_cf.string("USB Product Name")) as key, _cf.owned(
        io.IORegistryEntryCreateCFProperty(device, key, None, 0)
    ) as name:
        if name:
            return _cf.to_str(name)
    buffer = ctypes.create_string_buffer(128)  # io_name_t
    if io.IORegistryEntryGetName(device, buffer) == 0 and buffer.value:
        return buffer.value.decode("utf-8", "replace")
    return None


class _USBWatch:
    """USB events, from IOKit's matching notifications for USB devices."""

    def __init__(self) -> None:
        io = _io_registry()
        self.port = io.IONotificationPortCreate(0)
        self.iterators: List[int] = []
        self.callbacks = []
        for kind, name in ((b"IOServiceFirstMatch", "usb_connected"), (b"IOServiceTerminate", "usb_disconnected")):
            callback = _Matched(lambda refcon, iterator, name=name: self.matched(iterator, name))
            iterator = ctypes.c_uint32()
            # The matching dictionary is consumed by the call.
            io.IOServiceAddMatchingNotification(
                self.port, kind, io.IOServiceMatching(b"IOUSBHostDevice"), callback, None, ctypes.byref(iterator)
            )
            self.callbacks.append(callback)
            self.iterators.append(iterator.value)
            self.drain(iterator.value, None)  # the devices already there: this also arms the notification
        self.source = _RunLoopSource(io.IONotificationPortGetRunLoopSource(self.port))

    def drain(self, iterator: int, name: Optional[str]) -> None:
        io = _io_registry()
        while True:
            device = io.IOIteratorNext(iterator)
            if not device:
                return
            try:
                if name is not None:
                    _received.append(Event(name, device=_device_name(device)))
            finally:
                io.IOObjectRelease(device)

    def matched(self, iterator: int, name: str) -> None:
        try:
            self.drain(iterator, name)
        except Exception:  # an exception must not cross back into IOKit
            return

    def close(self) -> None:
        self.source.close()  # the port owns the source
        io = _io_registry()
        for iterator in self.iterators:
            io.IOObjectRelease(iterator)
        io.IONotificationPortDestroy(self.port)


_Reconfigured = ctypes.CFUNCTYPE(None, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p)
_BEGIN_CONFIGURATION = 1  # kCGDisplayBeginConfigurationFlag: the change is about to happen


class _DisplayWatch:
    """Display events, from CoreGraphics' reconfiguration callback: one event per change, whatever the displays."""

    def __init__(self) -> None:
        graphics = framework("CoreGraphics")
        graphics.CGDisplayRegisterReconfigurationCallback.argtypes = (_Reconfigured, ctypes.c_void_p)
        graphics.CGDisplayRegisterReconfigurationCallback.restype = ctypes.c_int32
        graphics.CGDisplayRemoveReconfigurationCallback.argtypes = (_Reconfigured, ctypes.c_void_p)
        graphics.CGDisplayRemoveReconfigurationCallback.restype = ctypes.c_int32
        self.callback = _Reconfigured(self.changed)
        graphics.CGDisplayRegisterReconfigurationCallback(self.callback, None)

    def changed(self, display: int, flags: int, info: int) -> None:
        # CoreGraphics calls back for each display, before and after: keep one event per change.
        if not flags & _BEGIN_CONFIGURATION and Event("displays_changed") not in _received:
            _received.append(Event("displays_changed"))

    def close(self) -> None:
        framework("CoreGraphics").CGDisplayRemoveReconfigurationCallback(self.callback, None)


_WATCHERS: Dict[str, Callable[[], Any]] = {
    _POWER: _PowerWatch,
    _NETWORK: _NetworkWatch,
    _USB: _USBWatch,
    _DISPLAYS: _DisplayWatch,
}


def _observer() -> int:
    _objc.define_class("PymacosEventObserver", {"handle:": ("v@:@", _Handle, _handle)})
    return _objc.new("PymacosEventObserver")


def _listen(names: List[str], on_event: Callable[[Event], bool], timeout: Optional[float]) -> None:
    """Observe ``names`` and turn the run loop until ``stop()``, the timeout, or ``on_event`` returning ``True``."""
    framework("AppKit")
    _notification_names()
    observer = _observer()
    wanted = {name: _NOTIFICATIONS[name] for name in names}
    centers = {kind: _center(kind) for kind in (_WORKSPACE, _DISTRIBUTED)}
    # The notification names, as AppKit spells them.
    spelled = {ours: notification for notification, ours in _notification_names().items()}
    for name, (kind, _) in wanted.items():
        if kind in _WATCHED:
            continue
        if kind == _WORKSPACE:
            _objc.send(
                centers[kind],
                "addObserver:selector:name:object:",
                observer,
                _objc.sel("handle:"),
                _objc.nsstring(spelled[name]),
                None,
                argtypes=(_objc.id, _objc.SEL, _objc.id, _objc.id),
                restype=None,
            )
        else:
            # By default the distributed center may hold notifications back while it deems the
            # process suspended; a script has no app lifecycle to resume it, so ask for them now.
            _objc.send(
                centers[kind],
                "addObserver:selector:name:object:suspensionBehavior:",
                observer,
                _objc.sel("handle:"),
                _objc.nsstring(spelled[name]),
                None,
                _DELIVER_IMMEDIATELY,
                argtypes=(_objc.id, _objc.SEL, _objc.id, _objc.id, ctypes.c_ulong),
                restype=None,
            )
    _stop.clear()
    _received.clear()
    kinds = {kind for kind, _ in wanted.values()}
    watchers = [watch() for kind, watch in _WATCHERS.items() if kind in kinds]
    deadline = None if timeout is None else time.monotonic() + timeout
    try:
        while not _stop.is_set():
            remaining = 0.1 if deadline is None else min(0.1, deadline - time.monotonic())
            if remaining <= 0:
                break
            _objc.run_until(lambda: bool(_received) or _stop.is_set(), remaining)
            while _received:
                if on_event(_received.popleft()):
                    return
    finally:
        for watcher in watchers:
            watcher.close()
        for center in centers.values():
            _objc.send(center, "removeObserver:", observer, argtypes=(_objc.id,), restype=None)
        _objc.send(observer, "release", restype=None)


def _takes_event(callback: Callable[..., object]) -> bool:
    """Whether ``callback`` accepts the event; callbacks may also take no arguments."""
    try:
        parameters = inspect.signature(callback).parameters.values()
    except (TypeError, ValueError):  # some builtins have no signature: pass the event
        return True
    return any(
        parameter.kind in (parameter.POSITIONAL_ONLY, parameter.POSITIONAL_OR_KEYWORD, parameter.VAR_POSITIONAL)
        for parameter in parameters
    )


def run(*, timeout: Optional[float] = None) -> None:
    """
    Listen for the events that have callbacks, and call them, until :func:`stop` or ``timeout`` seconds.

    Call it from the main thread: macOS delivers these events there.
    Callbacks run one at a time; an exception in one stops :func:`run` and
    propagates. Ctrl-C stops it too.
    """
    with _lock:
        names = sorted({handler.name for handler in _handlers})
    if not names:
        raise ValueError("no callbacks registered: add some with macos.events.on() first")

    def call(event: Event) -> bool:
        with _lock:
            callbacks = [handler.callback for handler in _handlers if handler.name == event.name]
        for callback in callbacks:
            if _takes_event(callback):
                callback(event)
            else:
                callback()
        return False

    _listen(names, call, timeout)


def wait(name: str, *, timeout: Optional[float] = None) -> Optional[Event]:
    """
    Wait until ``name`` happens, and return the :class:`Event`; ``None`` if ``timeout`` seconds pass first.

    ::

        macos.events.wait("screen_unlocked")
        print("welcome back")
    """
    _check(name)
    found: List[Event] = []

    def check(event: Event) -> bool:
        if event.name == name:
            found.append(event)
            return True
        return False

    _listen([name], check, timeout)
    return found[0] if found else None
