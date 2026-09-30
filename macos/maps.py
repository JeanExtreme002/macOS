# -*- coding: utf-8 -*-

"""
Turn an address into coordinates, and coordinates into an address, as Maps does.

::

    place = macos.maps.geocode("Avenida Paulista, 1578, São Paulo")[0]
    place.latitude, place.longitude          # (-23.5614, -46.6559)
    macos.maps.reverse_geocode(48.8584, 2.2945).city   # 'Paris'

Goes through Apple's geocoding service (``CLGeocoder``): it needs the
internet but no permission, not even Location. Apple limits how many
requests an app makes in a short time: space out large batches.
"""

import ctypes
import threading
from dataclasses import dataclass
from typing import List, Optional, Tuple

from . import _objc
from ._system import framework
from .errors import MacOSError

__all__ = ["Place", "geocode", "reverse_geocode"]

# kCLErrorDomain's codes.
_NETWORK, _NOT_FOUND = 2, 8


class _Coordinate(ctypes.Structure):
    _fields_ = [("latitude", ctypes.c_double), ("longitude", ctypes.c_double)]


@dataclass(frozen=True)
class Place:
    """A place found by :func:`geocode` or :func:`reverse_geocode`. Parts macOS doesn't know are ``None``."""

    name: Optional[str]
    """Such as ``'Eiffel Tower'`` or ``'1 Infinite Loop'``."""
    street: Optional[str]
    """The street, with the number when there's one: ``'Avenida Paulista, 1578'``."""
    city: Optional[str]
    state: Optional[str]
    postal_code: Optional[str]
    country: Optional[str]
    country_code: Optional[str]
    """ISO 3166 code, such as ``'BR'``."""
    latitude: float
    longitude: float
    time_zone: Optional[str]
    """Such as ``'America/Sao_Paulo'``."""


# One geocoding request at a time, as CLGeocoder allows.
_lock = threading.Lock()


def _text(placemark: int, key: str) -> Optional[str]:
    return _objc.pystring(_objc.send(placemark, key)) or None


def _place(placemark: int) -> Place:
    location = _objc.send(placemark, "location")
    point = _objc.send(location, "coordinate", restype=_Coordinate)
    # The postal address writes the street as each country does: "1 Infinite Loop", "Avenida Paulista, 1578".
    address = _objc.send(placemark, "postalAddress")
    street = _objc.pystring(_objc.send(address, "street")) if address else None
    zone = _objc.send(placemark, "timeZone")
    return Place(
        name=_text(placemark, "name"),
        street=street or _text(placemark, "thoroughfare"),
        city=_text(placemark, "locality"),
        state=_text(placemark, "administrativeArea"),
        postal_code=_text(placemark, "postalCode"),
        country=_text(placemark, "country"),
        country_code=_text(placemark, "ISOcountryCode"),
        latitude=round(point.latitude, 6),
        longitude=round(point.longitude, 6),
        time_zone=_objc.pystring(_objc.send(zone, "name")) if zone else None,
    )


Answer = Tuple[List[Place], Optional[Tuple[int, str]]]


def _handler(answers: List[Answer]) -> int:
    """A completion block, ``void (^)(NSArray<CLPlacemark *> *, NSError *)``, that files the answer in ``answers``."""

    def done(placemarks: Optional[int], error: Optional[int]) -> None:
        # Read everything now: the placemarks go away with the block's call.
        found = [_place(placemark) for placemark in _objc.nsarray(placemarks)] if placemarks else []
        failure = None
        if error:
            code = int(_objc.send(error, "code", restype=ctypes.c_long))
            failure = (code, _objc.pystring(_objc.send(error, "localizedDescription")) or "")
        answers.append((found, failure))

    return _objc.block(done, b"v@?@@", ctypes.c_void_p, ctypes.c_void_p)


def _frameworks() -> None:
    framework("CoreLocation")
    framework("Contacts")  # for the placemarks' postal addresses


def _ask(selector: str, argument: int, timeout: float) -> List[Place]:
    if threading.current_thread() is not threading.main_thread():
        raise MacOSError("geocoding answers on the main thread: call it from there")
    # Each request has its own block and answers: a canceled one's late answer lands in its
    # own list, which nobody reads, and can't pass for the next request's.
    answers: List[Answer] = []
    with _lock:
        geocoder = _objc.send(_objc.send(_objc.cls("CLGeocoder"), "alloc"), "init")
        try:
            _objc.send(geocoder, selector, argument, _handler(answers), argtypes=(_objc.id, ctypes.c_void_p), restype=None)
            if not _objc.run_until(lambda: bool(answers), timeout):
                _objc.send(geocoder, "cancelGeocode", restype=None)
                raise TimeoutError("Apple's geocoding service didn't answer within {} seconds".format(timeout))
        finally:
            _objc.send(geocoder, "release", restype=None)
    found, failure = answers[0]
    return _result(found, failure)


def _result(found: List[Place], failure: Optional[Tuple[int, str]]) -> List[Place]:
    """The places, or the error the service gave; finding nothing isn't an error."""
    if failure and failure[0] != _NOT_FOUND:
        if failure[0] == _NETWORK:
            raise MacOSError("could not reach Apple's geocoding service (offline, or too many requests): " + failure[1])
        raise MacOSError("geocoding failed: {} (error {})".format(failure[1], failure[0]))
    return found


def geocode(address: str, *, timeout: float = 15) -> List[Place]:
    """
    The places matching ``address``, the likeliest first; ``[]`` when none does.

    ::

        place = macos.maps.geocode("1 Infinite Loop, Cupertino")[0]
        place.latitude, place.longitude      # (37.3318, -122.0302)
        place.city, place.country_code       # ('Cupertino', 'US')

    Any address works, whole or in part, in any language; names come back
    in the system's language. The service guesses rather than give up, so
    check the place's ``country_code`` or ``city`` for vague addresses.
    """
    if not address.strip():
        raise ValueError("address must not be empty")
    _frameworks()
    with _objc.autorelease_pool():
        return _ask("geocodeAddressString:completionHandler:", _objc.nsstring(address), timeout)


def reverse_geocode(latitude: float, longitude: float, *, timeout: float = 15) -> Optional[Place]:
    """
    The address at ``latitude``, ``longitude``, or ``None`` when macOS finds nothing there.

    Out at sea it's the ocean's name, without an address.

    ::

        macos.maps.reverse_geocode(-22.9519, -43.2105).city   # 'Rio de Janeiro'
    """
    if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
        raise ValueError("latitude must be from -90 to 90 and longitude from -180 to 180, not {}, {}".format(latitude, longitude))
    _frameworks()
    with _objc.autorelease_pool():
        location = _objc.send(
            _objc.send(_objc.cls("CLLocation"), "alloc"),
            "initWithLatitude:longitude:",
            float(latitude),
            float(longitude),
            argtypes=(ctypes.c_double, ctypes.c_double),
        )
        try:
            found = _ask("reverseGeocodeLocation:completionHandler:", location, timeout)
        finally:
            _objc.send(location, "release", restype=None)
    return found[0] if found else None
