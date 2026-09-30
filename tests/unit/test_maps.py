"""Unit tests for :mod:`macos.maps`. They run on any platform."""

import threading

import pytest

import macos
from macos import maps

PLACE = maps.Place("Eiffel Tower", "5 Avenue Anatole France", "Paris", "Île-de-France", "75007", "France", "FR",
                   48.8584, 2.2945, "Europe/Paris")  # fmt: skip


def test_results_and_errors():
    assert maps._result([PLACE], None) == [PLACE]
    assert maps._result([], (8, "No result")) == []  # nothing found isn't an error
    with pytest.raises(macos.MacOSError, match="could not reach Apple's geocoding service"):
        maps._result([], (2, "The network is down"))
    with pytest.raises(macos.MacOSError, match="error 10"):
        maps._result([], (10, "Canceled"))


def test_argument_checks():
    with pytest.raises(ValueError, match="address must not be empty"):
        maps.geocode("  ")
    for latitude, longitude in ((91, 0), (0, 181), (-90.5, 0)):
        with pytest.raises(ValueError, match="latitude must be"):
            maps.reverse_geocode(latitude, longitude)


def test_only_the_main_thread_gets_answers():
    failures = []

    def ask():
        try:
            maps._ask("geocodeAddressString:completionHandler:", 0, timeout=1)
        except macos.MacOSError as error:
            failures.append(str(error))

    thread = threading.Thread(target=ask)
    thread.start()
    thread.join()
    assert failures == ["geocoding answers on the main thread: call it from there"]
